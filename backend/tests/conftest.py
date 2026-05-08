"""pytest fixtures."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("PREFLIGHT_MODE", "1")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    # Use sqlite for unit tests so we don't depend on Postgres
    monkeypatch.setenv("POSTGRES_URL", "sqlite+aiosqlite:///:memory:")
    yield
