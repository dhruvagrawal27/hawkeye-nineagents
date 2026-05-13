# HAWKEYE — Build status & next steps

> 🟢 **System is live** at <https://hawkeye.nineagents.in>. The full panel pitch
> (three-model ML fusion + TEE-attested narrative LLM) is running and verifiable
> from the API alone. Demo is judge-ready in `PREFLIGHT_MODE=1` (auth bypassed,
> role switcher in the top-right). The remaining items below are roadmap, not
> blockers.

## What's complete and verified working

### ML stack (all three models live in production)

| Component | Status | Verifiable at |
|---|---|---|
| **LightGBM scoring** — M1 + M2 blend with adversarial validation + confident learning | ✅ live | `/api/readyz → model_version`. AUC 0.998, F1 0.967 on RBI NFPC private leaderboard (Rank #4). |
| **SHAP TreeExplainer** (200-row background, top-5 factors per alert) | ✅ live | Every alert detail panel renders the SHAP waterfall. |
| **T-HGNN graph signal** — 2-layer Heterogeneous Graph Transformer, account ↔ counterparty bipartite, 160 K accounts | ✅ live | `/api/readyz → embeddings.metadata.thgnn_oof_auc` = **0.985**. Per-alert contribution visible in the Score composition card. |
| **SimCLR cold-start embedding** — NT-Xent contrastive self-supervised pre-training | ✅ live | `/api/readyz → embeddings.metadata.simclr_probe_auc` = **0.929**. Few-shot AUC at n=50 labels: 0.57. |
| **Fusion** — `0.88·lgb + 0.08·thgnn + 0.04·simclr` with auto-rescale on missing embedding + nearest-neighbor fallback for sparse account IDs | ✅ live | Alerts that LightGBM-alone would have missed are flagged with an amber "Rescued by graph fusion" badge. |
| **Confidential LLM narratives** — `openai/gpt-oss-120b` inside Intel TDX + NVIDIA H200 TEE on NEAR AI Cloud | ✅ live | `/api/attestation` returns the live ed25519 signing key + 5 KB Intel TDX quote per request. UI shows the proof under every memo. |
| Provider failover (NEAR AI → Groq → Jinja) | ✅ live | Memos persist `provider` + `tee_attested` columns for per-alert audit. |

### Infrastructure (verified live on Hetzner CX33)

| Component | Status |
|---|---|
| 12-service Docker Compose stack | ✅ running 24/7 |
| Postgres 15 + Alembic migrations (`0001..0003`) | ✅ applied |
| Redis 7 (per-employee feature snapshot + live deltas) | ✅ |
| Neo4j 5 graph upserts on every event | ✅ |
| Kafka topic `hawkeye.events` (3 partitions) | ✅ |
| Keycloak 23 OIDC pre-loaded (bypassed via `PREFLIGHT_MODE=1`) | ✅ |
| Host nginx + Let's Encrypt TLS (`certbot.timer` auto-renew) | ✅ |
| GitHub Actions CI (`ruff` + `pytest` + `tsc` + `npm`) + auto-deploy on `main` | ✅ |
| MinIO + Prometheus + Grafana + MLflow | ✅ |
| 14 artifact files on `/opt/hawkeye-data/artifacts/` (LightGBM + T-HGNN + SimCLR + metadata) | ✅ verified |
| Preflight check (10 terminal probes) | ✅ green |
| Backend test suite (32 tests) | ✅ all pass |

### Frontend

| Component | Status |
|---|---|
| Bloomberg-terminal dark theme with paper-tone reference panels | ✅ |
| Branch Command Center (Manager landing) | ✅ |
| Live alerts page + slide-over with SHAP waterfall + Score composition + TEE attestation badge | ✅ |
| Employee Detail with Timeline / SHAP / Memo / Alert history tabs + TEE badge on regenerate | ✅ |
| D3 force-directed graph explorer with dept clustering + filtering | ✅ |
| Replay Studio (mule_burst, sequential, inject-burst) | ✅ |
| Role switcher (Analyst / Supervisor / Branch Manager) with localStorage persistence | ✅ |
| Settings page (capability matrix + model card + feature registry) | ✅ |

## Honest roadmap — what's worth doing next

Ordered by panel-impact-per-day-of-work, all shippable inside the current
~₹700/month budget (no Hetzner upgrade, no GPU rent).

### Tier 1 — would land in ≤ 1 day each

1. **Keycloak SSO in the SPA** (`PREFLIGHT_MODE=0`). Backend already validates
   JWTs; only the SPA login redirect is missing. Unlocks the "real auth"
   pitch line without any new infra. WebAuthn/FIDO2 follows as a config flip
   in the realm.
2. **Differential privacy on SHAP** — 30 lines in `scoring._shap_factors`
   adds Laplacian noise (ε=0.5) to the per-feature contribution values.
   Bounds membership-inference attacks per DPDP Act 2023.
3. **Compliance posture page** in the SPA — single screen that reads
   `/api/readyz`, `/api/attestation`, and a couple of new flag-checks
   (DP enabled, audit-log populated, key-rotation age, backups). Auditors
   love a dashboard they can screenshot.

### Tier 2 — 2-5 days each

4. **HashiCorp Vault for secrets** — Vault container in compose, migrate
   the 7 `.env` secrets to KV-v2, backend reads via `python-hvac` at boot.
   Audit on every secret read + dynamic Postgres credentials.
5. **Continuous retraining loop** — nightly cron → Evidently-AI drift
   detection on the live feature stream → retrain LightGBM on
   `audit_log`-confirmed outcomes → A/B shadow + MLflow lineage.
6. **PGD/FGSM adversarial testing** via IBM ART — gates every model
   promotion on evasion failure rate. Lives in CI as a separate job.
7. **`pgvector` similarity search across investigation memos** — enable
   the Postgres extension, embed every saved narrative with
   `sentence-transformers/all-MiniLM-L6-v2` (CPU, 90 MB), expose
   `/narratives/similar/{id}`. Analysts ask "have we seen this pattern
   before?" all the time.

### Tier 3 — 1 week each

8. **Supply-chain CI hardening** — Trivy (CVE scan), Gitleaks (secret
   scan), Cosign (Sigstore image signing), SLSA Level 3 build attestation.
   All free GitHub Action steps.
9. **mTLS between containers** — generate a self-signed CA at
   compose-up, mount per-service certs, update each client to require
   mutual TLS. SPIFFE-style identity, no implicit network trust.
10. **Prophet macro-anomaly forecasting** — fit Prophet on the hourly
    alert-rate stream, flag deviations >3σ from forecast as
    organisation-scale anomalies (coordinated attacks, upstream bugs)
    that per-user scoring misses.

### Out of reach on current CX33 budget — pitched as roadmap, not promised

- **Self-hosted LLM weights** (Llama-3 / gpt-oss-120b on own GPU). Hetzner
  CX33 has no GPU. We deliberately moved the security boundary to NEAR AI
  Cloud's TEE instead — same confidentiality guarantee, no GPU CapEx.
- **TEE for the SCORING path** (LightGBM + T-HGNN running inside a TDX
  enclave). Would need a Phala TEE worker port or migration to Azure
  Confidential VM (€55/mo) / Scaleway COSMOS (€18/mo). The TEE we shipped
  for the LLM is the proof-of-concept; same vendor stack scales to scoring.
- **Federated learning** across multiple banks — needs multi-tenant infra
  + NPCI/IBA partnership. Pitch as Phase-2.
- **Quantum-safe crypto for data-at-rest** — wait for Postgres 17 PQC GA.

## Things to do before the panel walks in

1. Verify <https://hawkeye.nineagents.in> loads and the role switcher works.
2. Curl <https://hawkeye.nineagents.in/api/readyz> from a fresh terminal —
   `llm.tee_attested=true`, `embeddings.enabled=true`, all 5 services green.
3. Curl <https://hawkeye.nineagents.in/api/attestation> — confirms a fresh
   Intel TDX quote (5006 bytes) and the ed25519 signing key the panel can
   cross-check against NEAR AI's `/v1/attestation/report`.
4. Open an alert in the SPA — confirm the Score composition card + TEE
   attestation badge render. Pick a "Rescued by graph fusion" alert to
   showcase.
5. Have [DEMO.md](DEMO.md) open in another tab as a script if needed.
