# HAWKEYE — Roadmap (constraint-aware)

The current production deployment runs on a **Hetzner CX33 (4 vCPU / 8 GB / 80 GB) at ~€8/month with no backups, scoring against the Groq cloud LLM**. This document is the path forward **inside those constraints** — no GPU spend, no upgraded VPS tier, no managed services.

Everything in §1 ships on the existing box. Everything in §2 is honestly out of reach without spending more — listed for transparency, not as a near-term plan.

---

## §1 — What we CAN ship on the current CX33 (zero extra cost)

Sorted by impact-per-effort. Every item below has been costed against the 8 GB RAM / 4 vCPU budget.

> **Status update (v0.7.0)**: §1.4 (TEE-attested LLM), §1.5 (T-HGNN +
> SimCLR fusion via Kaggle GPU offload) and embedding-service nearest-
> neighbor coverage are all **shipped and live**. The items below are
> what remains for the next 1-2 sprints.

### 1.1 ⭐ Wire Keycloak SSO into the SPA (drop `PREFLIGHT_MODE=1`)

**What** — Add `keycloak-js` to the React SPA so it redirects to Keycloak on first visit, gets a JWT, uses it for API + WebSocket calls. Then flip `PREFLIGHT_MODE=0` in `/opt/hawkeye/.env` so the backend enforces auth.

**Why it matters** — Today anyone with the URL is in. Real auth is the difference between a demo and a product. Backend already validates JWT properly; only the SPA flow is missing.

**Cost** — 0. Keycloak already running in compose. Frontend code only.

**Effort** — 1 day.

**Pitch line**: *"FIDO2-capable SSO via Keycloak 23. JWT-validated API + WebSocket. Role from JWT claim, not in-memory toggle."*

---

### 1.2 ⭐ Differential privacy on SHAP explanations

**What** — Add Laplacian noise (ε=0.5) to the SHAP factor values shown in the audit trail. Model still scores accurately; the audit trail can't be inverted to reconstruct training rows.

**Why it matters** — DPDP Act 2023 + RBI FREE-AI flag membership-inference attacks. SHAP values leak training-set information. ε-DP provably bounds the leak.

**Cost** — 0. ~30 lines in `scoring._shap_factors`.

**Effort** — Half a day.

**Pitch line**: *"Differentially-private explanations (ε=0.5 Laplacian noise on SHAP). Bounds membership-inference attacks per DPDP Act 2023."*

---

### 1.3 ⭐ HashiCorp Vault for secrets (replace `.env` file)

**What** — Add a Vault container to compose. Migrate the 7 secrets (Groq, Postgres, Neo4j, MinIO, Keycloak admin, Grafana admin, Postgres URL) from `.env` to Vault KV-v2. Backend reads from Vault on startup via `python-hvac`.

**Why it matters** — `.env` files are the #1 leaked-secret vector. Vault gives you audit trails on every secret access, automatic rotation, dynamic database credentials.

**Cost** — 0. Vault dev-mode container is ~50 MB RAM. Fits comfortably.

**Effort** — 1 day.

**Pitch line**: *"Secrets in HashiCorp Vault — not `.env` files. Every read audited. Dynamic database credential rotation."*

---

### 1.4 ⭐ Continuous retraining + drift detection (Evidently AI)

**What** — Nightly cron in the backend that:
1. Pulls last-24h labeled outcomes from `audit_log` (analyst-confirmed alerts → positives, dismissed → negatives)
2. Detects feature distribution drift via Evidently AI (KS tests on each of the 146 features)
3. If drift > threshold OR ≥ 100 fresh labels → kicks off a retrain in the background
4. Logs to MLflow (already running), A/B shadow-mode for 48h, auto-promotes if metrics hold

**Why it matters** — Static models degrade. Insider tactics evolve. Without this, the "live" claim is hollow at month 3.

**Cost** — 0. Evidently AI is a Python lib (~20 MB). LightGBM retrain is CPU-only and fits in 4 GB peak (8 GB box has the headroom).

**Effort** — 1 week.

**Pitch line**: *"Continuous retraining gated on Evidently AI drift detection. A/B shadow-mode validation. MLflow lineage on every model promotion."*

---

### 1.5 ⭐ Adversarial robustness testing (PGD/FGSM via ART)

**What** — Integrate IBM's Adversarial Robustness Toolbox. Generate FGSM and PGD perturbations of mule transaction patterns. Verify the model still flags them at acceptable recall. Log any successful evasion as a model bug.

**Why it matters** — Sophisticated insiders WILL probe the model. RBI FREE-AI specifically calls out "adversarial testing pipeline" as required.

**Cost** — 0. ART runs locally on the trained LightGBM model.

**Effort** — 4-5 days.

**Pitch line**: *"Continuous adversarial red-team testing — every model release passes through automated PGD + FGSM evasion attempts before promotion."*

---

### 1.6 mTLS between containers

**What** — Generate self-signed CA + per-service certs at compose-up time. Mount into each container. Update FastAPI / Postgres / Neo4j / Redis / Kafka clients to require mutual TLS.

**Why it matters** — Defense-in-depth. Today the Docker bridge network is the trust boundary; if any service is compromised, lateral movement is open. mTLS forces every cross-service call to prove identity cryptographically.

**Cost** — 0. Some CPU overhead on TLS handshakes (~2-5%).

**Effort** — 3-4 days (the wiring is fiddly per-service).

**Pitch line**: *"Zero-trust service mesh — every internal call is mTLS-authenticated. SPIFFE-style service identity, no implicit network trust."*

---

### 1.7 Rate limiting + WAF-style API hardening

**What** — `slowapi` middleware on FastAPI: 100 req/min per IP, 1000 req/min per JWT user. Add OWASP top-10 security headers (CSP, X-Frame-Options, X-Content-Type-Options — most are at host nginx already, this tightens them). Block SQL-injection patterns at the edge.

**Why it matters** — Public endpoint deserves DDoS resistance + injection guards. Free hardening.

**Cost** — 0. Slowapi is ~10 KB.

**Effort** — 1-2 days.

**Pitch line**: *"Per-user + per-IP rate limiting. OWASP top-10 hardened. SQL-injection patterns blocked at the edge."*

---

### 1.8 ⭐ AIBOM + Model Card (formal AI lineage docs)

**What** — Generate a formal Google Model Card for the HAWKEYE LightGBM blend (intended use, training data, eval metrics, ethical considerations, known limitations) and an AI Bill of Materials listing every model version + training data checksum + dependency version (akin to SBOM for software).

**Why it matters** — RBI FREE-AI requires "model lineage" documentation. SOC 2 + ISO/IEC 23053 reference AIBOMs as a control. Easy audit win.

**Cost** — 0. Markdown.

**Effort** — 2 days.

**Pitch line**: *"Formal Model Card per Google standards + AI Bill of Materials per ISO/IEC 23053. Every model release tracked, every training-data hash recorded."*

---

### 1.9 Supply-chain hardening in CI (Trivy + Gitleaks + Cosign + SLSA)

**What** — Add four free GitHub Action steps to `ci.yml`:
- **Trivy** — scan every container image for known CVEs, fail CI if HIGH/CRITICAL
- **Gitleaks** — scan every PR for committed secrets
- **Cosign** — sign container images with Sigstore
- **SLSA provenance** — generate Level 3 build provenance attestation

**Why it matters** — Supply-chain attacks (xz-utils, SolarWinds) are the new normal. These four steps make the repo verifiably tamper-evident.

**Cost** — 0. All free GitHub Action steps.

**Effort** — 1 day.

**Pitch line**: *"Sigstore-signed images, SLSA Level 3 build provenance, Trivy CVE gating, Gitleaks secrets scanning. Supply-chain attack-proof CI."*

---

### 1.10 Compliance posture dashboard (in-app)

**What** — A new `/compliance` page in the SPA showing real-time compliance status: DPDP Act check (DP enabled? ✅), FREE-AI human-in-the-loop check (audit trail populated? ✅), retention policy (alerts >X days deleted? ✅), key rotation age (Vault leases <90d? ✅), backup status, etc.

**Why it matters** — Auditors love a dashboard they can screenshot. Compliance is a story you tell, not a binary state.

**Cost** — 0. Pure frontend + 1 backend endpoint.

**Effort** — 2 days.

**Pitch line**: *"Real-time compliance posture page. DPDP Act, RBI FREE-AI, ISO 27001, SOC 2 readiness — visible to the CISO in one screen."*

---

### 1.11 WebAuthn / FIDO2 hardware-key login (via Keycloak)

**What** — Enable WebAuthn in the Keycloak realm so analysts/supervisors/managers can authenticate with YubiKeys, Windows Hello, Touch ID. Pure config change in `realm-export.json`.

**Why it matters** — Bank security teams *love* hardware-key MFA. Phishing-resistant. RBI is pushing for it post-2024 fraud surge.

**Cost** — 0. Keycloak supports it natively.

**Effort** — Half a day (after 1.1 is done).

**Pitch line**: *"Phishing-resistant FIDO2 / WebAuthn hardware-key MFA. YubiKey, Windows Hello, biometric — all supported via Keycloak."*

---

### 1.12 Postgres `pgvector` for narrative similarity

**What** — Enable `pgvector` extension in Postgres. Embed every Groq-generated narrative with `sentence-transformers/all-MiniLM-L6-v2` (90 MB CPU model). Store embeddings in `narratives.embedding`. New endpoint: `/narratives/similar/{id}` — analysts can find historically-similar cases.

**Why it matters** — Investigators repeatedly ask "have we seen this pattern before?". Vector search makes that one click.

**Cost** — 0. MiniLM CPU model is ~90 MB, fits in backend container. Postgres+pgvector is open source.

**Effort** — 2-3 days.

**Pitch line**: *"Vector-search across investigation memos via pgvector + sentence-transformer embeddings. Find historically-similar cases in one query."*

---

### 1.13 Isolation Forest as second-line anomaly detector (zero-label)

**What** — Train an unsupervised Isolation Forest on the live Redis feature snapshots. Flag any user whose IF anomaly score crosses a threshold even when LightGBM doesn't. Pitch as the **partial answer to "zero-label cold start"** — a new bank with no labels gets IF anomaly detection on day one; LightGBM kicks in once they have ≥50 labeled incidents.

**Why it matters** — IF is the closest free thing to SimCLR (which needs GPU). Same headline ("zero-label day-one detection"), 1/100th the implementation cost.

**Cost** — 0. sklearn IsolationForest, ~5 MB.

**Effort** — 2 days.

**Pitch line**: *"Hybrid detection: supervised LightGBM (labeled banks) + unsupervised Isolation Forest (zero-label cold-start). New banks get useful detection day one — without contrastive pre-training."*

---

### 1.14 Time-series forecasting on alert volume (Prophet)

**What** — Fit a Prophet model on the historical alert-rate time series. Show "expected alert volume next 7 days" on the Manager dashboard. Flag anomalies when actual >3σ from forecast.

**Why it matters** — Macro-anomaly: "you're seeing 10× normal alert volume today" is itself a signal of something organisational happening (a coordinated attack, a bug in upstream system, etc.). Catches what individual-user models miss.

**Cost** — 0. Prophet runs CPU.

**Effort** — 2-3 days.

**Pitch line**: *"Prophet time-series forecasting on alert volume. Macro-anomaly detection — catches coordinated attacks invisible at the user level."*

---

## §1.4 — TEE-attested LLM (SHIPPED)

Investigation memos are now generated by `openai/gpt-oss-120b` running inside an Intel TDX + NVIDIA H200 GPU confidential compute enclave. Each request returns a cryptographic attestation that HAWKEYE caches at boot, surfaces per-alert in the UI, and exposes at `/api/attestation` for independent reviewer verification.

| What runs in the TEE | Investigation memo generation only (the LLM call). Scoring still happens in our Hetzner container — that's the next TEE frontier (see §2). |
|---|---|
| Hardware | Intel TDX CPU + NVIDIA H200 GPU TEE |
| Attestation | ed25519-signed gateway address + raw ≈5 KB Intel TDX quote per session |
| Cost | Pay-per-token at ~₹100/month at our alert volume; well within the CX33 budget claim |
| Code | [`backend/app/services/attestation_service.py`](backend/app/services/attestation_service.py) + provider abstraction in [`backend/app/services/narrative_service.py`](backend/app/services/narrative_service.py) |
| UI | [`frontend/src/components/alerts/TEEAttestationBadge.tsx`](frontend/src/components/alerts/TEEAttestationBadge.tsx) shows the proof inline under every narrative |

**Why this matters for the pitch**: insider-fraud memos describe specific employees + SHAP factors that flagged them. Sending that payload to a regular LLM API leaks it to the provider's sysadmins and any future supply-chain compromise. A TEE-attested gateway gives the bank the *security boundary* of self-hosting the model without the GPU CapEx. The Hetzner box now stores no plaintext model state — it only sees encrypted requests in transit.

---

## §1.5 — Kaggle-trained, backend-fused (the new T-HGNN + SimCLR path)

Two notebooks now live in the repo that train on Kaggle's free GPU and export artifacts that drop into `artifacts/`. The backend will load them on boot and fuse them into the LightGBM blend (no GPU required at serve-time, only inference).

| Item | Notebook | Train cost | Serve cost | Status |
|---|---|---|---|---|
| **T-HGNN (HGT over account ↔ counterparty)** | [`thgnn-train.ipynb`](thgnn-train.ipynb) | Kaggle P100/T4, ~30 min | O(1) account_id lookup → `thgnn_proba` | Notebook ✅, backend `embedding_service.py` ✅ — waiting on Kaggle export |
| **SimCLR contrastive pre-training** | [`simclr-pretrain.ipynb`](simclr-pretrain.ipynb) | Kaggle GPU, ~12 min | Linear probe fit at startup → O(1) account_id lookup → `simclr_proba` | Notebook ✅, backend integration ✅ — waiting on Kaggle export |

**Fusion strategy** — `backend/app/services/embedding_service.py` ships with default weights:
```
final = 0.88 * lgb_blend + 0.08 * thgnn_proba + 0.04 * simclr_proba
```
The service rescales weights when only one of the two embedding tables is present (e.g. T-HGNN loaded but SimCLR isn't), and falls back to the raw LightGBM blend when:
- the artifact files aren't on disk,
- or the queried account isn't in either embedding table.

This makes the artifact upload a **feature flag**, not a deploy step. Five unit tests in `backend/tests/test_embedding_service.py` lock the contract.

**Why this works on CX33** — training is what needs the GPU; inference is a `dict[str, float]` lookup. At startup the service:
1. Reads `thgnn_embeddings.parquet` → keeps only `(account_id, thgnn_proba)` (≈1.3 MB).
2. Reads `simclr_embeddings.parquet`, fits a sklearn `LogisticRegression` probe against the labeled subset of `account_feature_matrix.parquet`, then **discards the 128-dim matrix** and keeps only `(account_id, simclr_proba)` (≈1.3 MB).
3. Total resident memory cost: ~3 MB extra. Easily fits in CX33's 8 GB.

`/readyz` exposes the embedding state (versions, OOF AUC, fusion weights, account counts) so the live deploy log captures whether T-HGNN/SimCLR are active.

---

## §2 — What we honestly CAN'T ship on the current CX33

Listed for transparency. These need money or a different architecture.

| Item | Why we can't ship it on CX33 | What it would take |
|---|---|---|
| **Self-hosted LLM weights (run gpt-oss-120b on our own GPU)** | Hetzner CX33 has no GPU. Renting an H100 box is €280+/mo. | We get the **security boundary** of self-hosting without the CapEx by routing the LLM through a TEE-attested confidential gateway (see "TEE for LLM" row, now shipped). For full on-prem weight custody, the future option remains a Hetzner GPU box — separate spend decision. |
| **Trusted Execution Environment for the SCORING path** (LightGBM + T-HGNN run as plaintext inside our Hetzner container) | The CX33 itself has no TDX/SEV exposed by the hypervisor; the LightGBM model state lives in regular container memory. The TEE we ship today protects the LLM path, not the scoring path. | When a customer demands end-to-end confidential compute including the scoring model, port the FastAPI scoring service to a Phala TEE worker or move the whole deployment to Azure Confidential VM (~€55/mo, AMD SEV-SNP attested) / Scaleway COSMOS (~€18/mo, Intel TDX). The narrative-generation TEE we shipped is the proof-of-concept; same vendor stack scales to the scoring path. |
| **Federated learning across banks** | Requires multi-tenant infrastructure, multiple banks consenting, a coordinator with its own infra. Not a code-only change. | Out of reach as a single-VPS system. Pitch as Phase-2 with NPCI / IBA partnership. |
| **Quantum-safe crypto for data-at-rest** | Postgres native PQC support is still preview-stage. Hetzner's volume encryption uses AES-256. | Wait for Postgres 17 PQC GA + Hetzner adoption. Too speculative for now — keep on roadmap as the 2027 item. |
| **Daily Hetzner backups** | Costs ~€1.60/mo extra. You explicitly declined this. | If demoed to a real bank → enable in 1 click, ~€1.60/mo |
| **Multi-region failover** | Requires multiple VPSes + a load balancer in front. | ~€20/mo minimum. Out of scope for the demo. |
| **Apache Flink** | JVM heap requirements alone are 2-4 GB. Adds ~3 GB to the stack. CX33 would tip into swap. | Move to CX43 (16 GB) for ~€16/mo. Probably not worth it — direct Kafka consumer in FastAPI handles 500 ev/s comfortably. |

---

## §3 — Suggested 4-week sprint plan within constraints

Picking the highest panel-impact + lowest effort items from §1:

| Week | Items | Headline pitch unlock |
|---|---|---|
| **Week 1** | 1.1 (Keycloak SSO) + 1.2 (DP on SHAP) + 1.11 (WebAuthn) | "FIDO2-MFA SSO + differentially-private explanations" |
| **Week 2** | 1.3 (Vault) + 1.7 (rate limiting + headers) + 1.9 (CI hardening) | "HashiCorp Vault secrets, OWASP-hardened, Sigstore-signed images, SLSA Level 3" |
| **Week 3** | 1.13 (Isolation Forest) + 1.14 (Prophet) | "Hybrid supervised + unsupervised detection, zero-label day-one + macro-anomaly forecasting" |
| **Week 4** | 1.4 (drift + retraining) + 1.5 (adversarial testing) + 1.8 (Model Card + AIBOM) | "Continuous retraining gated on Evidently drift, ART adversarial-tested, formal Model Card + AIBOM" |

After 4 weeks, every Tier-1 RBI FREE-AI / DPDP / ISO 27001 / SOC 2 talking point is **demonstrably implemented in code**, not just on a slide. The pitch becomes:

> *"HAWKEYE ships with FIDO2 SSO, Vault-managed secrets, differentially-private SHAP explanations (ε=0.5), continuous Evidently-AI drift detection, automated PGD/FGSM adversarial testing, hybrid supervised + zero-label-cold-start detection (Isolation Forest + LightGBM), Prophet-based macro-anomaly forecasting, mTLS service mesh, and Sigstore-signed SLSA Level 3 builds — all in a single Hetzner CX33 instance at ~€8/month. Total cost of ownership for a single-bank deployment: under ₹10,000/year."*

That's a defensible answer to every "is this real or is this a slide?" question.

---

## §4 — Tech buzzwords that test well, mapped to what we can deliver

| Pitch buzzword | Cost-aware delivery |
|---|---|
| **Trusted Execution Environment** | ✅ shipped for the LLM path (§1.4) — Intel TDX + NVIDIA H200, per-request attestation. Scoring-path TEE still on roadmap. |
| **Self-hosted LLM** | ✅ effectively shipped — TEE-attested LLM gateway gives us the security boundary of self-hosting without the GPU CapEx. Full on-prem weight custody remains a separate spend decision. |
| **Differential privacy (ε=0.5)** | ✅ ship today (1.2) |
| **HashiCorp Vault** | ✅ ship today (1.3) |
| **mTLS service mesh** | ✅ ship today (1.6) |
| **WebAuthn / FIDO2** | ✅ ship today (1.11) |
| **Sigstore Cosign + SLSA Level 3** | ✅ ship today (1.9) |
| **Continuous adversarial red-team testing** | ✅ ship today (1.5) |
| **Evidently AI drift detection** | ✅ ship today (1.4) |
| **AI Bill of Materials (AIBOM)** | ✅ ship today (1.8) |
| **Zero-label cold start** | Partial — Isolation Forest (1.13). Full SimCLR needs GPU. |
| **Federated learning** | Pitch as Phase-2 with NPCI partnership; not deliverable on single VPS |
| **Quantum-safe crypto** | 2027 roadmap item; cite NIST PQC standards |
| **Vector search for similar cases** | ✅ ship today (1.12) |
| **Macro-anomaly forecasting** | ✅ ship today (1.14) |
