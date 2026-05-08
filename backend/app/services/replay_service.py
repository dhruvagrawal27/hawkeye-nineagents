"""JSONL → Kafka replay producer.

Modes:
  - sequential   : stream events in JSONL order
  - mule_burst   : front-load events from the top-N highest-score mule accounts
                   (default N=10), then revert to sequential. Guarantees an
                   alert within 30-60s of replay start. This is the demo path.
  - inject_burst : one-shot — publish ~50 events from top-5 mules immediately.
                   Wired to the "Inject Mule Burst" button in Replay Studio.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import structlog
from confluent_kafka import Producer

from app.config import settings
from app.services.feature_aggregator import feature_aggregator

log = structlog.get_logger(__name__)


def _delivery_report(err, msg) -> None:
    if err is not None:
        log.warning("replay.delivery_failed", error=str(err), topic=msg.topic())


class ReplayService:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._producer: Producer | None = None
        self._mule_acct_ids: list[str] = []

    def _ensure_producer(self) -> Producer:
        if self._producer is None:
            self._producer = Producer(
                {
                    "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                    "client.id": "hawkeye-replay",
                    "linger.ms": 10,
                    "batch.size": 16384,
                    "queue.buffering.max.messages": 100000,
                }
            )
        return self._producer

    @staticmethod
    def _events_path() -> Path:
        return settings.data_path / "synthetic_events.jsonl"

    @staticmethod
    def _accounts_path() -> Path:
        return settings.data_path / "synthetic_accounts.parquet"

    def _load_mule_account_ids(self, top_n: int = 10) -> list[str]:
        """Top-N mules by virtual is_mule flag from the synthetic accounts file."""
        if self._mule_acct_ids:
            return self._mule_acct_ids[:top_n]
        try:
            import pandas as pd

            sa = pd.read_parquet(self._accounts_path())
            mules = sa[sa["is_mule"] == 1]["account_id"].tolist()
            self._mule_acct_ids = mules
            return mules[:top_n]
        except Exception as exc:
            log.warning("replay.mule_index_load_failed", error=str(exc))
            return []

    async def start(
        self,
        mode: str = "mule_burst",
        rate: int | None = None,
        reset_alerts: bool = True,
    ) -> dict[str, Any]:
        if self._task and not self._task.done():
            return {"status": "already_running"}
        rate = max(1, min(int(rate or settings.REPLAY_DEFAULT_RATE), settings.REPLAY_MAX_RATE))

        # Auto-dismiss prior replay-sourced open alerts so each demo run sees
        # fresh alerts firing instead of everything dedup'ing into existing rows.
        n_dismissed = 0
        if reset_alerts:
            from sqlalchemy import update

            from app.models.alert import Alert
            from app.models.db import get_session

            async for db in get_session():
                stmt = (
                    update(Alert)
                    .where(Alert.status == "open", Alert.source == "replay")
                    .values(status="dismissed")
                )
                result = await db.execute(stmt)
                n_dismissed = result.rowcount or 0
                await db.commit()
            log.info("replay.alerts_reset", dismissed=n_dismissed)

        self._stop_event.clear()
        await feature_aggregator.connect()
        await feature_aggregator.set_replay_status("running")
        await feature_aggregator.reset_replay_stats()
        await feature_aggregator.update_replay_stats(
            mode=mode, rate=rate, started_at=str(int(time.time())), events_published=0, alerts_fired=0
        )
        self._task = asyncio.create_task(self._run_loop(mode=mode, rate=rate))
        log.info("replay.started", mode=mode, rate=rate)
        return {"status": "running", "mode": mode, "rate": rate, "alerts_dismissed": n_dismissed}

    async def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except TimeoutError:
                self._task.cancel()
        if self._producer:
            self._producer.flush(timeout=2.0)
        await feature_aggregator.set_replay_status("idle")
        log.info("replay.stopped")
        return {"status": "idle"}

    async def status(self) -> dict[str, Any]:
        s = await feature_aggregator.get_replay_status()
        stats = await feature_aggregator.get_replay_stats()
        return {"status": s, "stats": stats}

    async def inject_burst(self, n_events: int = 50, top_mules: int = 5) -> dict[str, Any]:
        await feature_aggregator.connect()
        producer = self._ensure_producer()
        mule_ids = set(self._load_mule_account_ids(top_n=top_mules))
        if not mule_ids:
            return {"published": 0, "reason": "no_mule_index"}
        published = 0
        async for event in self._iter_events():
            if event.get("account_id") not in mule_ids:
                continue
            self._publish(producer, event)
            published += 1
            if published >= n_events:
                break
        producer.flush(timeout=5.0)
        await feature_aggregator.increment_replay_stat("events_published", published)
        log.info("replay.inject_burst", published=published, top_mules=top_mules)
        return {"published": published}

    async def _iter_events(self):
        path = self._events_path()
        if not path.exists():
            log.error("replay.events_file_missing", path=str(path))
            return
        loop = asyncio.get_running_loop()
        with open(path, encoding="utf-8") as f:
            while True:
                line = await loop.run_in_executor(None, f.readline)
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def _publish(self, producer: Producer, event: dict[str, Any]) -> None:
        producer.produce(
            settings.KAFKA_TOPIC_EVENTS,
            json.dumps(event).encode("utf-8"),
            key=event.get("account_id", "").encode("utf-8") or None,
            on_delivery=_delivery_report,
        )
        producer.poll(0)

    async def _run_loop(self, mode: str, rate: int) -> None:
        producer = self._ensure_producer()
        mule_ids = set(self._load_mule_account_ids(top_n=10))
        published = 0
        sleep_between = 1.0 / rate if rate > 0 else 0.0
        try:
            # Phase 1 — front-load mule events when in mule_burst mode
            if mode == "mule_burst" and mule_ids:
                async for event in self._iter_events():
                    if self._stop_event.is_set():
                        break
                    if event.get("account_id") in mule_ids:
                        self._publish(producer, event)
                        published += 1
                        if published % 50 == 0:
                            await feature_aggregator.update_replay_stats(events_published=published)
                            producer.poll(0)
                        if sleep_between:
                            await asyncio.sleep(sleep_between)
                        if published >= 200:
                            break
                log.info("replay.mule_burst_phase_complete", published=published)

            # Phase 2 — sequential everything (replays the file)
            async for event in self._iter_events():
                if self._stop_event.is_set():
                    break
                self._publish(producer, event)
                published += 1
                if published % 100 == 0:
                    producer.poll(0)
                    await feature_aggregator.update_replay_stats(events_published=published)
                if sleep_between:
                    await asyncio.sleep(sleep_between)
        except asyncio.CancelledError:
            log.info("replay.task_cancelled", published=published)
            raise
        except Exception as exc:
            log.exception("replay.task_failed", error=str(exc))
        finally:
            producer.flush(timeout=2.0)
            await feature_aggregator.update_replay_stats(events_published=published)
            await feature_aggregator.set_replay_status("idle")
            log.info("replay.loop_finished", published=published)


replay_service = ReplayService()
