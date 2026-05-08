# HAWKEYE — AI-Driven Early Warning System for Internal & Privileged User Fraud

> Continuously monitors the behaviour of internal and privileged users across
> banking systems (core banking, treasury, loan origination, customer databases)
> and flags anomalous or potentially fraudulent activities in real time.

Built by team **NINEAGENTS** — RBI NFPC Phase 2, Rank #4 nationally
(AUC 0.998 · F1 0.967 on 400M+ real transactions).

[GitHub](https://github.com/dhruvagrawal27/hawkeye-nineagents) ·
[ARCHITECTURE.md](ARCHITECTURE.md) · [DEMO.md](DEMO.md) · [DEPLOYMENT.md](DEPLOYMENT.md) ·
[QUICKSTART.md](QUICKSTART.md) · [CHANGELOG.md](CHANGELOG.md)

---

## What HAWKEYE actually monitors

The unit of monitoring is **the privileged user** (a bank employee with access to core banking,
treasury, loan origination, customer databases, etc.) — **not the customer**. Every event in
the stream is one action this user performed: a transaction they authorised, a customer record
they read, an account modification they made.

Two of those concepts share dual schema in the data — banking fields the model scores against,
and an insider-threat overlay the analyst sees:

| Banking field (model input) | Insider overlay (UI) | Why it matters |
|---|---|---|
| `account_id` | `employee_id` | Subject of monitoring |
| `counterparty_id` | `system_resource` | Which bank system was touched |
| `txn_type` (C/D) | `access_type` (READ/WRITE) | Read vs. modification |
| (n/a) | `records_accessed` | Bulk-download detector |
| `is_after_hours`, `is_weekend` | same | Off-hours signal |
| `amount` | same | Value at risk |

### The five signal families (verbatim from the problem statement)

| Family | Concrete features |
|---|---|
| **Unusual transaction patterns** | `pass_rate` (% of money flowing through), `ps45/ps49` (structuring at ₹45-49K), `fan_ratio` (credits-in / debits-out), `b_max_vol` (peak monthly INR), `g_top1` (top-counterparty share) |
| **Off-hours access** | `pngt` (off-hours fraction), `pwkd` (weekend fraction), `hrs` (active-hours coverage) |
| **Bulk data downloads** | `records_accessed` ≥ 50 per event (read or write); flagged with 📥 in the live tape |
| **Unauthorized account modifications** | `access_type=WRITE` to systems outside the user's normal access pattern; flagged with 🔓 + W tag |
| **Privilege escalation attempts** | Graph fan-out — sudden expansion in distinct `system_resource` set per user; surfaced via `g_ncp` (graph counterparty count) deviation from baseline |

Each detection produces a **risk score (0-1)** with a **risk band** (LOW / MEDIUM / HIGH / CRITICAL), an
**SHAP explanation** (the 5 features driving this score in plain English), an **LLM-generated
investigation memo** (Groq `gpt-oss-120b` with reasoning_effort=low + a deterministic Jinja fallback),
and a **graph neighbourhood view** (which other flagged users this person shares systems with).

---

## What's in this build (everything you can click on right now)

### Persistent **Top Status Bar**
Live IST clock · 5 service health dots (Postgres / Redis / Neo4j / Kafka / Groq) · KPI counters
(open alerts, 24h alerts, high-risk users, total events, EPS) · WebSocket live indicator · **Role
switcher chip** at the far right.

### Seven pages
| Path | Page | Lands here when role is | Notes |
|---|---|---|---|
| `/` | **Branch Command Center** | Manager | Mission callout, approval queue, dept rollup, 7d×24h heatmap, audit feed, live tape |
| `/dashboard` | **Dashboard** | Analyst / Supervisor | Stat cards, events/sec chart, score histogram, top movers, live alert tape |
| `/alerts` | **Alerts** | all roles | Filterable / sortable table, slide-over with SHAP + narrative, **bulk triage** for sup/mgr |
| `/employees` | **Privileged users** | all roles | Top-risk grid, dept filter, search, browse table |
| `/employees/:id` | **User detail** | all roles | Animated risk gauge, 4 tabs (Timeline, SHAP, Narrative, Audit) |
| `/graph` | **Graph Explorer** | all roles | D3 force-directed user↔system graph, dept clustering, search, score filter |
| `/replay` | **Replay Studio** | all roles | mule_burst replay, inject-burst, live counters, pause/resume tape |
| `/settings` | **Settings** | all roles | Model card (AUC/F1/threshold), system health, **roles & permissions matrix** |

### Live event tape (Bloomberg-style)
Every event consumed shows up as a colored row that flashes in and fades out:
- 🔴 critical alert · 🟠 high · 🟡 medium · 🟢 normal
- Columns: `USER · SYSTEM · A/T · RECS · AMOUNT · SCORE · SIGNAL · TIME`
- 📥 icon = bulk-download (records_accessed ≥ 50)
- 🔓 W = unauthorized-modification candidate (WRITE to off-pattern system on an alert)
- OFF-HRS tag = activity outside business hours

### Three roles, three personas

| | **Analyst** (Tier-1) | **Supervisor** (Tier-2) | **Branch Manager** |
|---|---|---|---|
| Read alerts, triage individually | ✓ | ✓ | ✓ |
| Escalate to supervisor | — | ✓ | ✓ |
| Approve / reject escalations | — | ✓ | ✓ |
| Bulk triage | — | ✓ | ✓ |
| Regenerate Groq narrative | — | ✓ | ✓ |
| Audit log access | — | ✓ | ✓ |
| Department rollup + Command Center landing | — | — | ✓ |

#### How to switch role (the answer to "where's supervisor / admin login?")

The top-right **role chip** in the status bar opens a dropdown with all three roles. Pick one —
the entire UI gates immediately (Manager sees Command Center, Analyst sees Dashboard, etc.).
Selection persists in localStorage.

In production the role is taken from the Keycloak JWT claim `realm_access.roles`. The switcher
is a demo-only override that runs when `PREFLIGHT_MODE=1` in the backend env.

#### Real Keycloak login (when you flip `PREFLIGHT_MODE=0` in `.env`)

Two users come pre-loaded from `infra/keycloak/realm-export.json`:

```
analyst@hawkeye.local    / analyst       (role: analyst)
supervisor@hawkeye.local / supervisor    (roles: analyst + supervisor)
```

To add a third **Manager** account in production, add a user to that realm export with the
`manager` realm role (1-line edit). The auth.py code already reads roles correctly.

---

## Quick start (local)

```bash
git clone https://github.com/dhruvagrawal27/hawkeye-nineagents
cd hawkeye-nineagents
cp .env.example .env
# fill GROQ_API_KEY (get one at console.groq.com — free tier is enough for the demo)
# leave PREFLIGHT_MODE=1 for local dev (auth bypassed; role switcher controls UI gating)

docker compose up -d                                       # 12 services, ~60-90s cold boot
docker compose exec backend alembic upgrade head           # schema
docker compose exec backend python -m app.scripts.seed     # 50 alerts + 10k Redis features + 50 graph nodes
docker compose exec backend python -m app.scripts.preflight_check    # 10 checks, must show "PASSED: 10  FAILED: 0"

# Open the dashboard
start http://localhost:8080
```

Want to see live alerts firing? Open http://localhost:8080/replay and click **▶ Start mule_burst**,
then **Inject mule burst** — alerts pop in within 10 seconds.

For deploying to Hetzner, see [QUICKSTART.md](QUICKSTART.md) §"Production deploy".

---

## Tech stack

- **Backend**: Python 3.11, FastAPI, async SQLAlchemy 2, Alembic, structlog
- **ML**: LightGBM (M1+M2 blended), SHAP TreeExplainer, 146 features, threshold 0.16032509
- **LLM**: Groq SDK, model `openai/gpt-oss-120b` with `reasoning_effort=low`, Jinja fallback
- **Streaming**: Apache Kafka, confluent-kafka-python
- **Graph**: Neo4j 5 (community), AsyncGraphDatabase
- **State**: Redis 7 (per-user feature snapshot + live deltas), Postgres 15
- **Auth**: Keycloak 23 OIDC + JWT
- **Frontend**: React 18, Vite, TypeScript, Tailwind, D3.js, Recharts, zustand, TanStack Query
- **Infra**: Docker Compose (12 services), host nginx + certbot at the edge

---

## Deployment

Full reference: [DEPLOYMENT.md](DEPLOYMENT.md). One-line summary: bootstrap a Hetzner CX33+
(8 GB RAM minimum), upload artifacts, point DNS, certbot, push to main → GitHub Actions
deploys via SSH.

The 4 GB CX23 box you have for `lajja-server` is **not enough** to also run HAWKEYE — buy a
CX33 (~€8/mo) for HAWKEYE alone. See [QUICKSTART.md](QUICKSTART.md) for sizing rationale.

---

## Compliance posture

HAWKEYE operates under a strict **human-in-the-loop** policy. All automated risk scores must be
reviewed by a human analyst before any operational action is taken. Every alert ships with a SHAP
factor breakdown and a model-generated investigation memo for auditability. Compliant with RBI
FREE-AI guidelines, ITV-2 SSO requirements, and the bank's internal model risk management framework.

---

## License

Internal — NINEAGENTS / RBI NFPC Phase 2. Not for redistribution.
