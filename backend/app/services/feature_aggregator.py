"""Per-account feature aggregation in Redis.

Two layers:
  1. Base snapshot (`account:{id}:features`) — pre-loaded by seed.py from the
     real `account_feature_matrix.parquet`. Static for the lifetime of the
     replay (one row of 146 features). This is what the model actually
     scores on; the live deltas only nudge a small subset.
  2. Live deltas (`account:{id}:deltas`) — updated by the Kafka consumer on
     every event for that account. Fields tracked: n, n_offhours, n_weekend,
     n_struct_45_49k, sum_credit, sum_debit, n_unique_ips, last_event_ts.
     Applied to the base row before scoring.

We deliberately do NOT recompute all 146 features online — most are graph,
balance, or KYC features that don't change during a 5-minute demo. The
deltas just make the score "respond" to incoming events.
"""

from __future__ import annotations

import time
from typing import Any

import redis.asyncio as aioredis
import structlog

from app.config import settings

log = structlog.get_logger(__name__)

DELTA_TTL_SECONDS = 24 * 3600
LASTSCORE_TTL_SECONDS = 3600


class FeatureAggregator:
    def __init__(self, url: str | None = None) -> None:
        self._url = url or settings.REDIS_URL
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        if self._client is None:
            self._client = aioredis.from_url(self._url, decode_responses=True)
            await self._client.ping()
            log.info("feature_aggregator.connected", url=self._url.split("@")[-1])

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("FeatureAggregator not connected; call .connect() first.")
        return self._client

    @staticmethod
    def base_key(account_id: str) -> str:
        return f"account:{account_id}:features"

    @staticmethod
    def deltas_key(account_id: str) -> str:
        return f"account:{account_id}:deltas"

    @staticmethod
    def lastscore_key(account_id: str) -> str:
        return f"account:{account_id}:lastscore"

    async def store_base_features(self, account_id: str, features: dict[str, Any]) -> None:
        """Snapshot the 146-column feature row. No TTL — stays for the lifetime of seed."""
        flat = {k: ("" if v is None else str(v)) for k, v in features.items()}
        await self.client.hset(self.base_key(account_id), mapping=flat)

    async def get_base_features(self, account_id: str) -> dict[str, Any]:
        raw = await self.client.hgetall(self.base_key(account_id))
        return {k: _try_float(v) for k, v in raw.items()}

    async def has_base_features(self, account_id: str) -> bool:
        return bool(await self.client.exists(self.base_key(account_id)))

    async def apply_event_delta(self, account_id: str, event: dict[str, Any]) -> None:
        """Incrementally update live deltas from a single event."""
        amount = abs(float(event.get("amount", 0.0)))
        is_credit = event.get("txn_type") == "C"
        is_after_hours = bool(event.get("is_after_hours", False))
        is_weekend = bool(event.get("is_weekend", False))
        in_struct_band = 45_000 <= amount <= 49_999
        ip = event.get("ip_address") or event.get("workstation_ip", "")

        pipe = self.client.pipeline(transaction=False)
        key = self.deltas_key(account_id)
        pipe.hincrby(key, "live_n", 1)
        if is_after_hours:
            pipe.hincrby(key, "live_pngt_n", 1)
        if is_weekend:
            pipe.hincrby(key, "live_pwkd_n", 1)
        if in_struct_band:
            pipe.hincrby(key, "live_ps49_n", 1)
        if is_credit:
            pipe.hincrbyfloat(key, "live_credit_sum", amount)
        else:
            pipe.hincrbyfloat(key, "live_debit_sum", amount)
        if ip:
            pipe.sadd(f"account:{account_id}:ips", ip)
            pipe.expire(f"account:{account_id}:ips", DELTA_TTL_SECONDS)
        pipe.hset(key, "live_last_ts", str(time.time()))
        pipe.expire(key, DELTA_TTL_SECONDS)
        await pipe.execute()

    async def get_deltas(self, account_id: str) -> dict[str, float]:
        raw = await self.client.hgetall(self.deltas_key(account_id))
        return {k: _try_float(v) for k, v in raw.items()}

    async def get_unique_ip_count(self, account_id: str) -> int:
        return int(await self.client.scard(f"account:{account_id}:ips"))

    async def features_for_scoring(self, account_id: str) -> dict[str, Any] | None:
        """Return the merged base + delta feature dict ready for ScoringService.score()."""
        base = await self.get_base_features(account_id)
        if not base:
            return None
        deltas = await self.get_deltas(account_id)

        # Apply nudges. We add deltas to live counters that map onto model
        # features. Magnitudes are intentionally conservative (e.g. only
        # adding live_n / 10 to baseline `n`) so the demo doesn't see runaway
        # score drift from a single event.
        live_n = deltas.get("live_n", 0)
        if live_n:
            base["n"] = float(base.get("n", 0)) + live_n / 10.0

            pngt_n = deltas.get("live_pngt_n", 0)
            ps49_n = deltas.get("live_ps49_n", 0)

            new_pngt = pngt_n / max(live_n, 1)
            new_ps49 = ps49_n / max(live_n, 1)
            # Blend live ratio in 30/70 with baseline so a few burst events nudge but don't overwhelm
            base["pngt"] = 0.7 * float(base.get("pngt", 0)) + 0.3 * new_pngt
            base["ps49"] = 0.7 * float(base.get("ps49", 0)) + 0.3 * new_ps49

            credit_sum = deltas.get("live_credit_sum", 0.0)
            debit_sum = deltas.get("live_debit_sum", 0.0)
            if debit_sum > 0:
                live_fan = credit_sum / debit_sum
                base["fan_ratio"] = 0.7 * float(base.get("fan_ratio", 1)) + 0.3 * live_fan

        live_ips = await self.get_unique_ip_count(account_id)
        if live_ips:
            base["n_unique_ips"] = max(float(base.get("n_unique_ips", 0)), live_ips)
        return base

    async def remember_score(self, account_id: str, score: float, level: str) -> None:
        await self.client.set(
            self.lastscore_key(account_id),
            f"{score:.6f}|{level}",
            ex=LASTSCORE_TTL_SECONDS,
        )

    # -- Replay state ---------------------------------------------------

    async def set_replay_status(self, status: str) -> None:
        await self.client.set("replay:status", status)

    async def get_replay_status(self) -> str:
        return (await self.client.get("replay:status")) or "idle"

    async def update_replay_stats(self, **fields: Any) -> None:
        if fields:
            await self.client.hset(
                "replay:stats", mapping={k: str(v) for k, v in fields.items()}
            )

    async def increment_replay_stat(self, field: str, by: int = 1) -> int:
        return int(await self.client.hincrby("replay:stats", field, by))

    async def get_replay_stats(self) -> dict[str, str]:
        return await self.client.hgetall("replay:stats")

    async def reset_replay_stats(self) -> None:
        await self.client.delete("replay:stats")


def _try_float(v: Any) -> Any:
    if v in (None, "", "nan", "None"):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return v


feature_aggregator = FeatureAggregator()
