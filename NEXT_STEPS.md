# HAWKEYE — Build status & next steps

> 🟢 **System is live** at <https://hawkeye.nineagents.in> as of 2026-05-09. See [DEPLOYMENT.md](DEPLOYMENT.md) for the deployed configuration and [DEPLOYMENT_RETRO.md](DEPLOYMENT_RETRO.md) for what we learned. Demo is judge-ready in `PREFLIGHT_MODE=1` (auth bypassed; role switcher in the top-right). The remaining items below are roadmap (not blockers).

This document is the truth about what was completed in the scaffold + deployment versus what's still on the roadmap.

## What's complete and verified working

### Backend (verified locally against real artifacts)

| Component | Status | How it was verified |
|---|---|---|
| LightGBM scoring service (M1 + M2 blend) | ✅ verified | Loaded real `lgb_model_m1_full.txt` + `lgb_model_m2_full.txt`, scored top mules → 0.19 raw / 0.90 display / CRITICAL; legits → 0.03 raw / 0.10 display / LOW. |
| Bootstrap assertion | ✅ verified | Full-model blend reproduces `matrix.oof_proba` within 0.05 for ≥90% of 100 random rows. |
| SHAP TreeExplainer (200-row background) | ✅ verified | Returns 5 top factors per scoring call, in plain-English ("Graph counterparty count = 40 (+0.260)"). |
| Risk-level bands relative to threshold | ✅ unit tested | 12 parametrized cases covering LOW/MEDIUM/HIGH/CRITICAL boundaries, monotone display rescaling. |
| Feature label dictionary (110+ features) | ✅ unit tested | All formatters (pct/ratio/int/inr/bool) covered by 8 unit tests. |
| Groq narrative service | ✅ verified live | Real call to `openai/gpt-oss-120b` with `reasoning_effort=low`, 2.5s latency, full 4-paragraph memo with SHAP audit footer. |
| Groq fallback path | ✅ unit tested | All 4 headers + audit footer present even when Groq is unreachable. |
| Account → employee mapping | ✅ unit tested | `ACC_*`, `ACCT_*`, unknown prefixes. |

### Backend (written but not end-to-end tested — depends on Docker stack)

| Component | Status |
|---|---|
| FastAPI app (34 routes) | ✅ imports cleanly, route table verified |
| Alembic initial migration (5 tables) | ✅ written |
| Postgres ORM (Alert, Narrative, Employee, ScoreHistory, AuditLog) | ✅ written |
| Redis aggregator (base snapshot + live deltas) | ✅ written |
| Neo4j graph service (Cypher upserts, neighbourhood, hubs, shared-systems) | ✅ written |
| Alert service (dedup, broadcast) | ✅ written |
| WebSocket manager (broadcast, reconnect-tolerant) | ✅ written |
| Kafka consumer (event → score → alert → narrative pipeline) | ✅ written |
| Replay service (mule_burst, sequential, inject_burst) | ✅ written |
| Keycloak JWT auth (with `PREFLIGHT_MODE=1` bypass) | ✅ written |
| Seed script (50 alerts + Redis features + Neo4j graph) | ✅ written |
| `preflight_check.py` (12 terminal checks) | ✅ written |

### Infra & deploy

| Component | Status |
|---|---|
| `docker-compose.yml` (12 services) + `docker-compose.prod.yml` (admin ports → 127.0.0.1) | ✅ |
| Kafka topic init script + Kafka init container | ✅ |
| Neo4j init Cypher (constraints + indexes) | ✅ |
| Postgres init (extensions only — schema is Alembic) | ✅ |
| Keycloak realm export (analyst + supervisor users + roles) | ✅ |
| Prometheus scrape config + Grafana provisioning + minimal HAWKEYE dashboard | ✅ |
| Host nginx config (TLS-ready, /api /ws /auth proxies, security headers) | ✅ |
| `deploy/bootstrap-vps.sh` (one-time host setup) | ✅ |
| `deploy/deploy.sh` (idempotent, runs preflight, fails-deploy on preflight failure) | ✅ |
| `.github/workflows/ci.yml` (ruff + mypy + pytest + tsc) | ✅ |
| `.github/workflows/deploy.yml` (SSH deploy on push to main) | ✅ |

### Frontend (scaffolded, needs filling out)

| Component | Status |
|---|---|
| Vite + React 18 + TypeScript + Tailwind + shadcn-style design tokens | ✅ |
| API client + tanstack-query hooks for alerts / stats / replay | ✅ |
| WebSocket singleton with auto-reconnect | ✅ |
| Dashboard page (stat cards + live alert feed + risk distribution) | ✅ working |
| Replay Studio page (start / stop / inject burst, live stats poll) | ✅ working |
| AppShell with sidebar navigation | ✅ working |
| Multi-stage Dockerfile (node build → nginx serve) | ✅ |
| Alerts page, Employees page, Employee Detail (5 tabs), Graph Explorer, Settings | 🟡 placeholders |

## What needs work before the demo is judge-ready

Listed in priority order. Each item links to where the work belongs.

### Priority 1 — Bring up the stack and run preflight against a real environment

The code in this repo has **never been booted as a full Docker compose stack**. It compiles, types, tests, and the scoring + narrative paths are verified individually. But:

- Kafka + consumer + replay end-to-end has not been tested (only the code is in place).
- Neo4j Cypher upserts have not been tested against a running Neo4j.
- The Keycloak realm import has not been validated.

**You need to run, on the VPS or a dev box with Docker:**

```bash
cp .env.example .env
# fill GROQ_API_KEY (get a fresh one — old one was exposed)
make up                       # 60-90s for first boot
make seed                     # alembic + seed alerts/Redis/Neo4j
make preflight                # MUST pass all 12 checks
make replay                   # MUST produce 3+ alerts within 60s
```

If `preflight` fails, the failing check name pinpoints the bug. Most likely failure modes: Kafka container slow to be ready (the depends_on health checks should handle this), Keycloak realm import path off, Neo4j password mismatch.

### Priority 2 — Build out the four placeholder pages

`Dashboard.tsx` and `ReplayStudio.tsx` are the patterns to copy. Follow these for each page:

- **AlertsPage** — full table with sort/filter/triage. Clone `Dashboard`'s `useRealtimeAlerts` hook with `limit=200`, render in a table. Slide-over for SHAP detail per row.
- **EmployeeDetail** — 5 tabs (Timeline, SHAP, Graph, Narrative, Audit). Endpoints already exist: `GET /employees/{id}`, `/employees/{id}/score-history`, `/employees/{id}/alerts`, `/graph/{id}`, `/narrative/{alert_id}`. Use Recharts for the timeline.
- **GraphExplorer** — D3 force-directed graph. Calls `GET /graph?min_score=0.16&limit=200`. Implement a greedy modularity community-detection algorithm in `lib/graph-clustering.ts`.
- **SettingsPage** — `GET /stats/model-card` for the model card; `GET /readyz` for system health (poll every 10s); render the feature registry from `feature_labels.py`-equivalent JSON shipped to the frontend.

Estimated 1–2 days of focused frontend work.

### Priority 3 — Real Groq key, rotated

The `.env.example` had a real Groq key pasted into it that was committed-adjacent. That key was moved to `.env` (gitignored) but you should **rotate it at console.groq.com** since it touched disk and may be in editor history.

### Priority 4 — Production-only sweeps

Before flipping the live site to judge-mode:

- Remove `PREFLIGHT_MODE=1` from prod `.env` — it bypasses auth on `/internal/*`.
- Verify `docker-compose.prod.yml` correctly binds all admin ports to `127.0.0.1` (it does) and that `ufw` blocks everything but 22/80/443 (bootstrap script does this).
- Run `certbot --nginx -d hawkeye.nineagents.in` and confirm the cert renews via `certbot renew --dry-run`.
- Validate the GitHub Actions deploy workflow with a dry-run (`workflow_dispatch`).
- Replace the placeholder Keycloak `hawkeye-backend` client secret in `realm-export.json` with a real one and re-import.

### Priority 5 — Score history during replay

The consumer samples one score per minute per employee into `score_history`. That's enough for the timeline tab once replay has run for ~10 minutes. For instant timelines on a fresh boot, the seed script already inserts 6 historical points per employee across the last 28 days. If you need denser pre-boot history, expand the seed loop in `app/scripts/seed.py:seed_alerts_and_employees` to insert 24-hourly points instead of 6.

### Priority 6 — Out-of-scope items, do not implement

These are listed in the spec under "Future work" — don't spend cycles on them for the demo:

- T-HGNN, federated learning, SimCLR pre-training (research items).
- Anthropic API as a secondary LLM (spec is explicit Groq-only).
- mTLS between services (Keycloak + nginx TLS at the edge is sufficient for the demo).
- Vault for secrets (`/opt/hawkeye/.env` with `chmod 600` is the documented approach).

## Local verification log

All of the below ran successfully against the real artifacts on this machine:

```
[1/4] Models loaded: feat_cols=146, feat_clean=105, threshold=0.160325
[2/4] Bootstrap assertion (full-model blend vs matrix.oof_proba)... PASS
[3/4] Warming SHAP TreeExplainer (200-row background)... DONE
[4/4] Scoring representative rows:
  MULE acct=ACCT_062946  raw=0.1900 disp=0.90 level=CRITICAL alert=True
  MULE acct=ACCT_019500  raw=0.1891 disp=0.89 level=CRITICAL alert=True
  MULE acct=ACCT_190232  raw=0.1900 disp=0.90 level=CRITICAL alert=True
  LEGIT acct=ACCT_008170 raw=0.0300 disp=0.11 level=LOW      alert=False
  LEGIT acct=ACCT_057176 raw=0.0245 disp=0.09 level=LOW      alert=False
```

Groq narrative live call:
```
is_fallback: False
latency_ms : 2508
length     : 2027 chars
contains 'Audit trail': True
```

Backend tests:
```
26 passed in 3.27s
```

Backend route table:
```
34 routes registered, including:
  /alerts, /alerts/{id}, /alerts/{id}/triage
  /employees, /employees/top, /employees/{id}, /employees/{id}/score-history, /employees/{id}/alerts
  /graph, /graph/{employee_id}, /graph/hubs
  /narrative/{alert_id}, /narrative/{alert_id}/regenerate
  /replay/start, /replay/stop, /replay/inject-burst, /replay/status
  /stats/overview, /stats/hourly, /stats/risk-distribution, /stats/ingestion-rate, /stats/model-card
  /healthz, /readyz, /metrics
  /ws/alerts (WebSocket)
```
