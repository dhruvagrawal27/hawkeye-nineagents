"""HAWKEYE preflight — terminal verification suite (API-only).

Run inside the backend container:  python -m app.scripts.preflight_check
Exits 0 if all checks pass, 1 on any failure. Used by deploy.sh — a
failed preflight fails the deploy.

This script is intentionally light: it does NOT import scoring_service or
re-load LightGBM/SHAP. Those checks happen during the running uvicorn
lifespan; this script verifies them by hitting /readyz which exposes their
state. Keeping the preflight process small avoids OOM in resource-tight
containers (the running backend already has 700MB+ of model state loaded).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import httpx

BASE_URL = os.getenv("PREFLIGHT_BASE_URL", "http://localhost:8000")

CHECKS_PASSED: list[str] = []
CHECKS_FAILED: list[tuple[str, str]] = []


def ok(name: str) -> None:
    print(f"  OK   {name}", flush=True)
    CHECKS_PASSED.append(name)


def fail(name: str, reason: str) -> None:
    print(f"  FAIL {name}: {reason}", flush=True)
    CHECKS_FAILED.append((name, reason))


async def check_healthz(client: httpx.AsyncClient) -> None:
    try:
        r = await client.get(f"{BASE_URL}/healthz", timeout=5.0)
        if r.status_code == 200 and r.json().get("status") == "ok":
            ok("healthz")
        else:
            fail("healthz", f"status={r.status_code} body={r.text[:80]}")
    except Exception as exc:
        fail("healthz", str(exc))


async def check_readyz(client: httpx.AsyncClient) -> dict:
    try:
        r = await client.get(f"{BASE_URL}/readyz", timeout=10.0)
        body = r.json()
        services = body.get("services", {})
        down = [k for k, v in services.items() if v.get("status") == "down"]
        if down:
            fail("readyz", f"services down: {down}")
        else:
            ok(f"readyz_all_services ({len(services)} reachable)")
        return body
    except Exception as exc:
        fail("readyz", str(exc))
        return {}


async def check_models_loaded(readyz: dict) -> None:
    """The lifespan loaded scoring_service and asserted bootstrap. /readyz
    exposes the model version — its presence means the models loaded."""
    try:
        version = readyz.get("model_version") or ""
        threshold = readyz.get("threshold")
        if version and threshold and 0 < float(threshold) < 1:
            ok(f"models_loaded (version={version}, threshold={threshold:.4f})")
        else:
            fail("models_loaded", f"missing model_version/threshold in /readyz: {readyz}")
    except Exception as exc:
        fail("models_loaded", str(exc))


async def check_seeded_alerts(client: httpx.AsyncClient) -> int:
    try:
        r = await client.get(f"{BASE_URL}/internal/stats", timeout=5.0)
        n = int(r.json().get("alerts", 0))
        if n >= 10:
            ok(f"alerts_seeded ({n})")
        else:
            fail("alerts_seeded", f"only {n} alerts in DB, expected >=10")
        return n
    except Exception as exc:
        fail("alerts_seeded", str(exc))
        return 0


async def check_alerts_endpoint(client: httpx.AsyncClient) -> None:
    try:
        r = await client.get(f"{BASE_URL}/alerts?limit=5", timeout=10.0)
        if r.status_code != 200:
            fail("alerts_endpoint", f"status={r.status_code}")
            return
        items = r.json()
        if not isinstance(items, list) or len(items) == 0:
            fail("alerts_endpoint", f"unexpected payload (count={len(items) if isinstance(items, list) else 'n/a'})")
            return
        first = items[0]
        for required in ("id", "employee_id", "score", "display_score", "risk_level"):
            if required not in first:
                fail("alerts_endpoint", f"missing field {required}")
                return
        ok(f"alerts_endpoint (returned {len(items)})")
    except Exception as exc:
        fail("alerts_endpoint", str(exc))


async def check_employees_top(client: httpx.AsyncClient) -> None:
    try:
        r = await client.get(f"{BASE_URL}/employees/top?limit=5", timeout=10.0)
        if r.status_code == 200 and isinstance(r.json(), list):
            ok(f"employees_top ({len(r.json())})")
        else:
            fail("employees_top", f"status={r.status_code}")
    except Exception as exc:
        fail("employees_top", str(exc))


async def check_graph_endpoint(client: httpx.AsyncClient) -> None:
    try:
        r = await client.get(f"{BASE_URL}/graph?min_score=0.0&limit=20", timeout=10.0)
        if r.status_code == 200:
            body = r.json()
            n_nodes = len(body.get("nodes", []))
            ok(f"graph_endpoint (nodes={n_nodes})")
        else:
            fail("graph_endpoint", f"status={r.status_code}")
    except Exception as exc:
        fail("graph_endpoint", str(exc))


async def check_groq_narrative(client: httpx.AsyncClient) -> None:
    """Generate a narrative for an existing alert; verify Groq path or fallback."""
    try:
        r = await client.get(f"{BASE_URL}/alerts?limit=1", timeout=5.0)
        alerts = r.json()
        if not alerts:
            fail("groq_narrative", "no alerts to test against")
            return
        alert_id = alerts[0]["id"]
        rgen = await client.post(f"{BASE_URL}/narrative/{alert_id}/regenerate", timeout=60.0)
        if rgen.status_code != 200:
            fail("groq_narrative", f"regenerate returned {rgen.status_code}: {rgen.text[:120]}")
            return
        body = rgen.json()
        if "Audit trail" not in (body.get("body") or ""):
            fail("groq_narrative", "missing SHAP audit footer")
            return
        flag = " (fallback)" if body.get("is_fallback") else ""
        ok(f"groq_narrative (len={len(body['body'])}, latency={body.get('latency_ms', 0)}ms){flag}")
    except Exception as exc:
        fail("groq_narrative", str(exc))


async def check_websocket_broadcast(client: httpx.AsyncClient) -> None:
    try:
        import websockets

        async with websockets.connect("ws://localhost:8000/ws/alerts") as ws:
            await client.post(f"{BASE_URL}/internal/test-broadcast", timeout=5.0)
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                assert "type" in data
                ok("websocket_broadcast")
            except asyncio.TimeoutError:
                fail("websocket_broadcast", "no message received within 5s")
    except Exception as exc:
        fail("websocket_broadcast", str(exc))


async def check_replay_produces_alerts(client: httpx.AsyncClient) -> None:
    """Start replay → inject burst → poll until alert count rises.

    Robust to inject-burst slowness (large JSONL scan): the burst is fire-and-forget.
    Detects success based on the alert count growing past baseline within 90s.
    """
    try:
        # Make sure we start clean
        try:
            await client.post(f"{BASE_URL}/replay/stop", timeout=10.0)
        except Exception:
            pass
        await asyncio.sleep(1)

        r0 = await client.get(f"{BASE_URL}/internal/stats", timeout=10.0)
        baseline = int(r0.json().get("alerts", 0))

        rstart = await client.post(
            f"{BASE_URL}/replay/start",
            json={"mode": "mule_burst", "rate": 500},
            timeout=15.0,
        )
        if rstart.status_code != 200:
            fail("replay_produces_alerts", f"start returned {rstart.status_code}: {rstart.text[:120]}")
            return

        # Fire inject-burst with a generous timeout; we don't need to block on it.
        async def _inject():
            try:
                await client.post(f"{BASE_URL}/replay/inject-burst", timeout=120.0)
            except Exception as exc:
                print(f"      (inject-burst returned: {type(exc).__name__}: {exc})", flush=True)

        burst_task = asyncio.create_task(_inject())

        deadline = time.time() + 90
        new_alert_count = baseline
        while time.time() < deadline:
            await asyncio.sleep(3)
            try:
                r2 = await client.get(f"{BASE_URL}/internal/stats", timeout=10.0)
                new_alert_count = int(r2.json().get("alerts", 0))
            except Exception as exc:
                print(f"      (stats poll: {type(exc).__name__}: {exc})", flush=True)
                continue
            if new_alert_count > baseline:
                break

        # Best-effort cleanup
        try:
            await client.post(f"{BASE_URL}/replay/stop", timeout=10.0)
        except Exception:
            pass
        if not burst_task.done():
            burst_task.cancel()

        if new_alert_count > baseline:
            ok(f"replay_produces_alerts (baseline={baseline} -> {new_alert_count})")
        else:
            fail("replay_produces_alerts", f"alert count stayed at {baseline} for 90s")
    except Exception as exc:
        fail("replay_produces_alerts", f"{type(exc).__name__}: {exc}")


async def run_all() -> None:
    print("\n" + "=" * 60)
    print("  HAWKEYE PREFLIGHT CHECK")
    print("=" * 60 + "\n")

    async with httpx.AsyncClient() as client:
        await check_healthz(client)
        readyz = await check_readyz(client)
        await check_models_loaded(readyz)
        await check_seeded_alerts(client)
        await check_alerts_endpoint(client)
        await check_employees_top(client)
        await check_graph_endpoint(client)
        await check_groq_narrative(client)
        await check_websocket_broadcast(client)
        await check_replay_produces_alerts(client)

    print(f"\n{'=' * 60}")
    print(f"  PASSED: {len(CHECKS_PASSED)}    FAILED: {len(CHECKS_FAILED)}")
    if CHECKS_FAILED:
        print("\n  Failed checks:")
        for name, reason in CHECKS_FAILED:
            print(f"    - {name}: {reason}")
        print()
        sys.exit(1)
    else:
        print("\n  All checks passed. Safe to open the browser.\n")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_all())
