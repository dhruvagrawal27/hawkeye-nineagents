"""Keycloak JWT verification.

Strict by default; bypassed when PREFLIGHT_MODE=1 to let the preflight
script reach /alerts and /internal/* without a token. Never set in prod.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from fastapi import Header, HTTPException, status
from jose import jwt
from jose.exceptions import JWTError

from app.config import settings

log = structlog.get_logger(__name__)

_jwks_cache: dict[str, Any] | None = None


@dataclass(frozen=True)
class CurrentUser:
    sub: str
    username: str
    email: str | None
    roles: list[str]
    raw: dict[str, Any]


async def _fetch_jwks() -> dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    url = (
        f"{settings.KEYCLOAK_URL.rstrip('/')}/auth/realms/"
        f"{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        _jwks_cache = r.json()
    return _jwks_cache


def _bypass_user() -> CurrentUser:
    return CurrentUser(
        sub="preflight",
        username="preflight",
        email="preflight@hawkeye.local",
        roles=["analyst", "supervisor"],
        raw={"preauth": True},
    )


async def get_current_user(authorization: str | None = Header(None)) -> CurrentUser:
    if settings.is_preflight_mode:
        return _bypass_user()

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        jwks = await _fetch_jwks()
        # Find the right key by kid
        unverified = jwt.get_unverified_header(token)
        kid = unverified.get("kid")
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if key is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="unknown signing key")
        claims = jwt.decode(
            token,
            key,
            algorithms=[unverified.get("alg", "RS256")],
            audience=settings.KEYCLOAK_CLIENT_ID,
            options={"verify_aud": False},  # Keycloak puts clients in 'azp'
        )
    except JWTError as exc:
        log.warning("auth.token_invalid", error=str(exc))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc

    realm_roles = claims.get("realm_access", {}).get("roles", [])
    return CurrentUser(
        sub=claims.get("sub", "unknown"),
        username=claims.get("preferred_username", "unknown"),
        email=claims.get("email"),
        roles=realm_roles,
        raw=claims,
    )


def require_role(role: str):
    async def _checker(user: CurrentUser) -> CurrentUser:
        if role not in user.roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=f"requires role: {role}")
        return user

    return _checker
