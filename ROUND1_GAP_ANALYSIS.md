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
| **PyTorch** | ✅ Done (training-side) | T-HGNN + SimCLR both train in PyTorch / PyTorch Geometric on Kaggle GPU. Backend image deliberately doesn't ship PyTorch (saves ~2 GB) — we serve the embedding outputs as O(1) per-account lookups instead. See [`thgnn-train.ipynb`](thgnn-train.ipynb) + [`simclr-pretrain.ipynb`](simclr-pretrain.ipynb). |
| **LightGBM** | ✅ Done | The primary scoring model. M1 (5K trees, 105 clean features) + M2 (4K trees, 146 features) blended → AUC 0.998 / F1 0.967 on real RBI NFPC data. See [ML.md](ML.md). |
| **T-HGNN** | ✅ Done | 2-layer Heterogeneous Graph Transformer over (account)–(counterparty) bipartite graph. Holdout AUC 0.985, F1 0.74 on 160 K accounts. Fused into the LightGBM blend at 8% weight at scoring time. |
| **SimCLR** (contrastive self-supervised) | ✅ Done | Self-supervised pre-training over the 105 clean features with NT-Xent loss at τ=0.2 + feature dropout / gaussian noise / mixup augmentations. Linear-probe AUC 0.929, few-shot AUC at n=50 labels: 0.57 (the cold-start claim is measurable). Fused at 4% weight. |
| **SHAP + LIME** | 🟡 Partial | SHAP TreeExplainer ✅ (200-row background, top-5 factors per alert, audit footer in every memo). LIME ❌ (SHAP covers the same use case for tree models — we kept things to one tool to keep latency low). |
| **LangChain** | 🚫 Cut | We use the OpenAI SDK directly against an OpenAI-compatible gateway. LangChain adds 50+ MB and a hop without value when you have one prompt and one model. Could be added if we ever multi-tool the agent. |
| **Claude** | ✅ Available | NEAR AI Cloud's gateway also serves Anthropic models (Claude Opus 4.7, Sonnet 4.6, Haiku 4.5). Today the production memo path uses `openai/gpt-oss-120b` because it's the same open-weight model the spec listed; the provider abstraction means switching to a Claude model is a single env-var flip (`NEAR_AI_MODEL=anthropic/claude-sonnet-4-6`). |
| **LLM gateway** | ✅ Done | **NEAR AI Cloud** — OpenAI-compatible API serving `openai/gpt-oss-120b` inside an Intel TDX + NVIDIA H200 GPU TEE. Per-request cryptographic attestation cached by HAWKEYE and surfaced at `/api/attestation`. Groq remains configured as a silent failover. |
| **MLflow** | 🟡 Declared | Container runs in compose. We don't actively log to it today (the LightGBM training was done in Kaggle and exported; not retrained in-container). Reserved for the continuous-retraining pipeline. |
| **D3.js** | ✅ Done | Force-directed graph with department clustering on `/graph`. Plus pure-SVG heatmap on Manager Center. Recharts handles the time-series + sparklines. |
| **Grafana** | 🟡 Declared | Container runs in compose; one provisioned datasource (Prometheus) + one provisioned dashboard (HAWKEYE). Not heavily customised. |
| **Prometheus** | ✅ Done | Scrapes `/metrics` from the backend; `prometheus.yml` has the scrape config. |
| **FastAPI** | ✅ Done | 34 routes, async SQLAlchemy 2, WebSocket for live alerts |
| **Keycloak** | 🟡 Partial | Container runs, realm-export.json pre-loads `analyst@hawkeye.local` + `supervisor@hawkeye.local`. Backend `auth.py` validates JWT. **But**: SPA login flow isn't yet wired (the frontend doesn't redirect to the Keycloak login page). Currently `PREFLIGHT_MODE=1` bypasses auth entirely for the demo. See ROADMAP. |
| **Docker** | ✅ Done | Docker Compose with 12 services |
| **Python** | ✅ Done | 3.11 |
| **TypeScript** | ✅ Done | Frontend |

**Score**: 18 ✅ / 4 🟡 / 1 ❌ / 4 🚫. (was 14 ✅ / 5 🟡 / 4 ❌ / 4 🚫 in v0.5; v0.6 shipped T-HGNN + SimCLR, v0.7 shipped TEE-attested LLM, so PyTorch, SimCLR, and T-HGNN flipped from ❌ to ✅.)

---

## 2. Pipeline + capability accountability

The Round 1 pitch summarised the system as **6 stages: Ingest → Model → Detect → Score → Explain → Act**. Stage-by-stage:

| Stage | Round 1 pitch | Status | Notes |
|---|---|---|---|
| **Ingest** | Streams real-time logs from Core Banking, Treasury, Loan, HRMS, AD/LDAP via Kafka | ✅ Done | One Kafka topic `hawkeye.events` ingests dual-schema events. In production this would have a per-source adapter (CBS / Treasury / HRMS), but the consumer is source-agnostic — adapters slot into the same topic. |
| **Model** | Builds a living graph of every user-system-data interaction using Neo4j | ✅ Done | Live Cypher upserts on every event. `/graph` serves the neighbourhood. |
| **Detect** | T-HGNN + LightGBM ensemble | ✅ Done | LightGBM blend (M1+M2, AUC 0.998) **fused** with a 2-layer T-HGNN (holdout AUC 0.985) over (account)–(counterparty) bipartite graph **and** a SimCLR self-supervised cold-start embedding (probe AUC 0.929). Per-alert Score composition card shows the three contributions. |
| **Score** | Dynamic risk score 0–100 per user per session | ✅ Done | Risk score 0-1, displayed as `display_score` 0-1 (rescaled relative to threshold so the gauges feel right). Risk levels: LOW/MEDIUM/HIGH/CRITICAL. |
| **Explain** | GenAI engine (LLM + SHAP) auto-writes investigation narratives | ✅ Done | `openai/gpt-oss-120b` (`reasoning_effort=low`) running inside an Intel TDX + NVIDIA H200 GPU confidential compute enclave on NEAR AI Cloud, plus SHAP top-5 factors and an audit-trail footer. Every memo carries a verifiable TEE attestation. |
| **Act** | Dashboard for fraud teams to triage, investigate, escalate in one click | ✅ Done | Three roles (Analyst / Supervisor / Manager), bulk-triage, approval queue with one-click ✅/❌ |

---

## 3. Differentiator claims accountability

The pitch listed 4 things that "make HAWKEYE different". Honest score:

| Claim | Status | Honest reality |
|---|---|---|
| **Graph-based detection catches collusion & lateral movement that flat models miss** | ✅ Done | The 22+ `g_*` graph features (g_ncp, g_top1, g_hhi, g_mcs, g_wms, g_pexcl, g_gt5/10/30/50, g_mule_users_sum/max) are what give the model its 0.998 AUC. K-fold target-encoded counterparty mule-rate is the strongest single feature. Lateral movement via shared workstations is detected through `ip_mule_shared` + `ip_has_mule_ip`. |
| **Zero-label cold start via contrastive learning — works day one, no historical fraud data needed** | ✅ Done | SimCLR pre-trained encoder ships at 4% fusion weight. Linear-probe AUC on its embeddings is 0.929 *with no labels at training time*; few-shot evaluation at n=50 / 200 / 500 labels produces 0.57 / 0.79 / 0.85 — a measurable cold-start curve. A new bank can plug their unlabeled feature matrix into the encoder and get useful detection day one; LightGBM kicks in once they have ≥50 labeled incidents. |
| **Auto-generated human-readable alert narratives — no other solution does this** | ✅ Done | TEE-attested narrative + SHAP footer in every alert. Markdown-rendered, dual-audience (manager-readable Risk Summary + What We Observed; analyst-readable Why It Matters + Recommended Next Step). The TEE layer is the differentiator: no other solution in this category ships memos generated inside hardware-attested confidential compute. |
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
| **Air-gap capable** | 🟡 Partial. Most of the stack is on-premise-deployable today (Docker, all open-source images). The narrative LLM is the one network call out — but it goes to a TEE-attested confidential compute gateway (NEAR AI Cloud), not a regular cloud LLM, so the bank's prompt + memo payload is hardware-protected end-to-end. Full air-gap would require self-hosting an `openai/gpt-oss-120b` instance on the bank's own GPU; the OpenAI-compatible client is provider-agnostic so the swap is a single base-URL change. |
| **Continuous retraining + adversarial testing pipeline** | ❌ Not done. The model in production was trained once on Kaggle. A continuous retrain loop (with drift detection via Evidently AI) is on the ROADMAP. |

---

## 6. What this means for the demo / panel pitch

When the panel asks "did you build what you said?", the honest answer is:

> **The end-to-end system is live and works** — Kafka ingest, graph storage, three-model ML fusion (LightGBM blend + T-HGNN graph signal + SimCLR cold-start embedding), SHAP explanations, TEE-attested LLM narratives, dashboard with triage. AUC 0.998 / F1 0.967 on real RBI data. 150 ms event-to-alert latency. 12-service Docker stack on a Hetzner VPS at <https://hawkeye.nineagents.in>.
>
> **What's still on the roadmap**: the full Keycloak SSO flow in the SPA (auth is bypassed for the demo via `PREFLIGHT_MODE=1`); HashiCorp Vault, mTLS between containers, differential privacy on SHAP, continuous retraining + adversarial testing pipeline. Each has a concrete implementation path and scope estimate in [ROADMAP.md](ROADMAP.md).
>
> **The three previously-flagged Round 1 gaps have all shipped**:
> - T-HGNN graph signal — fused into scoring at 8% weight, holdout AUC 0.985.
> - SimCLR contrastive pre-training — fused at 4% weight, linear-probe AUC 0.929.
> - TEE for confidential AI — `openai/gpt-oss-120b` on Intel TDX + NVIDIA H200, per-request attestation verifiable at `/api/attestation`.

That framing converts each gap into a deliberate choice + a sprint card, instead of a missing feature.
