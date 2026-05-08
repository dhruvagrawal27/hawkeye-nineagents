# HAWKEYE — Every Action Leaves a Trace

Real-time insider-fraud detection for Indian bank employees. AI scoring + LLM-assisted investigation memos + live behavioural-graph navigation.

Built by team **NINEAGENTS** (ranked #4 nationally in RBI NFPC Phase 2 — AUC 0.998 / F1 0.967 on 400M+ real transactions).

> ⚠️ **Demo system** — operates under a strict human-in-the-loop policy. All automated risk scores must be reviewed by an analyst before any action. Compliant with RBI FREE-AI guidelines.

## Live demo

| | |
|---|---|
| Public URL | https://hawkeye.nineagents.in |
| Test analyst login | `analyst@hawkeye.local` / `analyst` |
| Test supervisor login | `supervisor@hawkeye.local` / `supervisor` |
| Health check | https://hawkeye.nineagents.in/api/healthz |
| Readiness check | https://hawkeye.nineagents.in/api/readyz |

See [DEMO.md](DEMO.md) for a 5-minute walkthrough script for judges.

## Architecture

```
synthetic_events.jsonl
       │
       ▼
  Replay → Kafka(hawkeye.events) → Consumer
                                      │
                          Redis aggregator + Neo4j graph
                                      │
                          LightGBM M1+M2 blend → SHAP top-5
                                      │ score >= threshold
                              Groq narrative (openai/gpt-oss-120b)
                                      │
                          FastAPI REST + WebSocket
                                      │
                          React SPA (D3, shadcn/ui, Tailwind)
```

Detailed component breakdown in [ARCHITECTURE.md](ARCHITECTURE.md).

## Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2 (async), Alembic, structlog
- **ML**: LightGBM (full-data models), SHAP TreeExplainer
- **LLM**: Groq SDK, model `openai/gpt-oss-120b`
- **Streaming**: Apache Kafka, confluent-kafka-python
- **Graph**: Neo4j 5 community
- **State**: Redis 7, Postgres 15
- **Auth**: Keycloak 23 (OIDC + JWT)
- **Frontend**: TypeScript, React 18, Vite, Tailwind, shadcn/ui, D3.js, Recharts
- **Infra**: Docker Compose, host nginx + certbot, Hetzner VPS

## Quick start (local)

```bash
git clone https://github.com/dhruvagrawal27/hawkeye-nineagents
cd hawkeye-nineagents
cp .env.example .env                    # then edit GROQ_API_KEY at minimum
make up                                 # build + start full stack
make seed                               # alembic + populate alerts/Neo4j/Redis
make replay                             # mule_burst replay → alerts fire
open http://localhost:8080              # dashboard
```

`make up` waits for backend health (~60s on first boot). Subsequent boots are <15s. The dashboard never shows an empty state — `make seed` populates 50 pre-computed alerts on every boot.

## Quick start (production deploy)

See [DEPLOYMENT.md](DEPLOYMENT.md). Summary:

1. Provision a fresh Ubuntu 22.04 VPS (4 vCPU / 16 GB RAM minimum recommended).
2. Run `deploy/bootstrap-vps.sh` once on the host.
3. Point `hawkeye.nineagents.in` A-record at the VPS IP.
4. `certbot --nginx -d hawkeye.nineagents.in`.
5. Push to `main`. GitHub Actions runs `deploy/deploy.sh` over SSH. Site updates in <5 minutes.

## What good looks like (acceptance)

- `make up && make seed && make replay` — full stack running on a fresh laptop in <5 minutes.
- `make preflight` exits 0 with all 12 terminal checks passing.
- `make replay` — 3+ alerts in the DB within 60s of starting.
- Dashboard shows seeded alerts immediately on login.
- "Inject Mule Burst" button on Replay Studio → 3+ alerts within 10 seconds.
- LLM narrative generated within 30 seconds, includes SHAP audit footer.
- Graph Explorer renders, "Collusion clusters" highlights detected groups.

## Future work (out of scope for this build)

- T-HGNN training (temporal heterogeneous graph network).
- Federated learning (per-bank training without data centralization).
- SimCLR contrastive pre-training for behavioural embeddings.
- Multi-region active-active failover.
- Vault / HashiCorp Vault secret management.
- mTLS between internal services.

## License

Internal — NINEAGENTS / RBI NFPC Phase 2. Not for redistribution.

## Team

**NINEAGENTS** — RBI NFPC Phase 2, Rank #4 nationally.
