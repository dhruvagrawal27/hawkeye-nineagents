"""Kafka consumer that scores events and creates alerts.

Runs as a single asyncio background task (started in main.py lifespan).
Pull-loops on the `hawkeye.events` topic, applies the event delta to
Redis-cached features, scores against the LightGBM blend, and creates
an alert (with Groq narrative) when score >= threshold.

Why a single-process consumer:
- The scoring service is an in-memory singleton (LightGBM models + SHAP).
- The WebSocket manager is also in-memory.
- Horizontal scaling would require a Redis pub/sub or Kafka consumer group
  with stickier partitioning. Out of scope for the demo. Documented in
  ARCHITECTURE.md.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog
from confluent_kafka import Consumer, KafkaError

from app.config import settings
from app.models.alert import Alert
from app.models.db import get_session
from app.models.employee import ScoreHistory
from app.services.alert_service import (
    _employee_id_from_account,
    create_or_update_alert,
)
from app.services.feature_aggregator import feature_aggregator
from app.services.graph_service import graph_service
from app.services.narrative_service import narrative_service
from app.services.scoring import scoring_service

log = structlog.get_logger(__name__)

SYSTEM_FROM_CP_PREFIX = ("CP_", "SYS_")


def _system_from_cp(cp: str | None) -> str:
    if not cp:
        return "SYS_UNKNOWN"
    if cp.startswith("CP_"):
        return "SYS_" + cp[3:]
    return cp if cp.startswith("SYS_") else f"SYS_{cp}"


class EventConsumer:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._consumer: Consumer | None = None

    def _ensure_consumer(self) -> Consumer:
        if self._consumer is None:
            self._consumer = Consumer(
                {
                    "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                    "group.id": settings.KAFKA_CONSUMER_GROUP,
                    "auto.offset.reset": "latest",
                    "enable.auto.commit": True,
                    "auto.commit.interval.ms": 5000,
                    "session.timeout.ms": 30000,
                }
            )
            self._consumer.subscribe([settings.KAFKA_TOPIC_EVENTS])
        return self._consumer

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        log.info("consumer.started", topic=settings.KAFKA_TOPIC_EVENTS, group=settings.KAFKA_CONSUMER_GROUP)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except TimeoutError:
                self._task.cancel()
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None

    async def _run(self) -> None:
        consumer = self._ensure_consumer()
        loop = asyncio.get_running_loop()
        try:
            while not self._stop_event.is_set():
                msg = await loop.run_in_executor(None, consumer.poll, 1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        log.warning("consumer.kafka_error", error=str(msg.error()))
                    continue
                try:
                    event = json.loads(msg.value().decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                try:
                    await self._handle_event(event)
                except Exception as exc:
                    log.exception("consumer.handle_event_failed", error=str(exc))
        except asyncio.CancelledError:
            raise
        finally:
            consumer.close()
            self._consumer = None

    async def _handle_event(self, event: dict[str, Any]) -> None:
        account_id = event.get("account_id")
        if not account_id:
            return
        employee_id = _employee_id_from_account(account_id)
        system_id = _system_from_cp(event.get("counterparty_id") or event.get("system_resource"))
        ts = event.get("transaction_timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ")
        access_type = event.get("access_type") or ("WRITE" if event.get("txn_type") == "D" else "READ")

        # 1. Update Redis live deltas
        await feature_aggregator.apply_event_delta(account_id, event)

        # 2. Update Neo4j (fire-and-forget — graph errors mustn't block scoring)
        try:
            await graph_service.upsert_event(
                employee_id=employee_id,
                account_id=account_id,
                system_id=system_id,
                access_type=access_type,
                ts=ts,
            )
        except Exception as exc:
            log.warning("consumer.graph_upsert_failed", error=str(exc), employee_id=employee_id)

        # 3. Score (need base features; if missing, skip scoring but keep delta)
        features = await feature_aggregator.features_for_scoring(account_id)
        if features is None:
            return  # account not seeded — graph still updates, no alert path

        result = scoring_service.score(features, account_id=account_id)
        await feature_aggregator.remember_score(account_id, result.score, result.risk_level)

        # Stream a sampled tick to the UI for the live event ticker.
        # Throttle per-account so a hot mule doesn't flood the WS.
        await self._maybe_emit_tick(
            employee_id=employee_id,
            account_id=account_id,
            score=result.display_score,
            raw_score=result.score,
            risk_level=result.risk_level,
            is_alert=result.is_alert,
            top_signal=result.factors[0].name_human if result.factors else None,
            event=event,
        )

        if result.score >= 0.5:
            log.info(
                "consumer.score_high",
                employee_id=employee_id,
                score=result.score,
                level=result.risk_level,
                top_factor=result.factors[0].name_human if result.factors else None,
            )

        if not result.is_alert:
            return

        # 4. Persist score history (sample one per minute per account to avoid flood)
        await self._maybe_record_score(employee_id, result.score, result.display_score)

        # 5. Create or dedupe alert
        async for db in get_session():
            alert, is_new = await create_or_update_alert(
                db,
                account_id=account_id,
                score_result=result,
                source="replay",
            )
            if is_new:
                await feature_aggregator.increment_replay_stat("alerts_fired", 1)
                # Update graph score
                try:
                    await graph_service.update_employee_score(
                        employee_id=employee_id,
                        account_id=account_id,
                        score=result.score,
                        risk_level=result.risk_level,
                    )
                except Exception as exc:
                    log.warning("consumer.graph_score_update_failed", error=str(exc))
                # Generate narrative async (don't block consumer)
                asyncio.create_task(self._generate_narrative_for(alert.id))

    _last_score_record: dict[str, float] = {}
    _last_tick_emit: dict[str, float] = {}
    _global_tick_count: int = 0

    async def _maybe_emit_tick(
        self,
        *,
        employee_id: str,
        account_id: str,
        score: float,
        raw_score: float,
        risk_level: str,
        is_alert: bool,
        top_signal: str | None,
        event: dict[str, Any],
    ) -> None:
        """Stock-ticker style WebSocket pulse.

        Always emit alerts. For non-alerting events, throttle per-account to
        ~1/sec so the WS stays useful but doesn't flood the client.
        """
        from app.services.alert_service import broadcast_event

        now = time.time()
        last = self._last_tick_emit.get(employee_id, 0.0)
        if not is_alert and (now - last) < 1.0:
            # Skip — recently sent a tick for this employee
            return
        self._last_tick_emit[employee_id] = now
        self._global_tick_count += 1

        await broadcast_event(
            {
                "type": "event.scored",
                "tick_id": self._global_tick_count,
                "employee_id": employee_id,
                "account_id": account_id,
                "score": score,
                "raw_score": raw_score,
                "risk_level": risk_level,
                "is_alert": is_alert,
                "top_signal": top_signal,
                "amount": float(event.get("amount") or 0.0),
                "txn_type": event.get("txn_type", ""),
                "channel": event.get("channel", ""),
                "is_after_hours": bool(event.get("is_after_hours", False)),
                "ts": event.get("transaction_timestamp"),
                # Insider-fraud signal fields per problem statement
                "system_resource": event.get("system_resource") or _system_from_cp(event.get("counterparty_id")),
                "access_type": event.get("access_type") or ("WRITE" if event.get("txn_type") == "D" else "READ"),
                "records_accessed": int(event.get("records_accessed") or 0),
            }
        )

    async def _maybe_record_score(self, employee_id: str, score: float, display: float) -> None:
        now = time.time()
        last = self._last_score_record.get(employee_id, 0.0)
        if now - last < 60.0:
            return
        self._last_score_record[employee_id] = now
        async for db in get_session():
            db.add(ScoreHistory(employee_id=employee_id, score=score, display_score=display))
            await db.commit()

    async def _generate_narrative_for(self, alert_id: int) -> None:
        try:
            from sqlalchemy import select

            async for db in get_session():
                alert = await db.get(Alert, alert_id)
                if alert is None:
                    return
                # Skip if narrative already exists
                from app.models.narrative import Narrative

                existing = (
                    await db.execute(select(Narrative).where(Narrative.alert_id == alert_id))
                ).scalar_one_or_none()
                if existing:
                    return
                shap_factors = list(alert.shap_factors) if alert.shap_factors else []
                # Build behaviour summary from base features
                base = await feature_aggregator.get_base_features(alert.account_id) or {}
                behaviour = {
                    "n_txn": int(float(base.get("n", 0) or 0)),
                    "pass_rate_pct": int(float(base.get("pass_rate", 0) or 0) * 100),
                    "pngt_pct": int(float(base.get("pngt", 0) or 0) * 100),
                    "ps49_pct": int(float(base.get("ps49", 0) or 0) * 100),
                    "fan_ratio": round(float(base.get("fan_ratio", 1) or 1), 2),
                    "shared_systems": 0,
                    "flagged_peers": 0,
                }
                try:
                    shared = await graph_service.shared_systems(alert.employee_id)
                    if shared:
                        behaviour["shared_systems"] = len(shared)
                        peers: set[str] = set()
                        for row in shared:
                            peers.update(row.get("peers", []))
                        behaviour["flagged_peers"] = len(peers)
                except Exception:
                    pass

                result = await narrative_service.generate(
                    employee_id=alert.employee_id,
                    score=float(alert.display_score),
                    raw_score=float(alert.score),
                    risk_level=alert.risk_level,
                    threshold=scoring_service.threshold,
                    factors=shap_factors,
                    behaviour=behaviour,
                )
                db.add(
                    Narrative(
                        alert_id=alert.id,
                        body=result.body,
                        model_version=result.model_version,
                        is_fallback=result.is_fallback,
                        latency_ms=result.latency_ms,
                    )
                )
                await db.commit()
                log.info(
                    "narrative.generated",
                    alert_id=alert.id,
                    is_fallback=result.is_fallback,
                    latency_ms=result.latency_ms,
                )
        except Exception as exc:
            log.exception("narrative.generation_failed", alert_id=alert_id, error=str(exc))


event_consumer = EventConsumer()
