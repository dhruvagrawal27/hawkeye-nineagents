"""Groq-backed investigation narrative generator with deterministic fallback.

Failure modes (timeout, rate limit, network) NEVER bubble up — we degrade
to a Jinja-rendered fallback with the same structure (4 paragraphs +
audit trail footer) so the UI cannot tell them apart. The fallback path
is logged at WARN with `groq_failure=true` for grep-ability.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from groq import APIError, APITimeoutError, AsyncGroq, RateLimitError
from jinja2 import Environment, FileSystemLoader, select_autoescape
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

log = structlog.get_logger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_env = Environment(
    loader=FileSystemLoader(str(PROMPTS_DIR)),
    autoescape=select_autoescape(default=False),
    keep_trailing_newline=True,
)
_PROMPT_TEMPLATE = _env.get_template("investigation_narrative.jinja2")


@dataclass(frozen=True)
class NarrativeResult:
    body: str
    is_fallback: bool
    latency_ms: int
    model_version: str


def _audit_footer(factors: list[dict[str, Any]]) -> str:
    out = ["", "---", "**Audit trail — model factors:**", ""]
    for f in factors:
        contribution = f.get("contribution", 0.0)
        out.append(
            f"- `{f['name']}` = {float(f.get('value', 0.0)):.4f}"
            f"  →  contribution {contribution:+.4f}  ({f.get('name_human', f['name'])})"
        )
    return "\n".join(out)


def _fallback_narrative(employee_id: str, score: float, risk_level: str, factors: list[dict[str, Any]], behaviour: dict[str, Any]) -> str:
    top_factor = factors[0] if factors else {"name_human": "abnormal behaviour", "value_human": "n/a"}
    txn = behaviour.get("n_txn", "n/a")
    pass_rate = behaviour.get("pass_rate_pct", "n/a")
    pngt = behaviour.get("pngt_pct", "n/a")
    ps49 = behaviour.get("ps49_pct", "n/a")
    fan = behaviour.get("fan_ratio", "n/a")
    shared = behaviour.get("shared_systems", "n/a")
    peers = behaviour.get("flagged_peers", "n/a")

    body = (
        f"**Risk Summary**\n"
        f"Employee {employee_id} triggered a {risk_level} alert with a model score of {score:.3f}. "
        f"The dominant signal is {top_factor['name_human']} at {top_factor.get('value_human','n/a')}. "
        f"Score exceeds the trained threshold and warrants immediate analyst review.\n\n"
        f"**What We Observed**\n"
        f"Across the observation window, {txn} transactions were recorded with a balance "
        f"pass-through rate of {pass_rate}% and an off-hours fraction of {pngt}%. "
        f"Structuring activity in the 45-49K range accounted for {ps49}% of transactions, "
        f"and counterparty fan-ratio is {fan}.\n\n"
        f"**Why It Matters**\n"
        f"This pattern matches the canonical mule-account profile: high pass-through, "
        f"after-hours bursts, and structuring just below the cash-reporting threshold. "
        f"The graph layer shows this employee shares {shared} systems with {peers} other "
        f"flagged employees, indicating possible coordination.\n\n"
        f"**Recommended Next Step**\n"
        f"Open a Tier-2 investigation. Pull the last 30 days of authorisation logs, freeze "
        f"the workstation IP for forensic capture, and brief the Branch Compliance Officer. "
        f"Do not close the ticket without human review.\n"
    )
    return body + _audit_footer(factors)


class NarrativeService:
    def __init__(self) -> None:
        self._client: AsyncGroq | None = None

    @property
    def client(self) -> AsyncGroq:
        if self._client is None:
            if not settings.GROQ_API_KEY:
                raise RuntimeError("GROQ_API_KEY not configured")
            self._client = AsyncGroq(api_key=settings.GROQ_API_KEY, timeout=settings.GROQ_TIMEOUT_SECONDS)
        return self._client

    async def generate(
        self,
        *,
        employee_id: str,
        score: float,
        raw_score: float,
        risk_level: str,
        threshold: float,
        factors: list[dict[str, Any]],
        behaviour: dict[str, Any],
    ) -> NarrativeResult:
        prompt = _PROMPT_TEMPLATE.render(
            employee_id=employee_id,
            score=score,
            raw_score=raw_score,
            risk_level=risk_level,
            threshold=threshold,
            factors=factors,
            behaviour=behaviour,
        )

        t0 = time.perf_counter()

        if not settings.GROQ_API_KEY:
            log.warning("narrative.groq_disabled.using_fallback", employee_id=employee_id)
            body = _fallback_narrative(employee_id, score, risk_level, factors, behaviour)
            return NarrativeResult(
                body=body,
                is_fallback=True,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                model_version=f"{settings.GROQ_MODEL}-fallback",
            )

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.5, max=4.0),
                retry=retry_if_exception_type((APITimeoutError, RateLimitError, APIError, asyncio.TimeoutError)),
                reraise=True,
            ):
                with attempt:
                    # gpt-oss models on Groq are reasoning models — allow headroom
                    # for completion content after the (low) reasoning budget.
                    response = await self.client.chat.completions.create(
                        model=settings.GROQ_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=1500,
                        reasoning_effort="low",
                    )
            body = (response.choices[0].message.content or "").strip()
            if len(body) < 80:
                raise ValueError(f"narrative too short (len={len(body)})")
            body = body + _audit_footer(factors)
            return NarrativeResult(
                body=body,
                is_fallback=False,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                model_version=settings.GROQ_MODEL,
            )
        except (RetryError, APIError, APITimeoutError, RateLimitError, asyncio.TimeoutError, ValueError) as exc:
            log.warning(
                "narrative.groq_failure.using_fallback",
                employee_id=employee_id,
                groq_failure=True,
                error=str(exc)[:200],
                error_type=type(exc).__name__,
            )
            body = _fallback_narrative(employee_id, score, risk_level, factors, behaviour)
            return NarrativeResult(
                body=body,
                is_fallback=True,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                model_version=f"{settings.GROQ_MODEL}-fallback",
            )


narrative_service = NarrativeService()
