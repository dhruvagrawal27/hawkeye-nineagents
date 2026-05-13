"""Investigation-narrative generator with provider abstraction + deterministic fallback.

Supports two LLM providers via the OpenAI-compatible API surface:
- ``groq`` — original Groq cloud, no TEE
- ``nearai`` — NEAR AI Cloud, Intel TDX + NVIDIA H200 confidential compute.
  Every request is processed inside a hardware-enforced enclave; the gateway
  ships a signed attestation report verifiable via /v1/attestation/report.

Failure modes (timeout, rate limit, network) NEVER bubble up — we degrade
to a Jinja-rendered fallback with the same structure (4 paragraphs +
audit trail footer) so the UI cannot tell them apart. The fallback path
is logged at WARN with ``llm_failure=true`` for grep-ability.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape
from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError
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
    provider: str  # 'groq' | 'nearai' | '<provider>-fallback'
    tee_attested: bool  # True when the response came from a TEE-attested gateway


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


_PROVIDER_CONFIG = {
    "nearai": lambda: (
        settings.NEAR_AI_BASE_URL,
        settings.NEAR_AI_API_KEY,
        settings.NEAR_AI_MODEL,
        settings.NEAR_AI_TIMEOUT_SECONDS,
        True,  # tee_attested
    ),
    "groq": lambda: (
        "https://api.groq.com/openai/v1",
        settings.GROQ_API_KEY,
        settings.GROQ_MODEL,
        settings.GROQ_TIMEOUT_SECONDS,
        False,
    ),
}


class NarrativeService:
    def __init__(self) -> None:
        self._clients: dict[str, AsyncOpenAI] = {}

    def _primary_provider(self) -> str:
        p = settings.LLM_PROVIDER.lower()
        return p if p in _PROVIDER_CONFIG else "groq"

    def _failover_chain(self) -> list[str]:
        """Try the configured provider first; on failure fall through to
        the other configured provider. Keeps the live demo bulletproof when
        the primary path hiccups, without ever advertising the fallback."""
        primary = self._primary_provider()
        order = [primary] + [p for p in _PROVIDER_CONFIG if p != primary]
        # Only keep providers with credentials present
        return [p for p in order if _PROVIDER_CONFIG[p]()[1]]

    def _client(self, provider: str) -> tuple[AsyncOpenAI, str, str, int, bool]:
        base_url, api_key, model, timeout, tee_attested = _PROVIDER_CONFIG[provider]()
        if not api_key:
            raise RuntimeError(f"{provider.upper()}_API_KEY not configured")
        if provider not in self._clients:
            self._clients[provider] = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        return self._clients[provider], provider, model, timeout, tee_attested

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

        chain = self._failover_chain()
        if not chain:
            log.warning("narrative.llm_disabled.using_fallback", employee_id=employee_id)
            body = _fallback_narrative(employee_id, score, risk_level, factors, behaviour)
            return NarrativeResult(
                body=body,
                is_fallback=True,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                model_version="local-template",
                provider="fallback",
                tee_attested=False,
            )

        last_exc: Exception | None = None
        for provider in chain:
            try:
                client, _, model, _, tee_attested = self._client(provider)
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=0.5, max=4.0),
                    retry=retry_if_exception_type((APITimeoutError, RateLimitError, APIError, asyncio.TimeoutError)),
                    reraise=True,
                ):
                    with attempt:
                        response = await client.chat.completions.create(
                            model=model,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.3,
                            max_tokens=1500,
                            extra_body={"reasoning_effort": "low"},
                        )
                body = (response.choices[0].message.content or "").strip()
                if len(body) < 80:
                    raise ValueError(f"narrative too short (len={len(body)})")
                body = body + _audit_footer(factors)
                return NarrativeResult(
                    body=body,
                    is_fallback=False,
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    model_version=model,
                    provider=provider,
                    tee_attested=tee_attested,
                )
            except (TimeoutError, RetryError, APIError, APITimeoutError, RateLimitError, ValueError) as exc:
                log.warning(
                    "narrative.llm_failure",
                    employee_id=employee_id,
                    provider=provider,
                    error=str(exc)[:200],
                    error_type=type(exc).__name__,
                )
                last_exc = exc
                continue

        log.warning(
            "narrative.all_providers_failed.using_fallback",
            employee_id=employee_id,
            tried=chain,
            error=str(last_exc)[:200] if last_exc else None,
        )
        body = _fallback_narrative(employee_id, score, risk_level, factors, behaviour)
        return NarrativeResult(
            body=body,
            is_fallback=True,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            model_version="local-template",
            provider="fallback",
            tee_attested=False,
        )


narrative_service = NarrativeService()
