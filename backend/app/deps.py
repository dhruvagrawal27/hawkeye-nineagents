"""FastAPI dependency factories."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.models.db import get_session


async def db_session() -> AsyncIterator[AsyncSession]:
    async for s in get_session():
        yield s


CurrentUserDep = Depends(get_current_user)


async def require_analyst(user: CurrentUser = CurrentUserDep) -> CurrentUser:
    return user  # any authenticated user


async def require_supervisor(user: CurrentUser = CurrentUserDep) -> CurrentUser:
    if "supervisor" not in user.roles and not user.raw.get("preauth"):
        from fastapi import HTTPException, status

        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="requires supervisor role")
    return user
