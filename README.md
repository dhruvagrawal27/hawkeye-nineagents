# HAWKEYE — AI-Driven Early Warning System for Internal & Privileged User Fraud

> Continuously monitors the behaviour of internal and privileged users across
> banking systems (core banking, treasury, loan origination, customer databases)
> and flags anomalous or potentially fraudulent activities in real time.

Built by team **NINEAGENTS** — RBI NFPC Phase 2, Rank #4 nationally
(AUC 0.998 · F1 0.967 on 400M+ real transactions).

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

## 🔐 Trust & security posture

The production trust story is on a known path within the **same €8/month CX33 budget**. Full plan in [ROADMAP.md](ROADMAP.md). 4-week sprint to shippable:

| Concern | Today | Constraint-aware fix | Cost |
|---|---|---|---|
| Auth bypass for the demo | `PREFLIGHT_MODE=1` | Wire Keycloak SSO into the SPA (1 day, frontend only) + WebAuthn / FIDO2 hardware-key MFA via Keycloak config | 0 |
| `.env` file as secrets store | 7 secrets in `chmod 600` `.env` | HashiCorp Vault container in compose, dynamic DB credentials, audit on every secret read | 0 |
| SHAP explanations leak training data | Plain SHAP values | Differential privacy on SHAP factors (ε=0.5 Laplacian noise) — bounds membership-inference per DPDP Act | 0 |
| Lateral movement on host | Docker bridge network is the trust boundary | mTLS between every container — SPIFFE-style service identity, no implicit trust | 0 |
| Static model degrades silently | Model trained once on Kaggle | Continuous retraining gated on Evidently AI drift detection, A/B shadow mode, MLflow lineage | 0 |
| Insiders can probe the model | Untested against adversarial inputs | PGD + FGSM red-team automation (IBM ART) blocking model promotion if evasion succeeds | 0 |
| Supply-chain attack surface | Standard Docker images | Sigstore Cosign-signed images, SLSA Level 3 provenance, Trivy CVE gating, Gitleaks secrets scanning | 0 |
| Model lineage opaque | No formal documentation | Google-standard Model Card + AI Bill of Materials per ISO/IEC 23053 | 0 |
| Zero-label cold start | Supervised LightGBM only | Isolation Forest as second-line unsupervised detector — banks with no labels get useful detection day one, LightGBM kicks in once they have ≥50 incidents | 0 |
| Macro-anomaly invisible at user level | Per-user scoring only | Prophet time-series forecasting on alert volume — flag organisational-scale anomalies (coordinated attacks, upstream bugs) | 0 |

What's **honestly out of reach** on the current CX33 budget (listed in ROADMAP §2):
- True T-HGNN (PyTorch+PyG needs ~16 GB RAM for training)
- SimCLR contrastive pre-training (needs GPU)
- Self-hosted LLM (needs GPU; Llama-3-8B CPU-only is 5-10 s/token)
- Trusted Execution Environment (depends on whether Hetzner offers Confidential VMs at the same price tier — under investigation)
- Federated learning (needs multi-tenant infra + bank partnerships)

The pitch line for the panel after the 4-week sprint:
> *"HAWKEYE ships with FIDO2 SSO, Vault-managed secrets, differentially-private SHAP (ε=0.5), continuous Evidently-AI drift detection, automated PGD/FGSM adversarial testing, hybrid supervised + zero-label-cold-start detection, Prophet macro-anomaly forecasting, mTLS service mesh, Sigstore-signed SLSA Level 3 builds — all on a single Hetzner CX33 at ₹720/month. Total cost of ownership for a single-bank deployment: under ₹10,000/year."*

---

## License

Proprietary. See [LICENSE](LICENSE). Repo is public for RBI NFPC panel evaluation only — no copy / fork / mirror / redistribution rights granted.

## Team

**NINEAGENTS** — RBI NFPC Phase 2, Rank #4 nationally.
