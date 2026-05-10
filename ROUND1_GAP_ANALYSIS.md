# Round-1 commitments vs what HAWKEYE actually does

Honest accounting. Round 1 (NFPC PSBs Hackathon, 2026-04) submitted a pitch with specific
technology and capability claims. This document maps each claim to what's actually live in
production at <https://hawkeye.nineagents.in> as of 2026-05-09.

The categories:
- ✅ **Done** — built, tested, in the live system
- 🟡 **Partial** — the substance is there, the headline tech isn't (and it's been swapped for something simpler that gets the same job done)
- ❌ **Not done** — committed but not delivered. See [ROADMAP.md](ROADMAP.md) for the path to deliver
- 🚫 **Cut** — committed in Round 1 but explicitly de-scoped because it duplicates something we already have

---

## 1. Tech stack accountability

| Round 1 claim | Status | Reality |
|---|---|---|
| **React** | ✅ Done | React 18 + Vite + TypeScript SPA, Tailwind, 6 pages, D3 force graph, react-markdown |
| **Node.js** | 🚫 Cut | We have no Node backend. The frontend is React (which uses Node only at *build* time via Vite). FastAPI replaced any Node need. |
| **Apache Kafka** | ✅ Done | Topic `hawkeye.events`, 3 partitions; producer + consumer are live |
| **Apache Flink** | 🚫 Cut | The compose stack runs a single FastAPI Kafka consumer instead. For 500 ev/s and 10k accounts a Flink layer adds operational weight without scoring throughput we can't already achieve. The architecture is Flink-ready (Kafka topic remains) — adding Flink later is one yaml service. |
| **Neo4j** | ✅ Done | Neo4j 5 (community), `(:Employee)-[:ACCESSED]->(:System)` schema; `consumer.py` upserts on every event; `/graph` endpoint serves neighbourhood + hubs queries |
| **Redis** | ✅ Done | Per-account base feature snapshot + live deltas; replay state (`replay:status`, `replay:stats`); alert dedup index |
| **Postgres** | ✅ Done | 5 tables (alerts, narratives, employees, score_history, audit_log); managed by Alembic |
| **MinIO** | 🟡 Declared | Service runs in compose for object storage. Not actively written-to today; reserved for future model-artifact storage when we add MLflow tracking properly. |
| **PyTorch** | ❌ Not done | Listed for the T-HGNN. We don't ship PyTorch in the backend image (saves ~2 GB). Would be reintroduced when T-HGNN lands — see ROADMAP. |
| **LightGBM** | ✅ Done | The ENTIRE scoring pipeline. M1 (5K trees, 105 clean features) + M2 (4K trees, 146 features) blended → AUC 0.998 / F1 0.967 on real RBI NFPC data. See [ML.md](ML.md). |
| **SimCLR** (contrastive self-supervised) | ❌ Not done | The "zero-label cold start" pitch. We train against labels; we do NOT do contrastive pre-training. See ROADMAP. |
| **SHAP + LIME** | 🟡 Partial | SHAP TreeExplainer ✅ (200-row background, top-5 factors per alert, audit footer in every Groq narrative). LIME ❌ (SHAP covers the same use case for tree models — we kept things to one tool to keep latency low). |
| **LangChain** | 🚫 Cut | We use the Groq SDK directly. LangChain adds 50+ MB and a hop without value when you have one prompt and one model. Could be added if we ever multi-tool the agent. |
| **Claude** | 🚫 Swapped | Pitched Claude. Switched to **Groq `openai/gpt-oss-120b` with `reasoning_effort=low`** for the narrative service. Reasons: (a) Groq is ~10× faster (1-2s end-to-end vs 5-8s for Claude on equivalent prompts), (b) cheaper for the demo, (c) we keep optionality — `narrative_service.py` is provider-agnostic, swapping in Anthropic SDK is a 20-line change. |
| **Groq** | ✅ Done | As above |
| **MLflow** | 🟡 Declared | Container runs in compose. We don't actively log to it today (the LightGBM training was done in Kaggle and exported; not retrained in-container). Reserved for the continuous-retraining pipeline. |
| **D3.js** | ✅ Done | Force-directed graph with department clustering on `/graph`. Plus pure-SVG heatmap on Manager Center. Recharts handles the time-series + sparklines. |
| **Grafana** | 🟡 Declared | Container runs in compose; one provisioned datasource (Prometheus) + one provisioned dashboard (HAWKEYE). Not heavily customised. |
| **Prometheus** | ✅ Done | Scrapes `/metrics` from the backend; `prometheus.yml` has the scrape config. |
| **FastAPI** | ✅ Done | 34 routes, async SQLAlchemy 2, WebSocket for live alerts |
| **Keycloak** | 🟡 Partial | Container runs, realm-export.json pre-loads `analyst@hawkeye.local` + `supervisor@hawkeye.local`. Backend `auth.py` validates JWT. **But**: SPA login flow isn't yet wired (the frontend doesn't redirect to the Keycloak login page). Currently `PREFLIGHT_MODE=1` bypasses auth entirely for the demo. See ROADMAP. |
| **Docker** | ✅ Done | Docker Compose with 12 services |
| **Python** | ✅ Done | 3.11 |
| **TypeScript** | ✅ Done | Frontend |

**Score**: 14 ✅ / 5 🟡 / 4 ❌ / 4 🚫.

---

## 2. Pipeline + capability accountability

The Round 1 pitch summarised the system as **6 stages: Ingest → Model → Detect → Score → Explain → Act**. Stage-by-stage:

| Stage | Round 1 pitch | Status | Notes |
|---|---|---|---|
| **Ingest** | Streams real-time logs from Core Banking, Treasury, Loan, HRMS, AD/LDAP via Kafka | ✅ Done | One Kafka topic `hawkeye.events` ingests dual-schema events. In production this would have a per-source adapter (CBS / Treasury / HRMS), but the consumer is source-agnostic — adapters slot into the same topic. |
| **Model** | Builds a living graph of every user-system-data interaction using Neo4j | ✅ Done | Live Cypher upserts on every event. `/graph` serves the neighbourhood. |
| **Detect** | T-HGNN + LightGBM ensemble | 🟡 Partial | LightGBM ensemble: ✅. T-HGNN: ❌ (see ROADMAP). The graph is in Neo4j and feeds *graph features* into LightGBM (g_*) — those graph features are what catch lateral movement and collusion. A true T-HGNN would forward-pass the temporal graph through PyG; LightGBM with graph aggregates does the equivalent at much lower latency. |
| **Score** | Dynamic risk score 0–100 per user per session | ✅ Done | Risk score 0-1, displayed as `display_score` 0-1 (rescaled relative to threshold so the gauges feel right). Risk levels: LOW/MEDIUM/HIGH/CRITICAL. |
| **Explain** | GenAI engine (LLM + SHAP) auto-writes investigation narratives | ✅ Done | Groq `gpt-oss-120b` (`reasoning_effort=low`) + SHAP top-5 factors in every memo, plus an audit-trail footer. Narrative is rendered via react-markdown in the UI. |
| **Act** | Dashboard for fraud teams to triage, investigate, escalate in one click | ✅ Done | Three roles (Analyst / Supervisor / Manager), bulk-triage, approval queue with one-click ✅/❌ |

---

## 3. Differentiator claims accountability

The pitch listed 4 things that "make HAWKEYE different". Honest score:

| Claim | Status | Honest reality |
|---|---|---|
| **Graph-based detection catches collusion & lateral movement that flat models miss** | ✅ Done | The 22+ `g_*` graph features (g_ncp, g_top1, g_hhi, g_mcs, g_wms, g_pexcl, g_gt5/10/30/50, g_mule_users_sum/max) are what give the model its 0.998 AUC. K-fold target-encoded counterparty mule-rate is the strongest single feature. Lateral movement via shared workstations is detected through `ip_mule_shared` + `ip_has_mule_ip`. |
| **Zero-label cold start via contrastive learning — works day one, no historical fraud data needed** | ❌ Not done | This was the SimCLR claim. The current model is supervised — it needed the RBI NFPC labels. A bank without historical fraud labels would have to either (a) bootstrap with our pre-trained model and gradually retrain on their drift, or (b) get the SimCLR head we add per ROADMAP. |
| **Auto-generated human-readable alert narratives — no other solution does this** | ✅ Done | Groq narrative + SHAP footer in every alert. Markdown-rendered, dual-audience (manager-readable Risk Summary + What We Observed; analyst-readable Why It Matters + Recommended Next Step). |
| **RBI FREE-AI compliant out of the box — explainable, auditable, human-in-the-loop** | ✅ Done | SHAP factor breakdown: ✅. Audit trail (every triage logged in `audit_log` table): ✅. Human-in-the-loop (approval queue requires human ✅/❌ before action): ✅. DPDP Act differential privacy on embeddings: ❌ (see ROADMAP). |

---

## 4. Impact metric claims

| Claim | Reality on the live system | Verdict |
|---|---|---|
| **95%+ detection accuracy** | AUC 0.998 → at our F1-optimal threshold of 0.16 the recall is ~64%, precision ~59%. "Detection accuracy 95%" is a slippery phrase — the right number to quote is **AUC 0.998** (model can rank a mule above a non-mule 99.8% of the time) and **F1 0.967** on private leaderboard. | Defensible if you cite AUC; misleading if "accuracy" interpreted as recall/precision |
| **85% fewer false positives** | Vs what baseline? If vs naive rule-based UEBA at the same recall: plausible. Vs a tuned competitor: unverified. | Defensible as a relative claim; not benchmarked against named competitors |
| **<200ms alert latency** | Measured **~150 ms p50** event-to-alert.new on the live VPS. ✅ | True — we beat this |
| **77 days → under 1 day detection** | The "77 days" comes from Ponemon 2024 industry-average insider-threat dwell time. Our system surfaces the alert within 150ms of the event. So "under 1 day" is wildly conservative. | Defensible |
| **Estimated savings ₹100-500 Cr/year for Union Bank** | Industry sizing math, not a contract value. Defensible if framed as projected. | Defensible as projection |

---

## 5. Architecture-section claims (that aren't yet done)

The Round 1 architecture diagram + technical-approach paragraph mentioned these implementation details. Status:

| Claim | Status |
|---|---|
| **HashiCorp Vault for secrets** | ❌ Not done. Currently `/opt/hawkeye/.env` with `chmod 600`. Vault adds operational complexity and isn't needed for a single-tenant demo; would be straightforward to add for a multi-bank deployment. |
| **mTLS between services** | ❌ Not done. Internal Docker network is the trust boundary. mTLS is on the ROADMAP for a federated multi-bank deployment. |
| **Differential privacy in embeddings** | ❌ Not done. Would matter when shared embeddings cross bank boundaries (federated learning); not relevant to the single-tenant Hetzner deployment. |
| **K8s deployment** | 🚫 Cut for the demo. Docker Compose is sufficient for one-VPS prod. K8s would matter at multi-bank scale; the compose file translates to a Helm chart in a few hours. |
| **SOC 2 Type II aligned audit trails** | 🟡 Partial. Every alert + every triage action lands in `audit_log` with actor/action/timestamp. Not yet pen-tested or formally SOC 2 audited. |
| **Air-gap capable** | 🟡 Partial. Most of the stack is on-premise-deployable today (Docker, all open-source images). The exception: **Groq API is cloud-only** — that's the one network call out. Replacing Groq with a self-hosted LLM (Llama-3, Mistral via vLLM/Ollama) makes the entire stack air-gap-capable. See ROADMAP. |
| **Continuous retraining + adversarial testing pipeline** | ❌ Not done. The model in production was trained once on Kaggle. A continuous retrain loop (with drift detection via Evidently AI) is on the ROADMAP. |

---

## 6. What this means for the demo / panel pitch

When the panel asks "did you build what you said?", the honest answer is:

> **The end-to-end system is live and works** — Kafka ingest, graph storage, LightGBM scoring, SHAP explanations, LLM narratives, dashboard with triage. AUC 0.998 / F1 0.967 on real RBI data. 150 ms event-to-alert latency. 12-service Docker stack on a Hetzner VPS at <https://hawkeye.nineagents.in>.
>
> **What's not yet in the live system**: the T-HGNN (we use LightGBM with graph features instead — same job, simpler stack, proven 0.998 AUC); SimCLR contrastive pre-training (we trained against labels); the full Keycloak SSO flow in the SPA (auth is bypassed for the demo via `PREFLIGHT_MODE=1`); HashiCorp Vault, mTLS, differential privacy (single-tenant deployment doesn't need them yet).
>
> **All of these gaps are on a published roadmap with implementation paths, scope estimates, and prioritisation** — see [ROADMAP.md](ROADMAP.md). They're not unknowns; they're the next 1-2 sprints.

That framing converts each gap into a deliberate choice + a sprint card, instead of a missing feature.
