# HAWKEYE — Architecture

This document explains the data flow, data-model decisions, and critical design choices. Read this before modifying anything in `backend/app/services/` or `backend/app/consumers/`.

## High-level flow

```
synthetic_events.jsonl
       │
       ▼
┌────────────────┐    ┌──────────────────────────────────────────────┐
│ Replay service │───►│  Kafka  (hawkeye.events)                    │
└────────────────┘    └──────────────┬───────────────────────────────┘
                                     │
                  ┌──────────────────▼──────────────────┐
                  │  Event consumer (FastAPI bg task)    │
                  └──────┬───────────────────────┬──────┘
                         │                       │
                  ┌──────▼──────┐         ┌──────▼──────┐
                  │ Redis        │         │ Neo4j        │
                  │ rolling-window│         │ employee→sys │
                  │ deltas        │         │ live graph   │
                  └──────┬───────┘         └──────┬──────┘
                         │                        │
                  ┌──────▼────────────────────────▼──────┐
                  │  Scoring service                     │
                  │    LightGBM M1+M2 blend (88%)        │
                  │  + T-HGNN graph proba    (8%)        │
                  │  + SimCLR cold-start     (4%)        │
                  │  + SHAP top-5 explanation             │
                  └──────────────┬───────────────────────┘
                                 │ score >= threshold
                  ┌──────────────▼───────────────────────┐
                  │  Narrative service                    │
                  │    openai/gpt-oss-120b inside         │
                  │    Intel TDX + NVIDIA H200 TEE        │
                  │    (NEAR AI Cloud, per-req attest)    │
                  │    + silent failover + Jinja          │
                  └──────────────┬───────────────────────┘
                                 │
                  ┌──────────────▼───────────────────────┐
                  │  FastAPI REST + WebSocket             │
                  └──────────────┬───────────────────────┘
                                 │
                  ┌──────────────▼───────────────────────┐
                  │  React SPA (Vite + Tailwind)          │
                  └───────────────────────────────────────┘
```

## Why this works (and the choices that shape it)

### 1. Two datasets, deterministic mapping

The `account_feature_matrix.parquet` (160k accounts, 146 features per row) is the *real* RBI NFPC Phase 2 data — the source of model truth. The `synthetic_events.jsonl` (516k events, 10k synthetic accounts) is the demo replay stream. The two have different account-id namespaces (`ACCT_*` vs `ACC_*`).

**Decision**: at seed time, every synthetic account-id is deterministically hashed into a real account-id from the matrix, with `is_mule` parity preserved (synthetic mules → real mules, synthetic legits → real legits). This pre-loaded base feature row lives in Redis at `account:{id}:features`. When events stream in, the consumer fetches the base row, applies a small set of live deltas (counters: `n`, `pngt`, `ps49`, fan ratios), and scores. The model sees real-data feature distributions; the demo gets a live-feel stream.

### 2. Score range is tight, so risk levels are relative

Empirically, the full-data LightGBM blend produces scores in `[0.026, 0.190]` even on known mules. The trained threshold is `0.16032509`. The "score=0.95 CRITICAL" examples in the spec are aspirational — real outputs cluster near the decision boundary.

**Decision**: store the raw blended score for ML correctness, *and* compute a `display_score` rescaled into `[0.0, 1.0]` for UI readability. Risk levels are bands relative to the threshold:

| Band | Raw score | Display | Risk level |
|---|---|---|---|
| Below | `score < threshold * 0.5` | < 0.30 | LOW |
| Watch | `threshold * 0.5 ≤ score < threshold` | 0.30–0.50 | LOW |
| Alert | `threshold ≤ score < threshold + 0.01` | 0.50–0.70 | MEDIUM |
| High | `threshold + 0.01 ≤ score < threshold + 0.02` | 0.70–0.85 | HIGH |
| Critical | `score ≥ threshold + 0.02` | 0.85–1.00 | CRITICAL |

Constants in `backend/app/services/risk_levels.py` — single source of truth.

### 3. Bootstrap assertion compares to `matrix.oof_proba`, not OOF predictions

The spec told us to compare loaded-model output against `oof_predictions.parquet` within ±0.05. This cannot work — OOF predictions come from K-fold CV (each row predicted by a fold model that didn't see it), but the persisted models are full-data models. They are *different distributions*.

**Decision**: `account_feature_matrix.parquet` includes a column `oof_proba` which IS the full-model holdout prediction. Loaded-model blend reproduces this within mean delta ≈ 0.009, p95 ≈ 0.020. Bootstrap assertion compares to this column. Documented in `backend/app/services/scoring.py`.

### 4. Three guarantees that the dashboard is never empty

| Layer | Mechanism |
|---|---|
| **Boot** | `seed.py` inserts 50 alerts from the top-50 mules in `account_feature_matrix.parquet` if the alerts table has <10 rows. Every boot, no exceptions. |
| **Replay** | The default replay mode (`mule_burst`) injects events from the top-10 mule accounts *first*, before the general stream, guaranteeing alerts within 30–60s. |
| **Preflight** | `preflight_check.py` directly creates a test alert + generates a TEE-attested narrative + reads it back. If any link in the chain fails, the deploy fails. |

### 5. Alert deduplication

Without dedup, a sustained stream of mule events would produce thousands of alerts for the same employee. Rule (in `services/alert_service.py`):

> Do not create a new alert for the same `employee_id` within the last `ALERT_DEDUP_WINDOW_MINUTES` (default 60) UNLESS the new score is at least `ALERT_DEDUP_DELTA` (default 0.05) higher than the existing open alert.

When a new event raises an existing alert's score, we update the alert in place (touch `last_seen_at`, replace `score` if new is higher) instead of creating a duplicate.

### 6. Insider-threat translation in the API layer only

The model knows `account_id`, `counterparty_id`, `ip_address`. The dashboard speaks `employee_id`, `system_resource`, `workstation`. Translation happens in `app/api/*.py` response builders:

- `account_id` → `employee_id` (replace `ACC_` / `ACCT_` prefix with `EMP_`)
- `counterparty_id` → `system_resource` (replace `CP_` prefix with `SYS_`)

The internal services NEVER see the remapped values. This keeps the model contract clean and lets us re-skin the demo for other contexts.

### 7. LLM failure must never surface to the UI

The investigation memo is generated through a provider chain:

1. **Primary** (when `LLM_PROVIDER=nearai`): `openai/gpt-oss-120b` on NEAR AI Cloud's Intel TDX + NVIDIA H200 GPU confidential compute gateway. Per-request TDX attestation cached by `attestation_service`.
2. **Silent failover**: if the primary call fails (timeout, rate limit, network), `narrative_service` transparently retries against any other configured provider (e.g. a Groq key set in `.env`). Failover is logged at WARN but invisible in the UI.
3. **Final fallback**: if all providers fail, a Jinja-rendered template renders the same 4-paragraph + audit-footer structure using the SHAP factors. Structurally identical so the UI cannot tell the difference.

Every saved narrative records `provider` and `tee_attested` columns so auditors can verify per-alert which path produced it. `tenacity` wraps each provider call with 3 retries + exponential backoff. Failure is grepped via `llm_failure=true` in structlog.

### 8. Models loaded once at startup

`ScoringService` is a module-level singleton instantiated in `app/main.py` lifespan. LightGBM boosters and SHAP TreeExplainer (with a 200-row background sampled from `account_feature_matrix.parquet`) are loaded exactly once. Per-request scoring is just a vector lookup + matrix multiply — sub-millisecond.

## Postgres schema (key tables)

| Table | Purpose |
|---|---|
| `alerts` | One row per de-duplicated alert. Indexes on `employee_id`, `triggered_at desc`, `status`. |
| `narratives` | One row per generated narrative. FK → `alerts.id`. Stores `model_version`, `generated_at`, `is_fallback`. |
| `employees` | Synthetic employee directory (id, name, department, joining date). Populated at seed. |
| `score_history` | Time-series of scores per employee (sampled hourly during replay). Used for the timeline tab. |
| `audit_log` | Every triage action (dismiss / investigate / escalate). FK → `alerts.id`. |

## Neo4j schema

Nodes:
- `Employee {id, risk_score, risk_level, department, last_seen_at}`
- `System {id, kind, access_count}`

Relationships:
- `(Employee)-[:ACCESSED {count, last_at}]->(System)`

Updated incrementally by the consumer on every event:
```cypher
MERGE (e:Employee {id: $emp})
MERGE (s:System {id: $sys})
MERGE (e)-[r:ACCESSED]->(s)
ON CREATE SET r.count = 1, r.last_at = $ts
ON MATCH SET r.count = r.count + 1, r.last_at = $ts
```

## Redis keyspace

| Key | Type | TTL | Purpose |
|---|---|---|---|
| `account:{id}:features` | Hash | none | Pre-loaded base feature row from matrix. |
| `account:{id}:deltas` | Hash | 24h | Live counters updated by consumer (n, pngt, ps49, hrs, etc.) |
| `account:{id}:lastscore` | String | 1h | Last computed score (for replay studio's mini-histogram) |
| `replay:status` | String | none | "idle" / "running" / "paused" |
| `replay:stats` | Hash | none | events_published, alerts_fired, started_at, rate |
| `dedup:alert:{emp_id}` | Hash | 1h | Existing open alert id + score for dedup logic |

## Kafka topics

| Topic | Partitions | Retention | Producer | Consumers |
|---|---|---|---|---|
| `hawkeye.events` | 3 | 24h | replay_service | event_consumer (group `hawkeye-scorer`) |

## Threat model & security boundaries

- All admin ports (5432 Postgres, 7474/7687 Neo4j, 9090 Prometheus, 3000 Grafana, 9001 MinIO console, 8081 Keycloak admin) bind to `127.0.0.1` in `docker-compose.prod.yml`. Only ports `80` and `443` are publicly reachable, served by host nginx with TLS.
- JWT verification on every API request except `/healthz`, `/readyz`, `/metrics`, and (when `PREFLIGHT_MODE=1`) `/internal/*`.
- NEAR AI API key, Groq API key (fallback), Postgres password, Keycloak admin password, MinIO secret all loaded from `/opt/hawkeye/.env` (`chmod 600`, owner-only). Never logged. Structlog redacts any field matching `*_key`, `*_secret`, `*_password`.
- CSP and security headers (X-Frame-Options DENY, X-Content-Type-Options nosniff, HSTS) set by host nginx.
