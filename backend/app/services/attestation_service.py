"""TEE attestation cache for the NEAR AI Cloud LLM gateway.

NEAR AI Cloud exposes a `/v1/attestation/report` endpoint that returns the
Intel TDX quote + the signing key used to authenticate every inference
response. We fetch it once at startup, cache the signing address + a
fingerprint of the Intel quote, and surface them on `/readyz` and per-alert
so the panel can independently verify the confidential-compute claim.

This service is a no-op when LLM_PROVIDER != 'nearai'.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


@dataclass
class AttestationSnapshot:
    """The data we care about from NEAR AI Cloud's TEE attestation report."""

    signing_address: str | None = None
    signing_algo: str | None = None
    intel_quote_sha256: str | None = None
    intel_quote_prefix: str | None = None  # first 32 hex chars for display
    intel_quote_bytes: int = 0
    fetched_at: str | None = None
    fetch_ok: bool = False
    error: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signing_address": self.signing_address,
            "signing_algo": self.signing_algo,
            "intel_quote_sha256": self.intel_quote_sha256,
            "intel_quote_prefix": self.intel_quote_prefix,
            "intel_quote_bytes": self.intel_quote_bytes,
            "fetched_at": self.fetched_at,
            "fetch_ok": self.fetch_ok,
            "error": self.error,
        }


class AttestationService:
    """Singleton — main.py lifespan calls .refresh() once after boot."""

    def __init__(self) -> None:
        self.snapshot: AttestationSnapshot = AttestationSnapshot()

    @property
    def is_attested(self) -> bool:
        """True when we hold a valid TEE attestation report from NEAR AI Cloud."""
        s = self.snapshot
        return bool(
            s.fetch_ok
            and s.signing_address
            and s.intel_quote_sha256
            and s.intel_quote_bytes > 0
        )

    async def refresh(self) -> AttestationSnapshot:
        """Pull the latest attestation report from the configured NEAR AI base URL.
        Safe to call repeatedly — never raises.
        """
        from datetime import UTC, datetime

        if settings.LLM_PROVIDER != "nearai":
            self.snapshot = AttestationSnapshot(
                fetch_ok=False,
                error="LLM_PROVIDER != 'nearai' — attestation disabled",
            )
            return self.snapshot

        if not settings.NEAR_AI_API_KEY:
            self.snapshot = AttestationSnapshot(
                fetch_ok=False,
                error="NEAR_AI_API_KEY not set",
            )
            return self.snapshot

        url = f"{settings.NEAR_AI_BASE_URL}/attestation/report"
        headers = {"Authorization": f"Bearer {settings.NEAR_AI_API_KEY}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            log.warning("attestation.fetch_failed", extra={"url": url, "error": str(exc)})
            self.snapshot = AttestationSnapshot(
                fetch_ok=False, error=f"{type(exc).__name__}: {exc}"
            )
            return self.snapshot

        gw = body.get("gateway_attestation") or {}
        quote_hex = gw.get("intel_quote") or ""
        # The quote is a hex-encoded Intel TDX evidence blob (~5KB).
        # Display a sha256 + 32-char prefix so the UI can show a verifiable
        # fingerprint without bloating the payload.
        try:
            quote_bytes_raw = bytes.fromhex(quote_hex) if quote_hex else b""
        except ValueError:
            quote_bytes_raw = quote_hex.encode("utf-8")
        quote_sha = hashlib.sha256(quote_bytes_raw).hexdigest() if quote_bytes_raw else None

        self.snapshot = AttestationSnapshot(
            signing_address=gw.get("signing_address"),
            signing_algo=gw.get("signing_algo"),
            intel_quote_sha256=quote_sha,
            intel_quote_prefix=quote_hex[:32] if quote_hex else None,
            intel_quote_bytes=len(quote_bytes_raw),
            fetched_at=datetime.now(UTC).isoformat(),
            fetch_ok=True,
        )
        log.info(
            "attestation.refreshed",
            extra={
                "signing_address": self.snapshot.signing_address[:16] + "..."
                if self.snapshot.signing_address
                else None,
                "quote_bytes": self.snapshot.intel_quote_bytes,
                "quote_sha256": (self.snapshot.intel_quote_sha256 or "")[:16] + "...",
            },
        )
        return self.snapshot


attestation_service = AttestationService()
