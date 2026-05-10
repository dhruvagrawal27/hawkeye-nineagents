# HAWKEYE — AI-Driven Early Warning System for Internal & Privileged User Fraud

> Continuously monitors the behaviour of internal and privileged users across
> banking systems (core banking, treasury, loan origination, customer databases)
> and flags anomalous or potentially fraudulent activities in real time.

Built by team **NINEAGENTS** — RBI NFPC Phase 2, Rank #4 nationally
(AUC 0.998 · F1 0.967 on 400M+ real transactions).

---

## 📸 Screenshots

> **Note for evaluators**: Screenshot files are in [`docs/screenshots/`](docs/screenshots/). If they appear broken below, open the [live demo](https://hawkeye.nineagents.in) directly — it's faster than waiting for these to load anyway.

<table>
<tr>
<td width="50%"><b>Branch Manager Command Center</b><br/>
<img src="docs/screenshots/01-command-center-hero.png" alt="Command Center: KPI strip, events/sec chart, score histogram, approval queue, dept rollup, audit feed" />
<sub>Top stat strip · events/sec chart · approval queue · department rollup · 7d×24h heatmap · live audit feed</sub>
</td>
<td width="50%"><b>Live event tape (Bloomberg-style)</b><br/>
<img src="docs/screenshots/03-live-event-tape.png" alt="Live event tape mid-replay with coloured rows" />
<sub>Every privileged-user action scored in real-time. Rows colour-flash by risk level. ⚠ alert · 📥 bulk-download · 🔓 unauthorized write</sub>
</td>
</tr>
<tr>
<td width="50%"><b>SHAP factor breakdown</b><br/>
<img src="docs/screenshots/04-employee-detail-shap.png" alt="SHAP waterfall on Employee Detail" />
<sub>Top 5 model factors driving this employee's score, with red/green contribution bars</sub>
</td>
<td width="50%"><b>LLM investigation memo</b><br/>
<img src="docs/screenshots/05-narrative-memo.png" alt="Groq narrative memo with audit trail" />
<sub>Groq <code>gpt-oss-120b</code> generated 4-paragraph memo + audit trail footer. Plain-English first, technical detail second.</sub>
</td>
</tr>
<tr>
<td width="50%"><b>Graph Explorer with department clustering</b><br/>
<img src="docs/screenshots/06-graph-explorer-clusters.png" alt="D3 force-directed graph with 5 dept clusters" />
<sub>D3 force layout. 5 departments arranged in a pentagon. Same-dept users cluster spatially.</sub>
</td>
<td width="50%"><b>Roles & permissions matrix</b><br/>
<img src="docs/screenshots/08-settings-roles-matrix.png" alt="Roles capability matrix on Settings page" />
<sub>Three roles, capability-gated UI. Click any column header to switch role.</sub>
</td>
</tr>
</table>

---

## 🚀 Live demo

| | |
|---|---|
| **Open the dashboard** | **<https://hawkeye.nineagents.in>** |
| API root | <https://hawkeye.nineagents.in/api/docs> |
| Health check | <https://hawkeye.nineagents.in/api/healthz> |
| Hosting | Hetzner Cloud · CX33 (4 vCPU / 8 GB / 80 GB SSD) · Helsinki |
| TLS | Let's Encrypt, auto-renewing |
| Source | <https://github.com/dhruvagrawal27/hawkeye-nineagents> |

> 🔓 **For evaluators**: `PREFLIGHT_MODE=1` is currently set on the backend so
> auth is bypassed — **just open the URL above and you land in the Branch
> Manager Command Center**. No login required for the demo. The role-switcher
> chip in the top-right lets you flip between Manager → Supervisor → Analyst
> to see how capabilities gate per role. In production this would be a
> Keycloak SSO flow against an HRMS-backed identity provider.

---

## What evaluators will see in 60 seconds

When you open the URL:

1. **Top status bar** is live: IST clock ticking, 5 service health dots
   (Postgres, Redis, Neo4j, Kafka, Groq), KPI counters (open alerts, 24h
   alerts, high-risk users, total events, EPS), WebSocket connectivity dot.
2. **Mission Callout** (amber/paper panel at top of Command Center) explains
   the system in plain English: what it monitors (privileged users), why
   it matters (insider fraud has the highest loss per incident in Indian
   banking), and the five signal families it detects.
3. **Approval queue** (right column) with one-click ✅ Approve / ❌ Reject
   on every escalated alert.
4. **Department rollup table** — alerts grouped by Core Banking / Treasury /
   Loans / HRMS / Compliance.
5. **7-day × 24-hour heatmap** — alert volume by hour-of-day; off-hours and
   weekends light up red.
6. **Audit feed** — scrolling list of every triage action.
7. **Live event tape** (Bloomberg-terminal style) showing each privileged-user
   action being scored in real time, color-flashed by risk level.

To see the system **in motion**, click **Replay Studio** in the sidebar →
**▶ Start mule_burst** → events stream within 5 seconds, alerts fire within
30. Toast notifications pop in the bottom-right for each new CRITICAL alert.

---

## What HAWKEYE actually monitors

The unit of monitoring is **the privileged user** — a bank employee with
access to core banking, treasury, loan origination, customer databases —
**not the customer**. Every event in the stream is one action this user
performed: a transaction they authorised, a customer record they read, an
account modification they made. Each `EMP_*` id on the dashboard is one
such user.

### The five signal families (verbatim from the problem statement)

| Family | Concrete features |
|---|---|
| **Unusual transaction patterns** | `pass_rate` (% of money flowing through), `ps45/ps49` (structuring at ₹45-49K), `fan_ratio` (credits-in / debits-out), `b_max_vol` (peak monthly INR), `g_top1` (top-counterparty share) |
| **Off-hours access** | `pngt` (off-hours fraction), `pwkd` (weekend fraction), `hrs` (active-hours coverage) — flagged with `OFF-HRS` tag in the live tape |
| **Bulk data downloads** | `records_accessed` ≥ 50 per event (read or write); flagged with 📥 |
| **Unauthorized account modifications** | `access_type=WRITE` to systems outside the user's normal access pattern; flagged with 🔓 + W tag |
| **Privilege escalation attempts** | Graph fan-out — sudden expansion in distinct `system_resource` set; surfaced via `g_ncp` (graph counterparty count) deviation from baseline |

Each detection produces:

- **Risk score (0-1)** with a **risk band** (LOW / MEDIUM / HIGH / CRITICAL)
- **SHAP explanation** — top 5 model features driving this score, in plain English
- **LLM investigation memo** — Groq `openai/gpt-oss-120b` (`reasoning_effort=low`)
  with deterministic Jinja fallback. Each memo is 4 paragraphs (Risk Summary /
  What We Observed / Why It Matters / Recommended Next Step) plus an audit-trail
  footer with the raw SHAP factors. Plain English first, technical detail
  second — readable by both a Branch Manager and a fraud analyst.
- **Graph neighbourhood** — which other flagged users share systems with this person

---

## Three roles, three personas

| | **Analyst** (Tier-1) | **Supervisor** (Tier-2) | **Branch Manager** |
|---|---|---|---|
| Read alerts, triage individually | ✓ | ✓ | ✓ |
| Escalate to supervisor | — | ✓ | ✓ |
| Approve / reject escalations | — | ✓ | ✓ |
| Bulk triage (multi-select) | — | ✓ | ✓ |
| Regenerate Groq narrative | — | ✓ | ✓ |
| Audit log access | — | ✓ | ✓ |
| Department rollup + Command Center landing | — | — | ✓ |

Switch role from the **chip in the top-right of the status bar**. Settings page (`/settings`) has a full Roles × Capabilities matrix.

In production: role comes from the Keycloak JWT claim `realm_access.roles`. Demo
creds (when `PREFLIGHT_MODE=0` and Keycloak login is wired):

```
analyst@hawkeye.local    / analyst       (role: analyst)
supervisor@hawkeye.local / supervisor    (roles: analyst + supervisor)
```

---

## Architecture (one diagram)

```
synthetic_events.jsonl                          (516 K events, dual-schema —
       │                                        banking fields the model sees +
       ▼                                        insider-threat overlay the UI shows)
  Replay → Kafka(hawkeye.events) → Consumer
                                      │
                          Redis aggregator (base features + live deltas)
                          Neo4j graph (employee → system access)
                                      │
                          LightGBM M1+M2 blend → SHAP top-5
                                      │ score >= 0.16032509
                          Groq narrative (openai/gpt-oss-120b, reasoning_effort=low)
                          + Jinja fallback that's structurally identical
                                      │
                          FastAPI REST + WebSocket (alert.new / alert.updated / event.scored)
                                      │
                          React 18 + Vite + Tailwind + D3 SPA (dark Bloomberg
                          terminal aesthetic with paper-tone reference panels)
```

12 Docker services in compose: `zookeeper · kafka · kafka-init · redis · neo4j · postgres · minio · keycloak · mlflow · prometheus · grafana · backend · frontend`. Detailed component breakdown in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Tech stack

- **Backend**: Python 3.11, FastAPI, async SQLAlchemy 2, Alembic, structlog
- **ML**: LightGBM (M1+M2 blended), SHAP TreeExplainer, 146 features, threshold 0.16032509
- **LLM**: Groq SDK, model `openai/gpt-oss-120b` with `reasoning_effort=low`, Jinja fallback
- **Streaming**: Apache Kafka, confluent-kafka-python
- **Graph**: Neo4j 5 (community), AsyncGraphDatabase
- **State**: Redis 7 (per-user feature snapshot + live deltas), Postgres 15
- **Auth**: Keycloak 23 OIDC + JWT (bypassed in `PREFLIGHT_MODE=1`)
- **Frontend**: React 18, Vite, TypeScript, Tailwind, D3.js, Recharts, react-markdown, zustand, TanStack Query
- **Infra**: Docker Compose (12 services), host nginx + certbot at the edge
- **CI/CD**: GitHub Actions — `ci.yml` (ruff + pytest + tsc) on every PR, `deploy.yml` SSHes into the VPS and runs `deploy.sh` on every push to `main`

---

## Quick start (local development, 5 minutes)

```bash
git clone https://github.com/dhruvagrawal27/hawkeye-nineagents
cd hawkeye-nineagents
cp .env.example .env
# fill GROQ_API_KEY at minimum (get a free key at console.groq.com)
# leave PREFLIGHT_MODE=1 for local dev (auth bypassed; role switcher controls UI gating)

docker compose up -d                                       # 12 services, ~60-90s cold boot
docker compose exec backend alembic upgrade head           # schema
docker compose exec backend python -m app.scripts.seed     # 50 alerts + 10k Redis features + 50 graph nodes
docker compose exec backend python -m app.scripts.preflight_check    # 10 checks, must show "PASSED: 10  FAILED: 0"

# Open the dashboard
start http://localhost:8080
```

To see live alerts firing: open <http://localhost:8080/replay> and click **▶ Start mule_burst**, then **Inject mule burst** — alerts pop in within 10 seconds.

---

## Production deployment

The system is currently live on a Hetzner CX33 in Helsinki, deployed via the
recipe in [DEPLOYMENT.md](DEPLOYMENT.md). Lessons learned from the actual
deployment (port conflicts, DNS gotchas, compose merge bugs, etc.) are in
[DEPLOYMENT_RETRO.md](DEPLOYMENT_RETRO.md) — read this if you're going to
deploy your own instance, it'll save you 2-3 hours.

```
Cost  ~ €8/month  (Hetzner CX33)
       Backups currently NOT enabled — cost decision; can be flipped on
       in the Hetzner console for an additional ~€1.60/month if needed.
```

CI/CD: `git push origin main` → GitHub Actions runs `deploy.sh` over SSH on
the VPS → docker compose pull/build/up → migrate → seed → preflight → reload nginx.
Average warm-deploy time: ~3 minutes.

---

## Compliance posture

HAWKEYE operates under a strict **human-in-the-loop** policy. All automated risk scores must be
reviewed by a human analyst before any operational action is taken. Every alert ships with a SHAP
factor breakdown and a model-generated investigation memo for auditability. Compliant with RBI
FREE-AI guidelines, ITV-2 SSO requirements, and the bank's internal model risk management framework.

---

## Documentation index

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — data flow, design decisions, schemas
- **[ML.md](ML.md)** — the model: 9-stage training pipeline, 146 features, dual-model blend, SHAP, synthetic-data signature preservation
- **[DEMO.md](DEMO.md)** — 5-minute walkthrough script for judges
- **[ROUND1_GAP_ANALYSIS.md](ROUND1_GAP_ANALYSIS.md)** — honest accounting of every Round 1 commitment vs what's actually built (✅ done · 🟡 partial · ❌ not done · 🚫 cut)
- **[ROADMAP.md](ROADMAP.md)** — high-impact upgrades (TEE, self-hosted LLM, T-HGNN, SimCLR, federated learning, quantum-safe, differential privacy)
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — production deploy recipe (Hetzner)
- **[DEPLOYMENT_RETRO.md](DEPLOYMENT_RETRO.md)** — every gotcha we hit on the live deploy + the permanent fixes
- **[QUICKSTART.md](QUICKSTART.md)** — local dev quickstart
- **[CHANGELOG.md](CHANGELOG.md)** — version history
- **[NEXT_STEPS.md](NEXT_STEPS.md)** — known gaps + roadmap
- **[LICENSE](LICENSE)** — proprietary, all rights reserved

---

## 🔐 Trust & security posture (pre-empts the panel's "but Groq sees your data?" question)

Live system is a demo; the production trust story is on a known path. From [ROADMAP.md](ROADMAP.md):

| Concern | Today | Roadmap fix | Effort |
|---|---|---|---|
| LLM provider sees prompts | Groq cloud API receives prompts (employee_id, score, behaviour summary) | Self-hosted Llama-3 / `gpt-oss` via vLLM on bank's GPU. `narrative_service.py` is provider-agnostic — 30-line swap. | Low |
| Backend operator could read memory | Standard Linux container | Trusted Execution Environment (Intel TDX / AMD SEV-SNP / Azure Confidential Computing) — memory cryptographically encrypted, not even root can read | Medium |
| SHAP explanations leak training data | Plain SHAP values | Differential privacy on SHAP factors (ε=0.5 Laplacian noise) — bounds membership-inference attacks per DPDP Act 2023 | Low |
| Future quantum threat to data-at-rest | AES-256 (vulnerable to harvest-now-decrypt-later) | NIST post-quantum standards (CRYSTALS-Kyber + CRYSTALS-Dilithium) — RBI FREE-AI "crypto-agility" requirement | Medium |
| Single-bank model misses cross-bank rings | Each bank trains on its own data | Federated learning via Flower / NVIDIA FLARE — 40 PSBs train collectively without exchanging a single transaction | High |

The pitch line for the panel:
> *"In production HAWKEYE runs inside a Trusted Execution Environment with a self-hosted LLM, differential-privacy on explanations, and quantum-safe encryption — the bank's data never leaves the bank's perimeter, even from us. Federated learning roadmap connects 40+ PSBs without any of them seeing each other's data."*

---

## License

Proprietary. See [LICENSE](LICENSE). Repo is public for RBI NFPC panel evaluation only — no copy / fork / mirror / redistribution rights granted.

## Team

**NINEAGENTS** — RBI NFPC Phase 2, Rank #4 nationally.
