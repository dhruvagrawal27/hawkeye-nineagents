# HAWKEYE — Roadmap & high-impact tech upgrades

The current live system at <https://hawkeye.nineagents.in> covers the
end-to-end demo. This document is what we'd add **next** — a mix of
Round 1 commitments not yet delivered and "new-age" upgrades that turn
the pitch from "AI fraud detector" into "bank-grade trustworthy AI".

Each section: **What it is · Why it matters · Effort · Implementation
sketch · Pitch line for the panel.**

---

## Tier 1 — Bank-grade trust (these unlock real customer conversations)

### 1.1 ⭐ Trusted Execution Environment (TEE) for the scoring pipeline

**What it is** — Run the backend container inside an Intel SGX / AMD SEV-SNP /
Azure Confidential Computing enclave. Memory is encrypted; even root on the
host (and the cloud admin, and us) can't read what's inside.

**Why it matters** — Banks won't ship privileged-user behaviour data to a
SaaS where the operator could theoretically read it. TEEs make "we can't see
your data even if we wanted to" a *cryptographic* guarantee, not a policy.

**Effort** — Medium. Azure/Hetzner now offer confidential VMs out-of-the-box
(Intel TDX or AMD SEV-SNP). Refactor needed: backend image rebuilt as a
confidential container. Performance hit ~5-10% on inference.

**Pitch line**
> *"HAWKEYE runs inside a Trusted Execution Environment. Data is encrypted
> in-memory; even our own DevOps team cannot read it. Cryptographically
> attested by hardware. Bank's keys, bank's data, full stop."*

**Implementation sketch**
- Migrate VPS to Hetzner Confidential Computing tier (Intel TDX) OR Azure
  Confidential Container Instances
- Add TEE-attestation endpoint `/api/attest` that returns the SGX/SEV
  measurement quote
- Document in DEPLOYMENT.md as the production path for any real-data deployment

---

### 1.2 ⭐ Self-hosted LLM (replace Groq cloud API with on-premise model)

**What it is** — Run the narrative LLM (`llama-3.1-70B`, `mistral-large`,
`gpt-oss-120b`) on the bank's own GPU via vLLM, Ollama, or Triton. No
external API call. Drop-in replacement for the Groq SDK.

**Why it matters** — Currently every alert sends a prompt to api.groq.com.
The prompt contains employee_id, score, behaviour summary. Banks regard this
as data exfiltration even if Groq's TOS says "no training". Self-hosted = zero
external network call = compliance officer signs immediately.

**Effort** — Low to medium. The narrative_service.py is already
provider-agnostic. Swapping the AsyncGroq client for an OpenAI-compatible
vLLM endpoint is ~30 lines. The bigger lift is provisioning the GPU box (1×
A100 80GB serves 8B-70B models comfortably).

**Pitch line**
> *"No data ever leaves the bank's perimeter. Our LLM runs on a GPU inside
> your data centre. Zero outbound network calls during scoring. Zero logs at
> any third-party LLM provider. Air-gap capable."*

**Implementation sketch**
- New `narrative_service_local.py` that talks to a vLLM OpenAI-compatible
  endpoint at `http://llm-gpu:8000/v1`
- Env var `NARRATIVE_PROVIDER=groq|local` selects at boot
- Add docker-compose.gpu.yml overlay that runs vLLM + nvidia-runtime
- Document the self-hosted recipe in DEPLOYMENT.md

---

### 1.3 Differential privacy on the SHAP explanations

**What it is** — Add ε-differential noise to the SHAP factor values shown
in the audit trail. The model still scores accurately; the audit trail
can't be inverted to reconstruct individual training rows.

**Why it matters** — DPDP Act 2023 + RBI FREE-AI explicitly call out
membership-inference attacks. SHAP factors leak information about the
training set. Differential privacy provably bounds that leak.

**Effort** — Low. Add Laplacian noise scaled by the SHAP value's sensitivity
in `scoring._shap_factors`. ~20 lines.

**Pitch line**
> *"Even our model's explanations are differentially-private (ε=0.5).
> Membership-inference attacks are bounded. DPDP Act compliant by design."*

---

### 1.4 Quantum-safe cryptography for data-at-rest

**What it is** — Replace AES-256 (vulnerable to quantum) with post-quantum
algorithms (CRYSTALS-Kyber for KEM, CRYSTALS-Dilithium for signatures —
the NIST PQC standards finalised 2024). Used for Postgres encryption,
Neo4j volume encryption, model weights at rest.

**Why it matters** — RBI FREE-AI Aug 2025 framework specifically calls out
"crypto-agility" as a required posture. "Harvest now, decrypt later"
attacks mean even today's traffic is at risk if a quantum computer arrives
in 2030+.

**Effort** — Medium. Most Postgres / Linux LUKS / cloud-provider KMS now
offer hybrid (AES + Kyber) modes. Configuration change, not a rewrite.

**Pitch line**
> *"Quantum-safe by 2026 — CRYSTALS-Kyber for key encapsulation,
> CRYSTALS-Dilithium for signatures. Compliant with NIST PQC standards.
> Future-proof against harvest-now-decrypt-later attacks."*

---

## Tier 2 — Round 1 tech we promised but haven't built yet

### 2.1 ⭐ Temporal Heterogeneous Graph Neural Network (T-HGNN)

**What it is** — A PyTorch Geometric model that ingests the live Neo4j graph
as a heterogeneous typed graph (Employee, System, Customer, Transaction nodes;
ACCESSED, AUTHORIZED, MODIFIED edges) with temporal attention. Outputs an
embedding per (employee, time) → fed alongside LightGBM as a third model in
the blend.

**Why it matters** — Round 1 headline claim. Currently we use Neo4j to *store*
the graph and compute *aggregate* graph features for LightGBM (g_ncp, g_top1
etc). A true T-HGNN forward-pass picks up patterns aggregates miss — e.g.
"this employee accessed System A, then System B 30 min later, then System C
during off-hours" sequence patterns that destroy when summarised to counts.

**Effort** — High. ~2-3 weeks of work:
- Snapshot Neo4j graph at training time → PyG HeteroData
- Implement T-HGNN architecture (HGT or HAN with temporal positional encoding)
- Train on labeled mules from RBI NFPC
- Distill to ONNX for sub-100ms inference
- Add as third model in the blend (`blend_weights: m1=0.40, m2=0.35, thgnn=0.25`)
- Update bootstrap assertion to validate the new artifact

**Pitch line**
> *"Temporal Heterogeneous Graph Neural Network for sequence-aware detection.
> Catches multi-step lateral movement (System A → B → C across hours)
> that flat ensembles miss. PyG-based, ONNX-distilled, sub-100ms inference."*

---

### 2.2 SimCLR contrastive self-supervised pre-training

**What it is** — Pre-train the user-embedding head on UNLABELED behaviour
sequences using SimCLR (or BYOL). Each user's day is a "view"; two augmented
views of the same user's day should embed close, two random users far. After
pre-training, fine-tune the LightGBM classifier on whatever small labeled
fraud set the bank has.

**Why it matters** — Round 1 promised "zero-label cold start". A bank with no
historical fraud labels can't use our supervised LightGBM on day one. SimCLR
gives them a useful representation from their own unlabeled data, then a tiny
labeled set (50 incidents) fine-tunes to bank-specific drift.

**Effort** — Medium-high. ~1-2 weeks:
- Define augmentations (time-jitter, channel-mask, amount-quantise) that
  preserve fraud signature
- SimCLR training loop in PyTorch on the 6-month behaviour windows
- Project embeddings to 128-dim → feed as features to LightGBM
- Document the bootstrapping playbook for "first 50 labels" use-case

**Pitch line**
> *"Zero-label cold start: SimCLR contrastive pre-training learns each user's
> 'normal' from their own unlabeled behaviour. Fine-tunes on as few as 50
> labeled incidents per bank. Day-1 deployable to any new bank."*

---

### 2.3 Wire Keycloak SSO into the SPA (drop PREFLIGHT_MODE)

**What it is** — Add `keycloak-js` to the React SPA so it redirects to the
Keycloak login page on first visit, gets a JWT, and uses it for API + WS calls.
Then flip `PREFLIGHT_MODE=0` in `/opt/hawkeye/.env` to enforce auth on the
backend.

**Why it matters** — Real auth is the difference between a demo and a product.
Backend already validates JWT properly via `auth.py`; just the SPA flow is
missing. ~1 day.

**Effort** — Low.

**Implementation sketch**
- `npm install keycloak-js`
- `frontend/src/lib/auth.ts` — Keycloak singleton with `init({onLoad: 'login-required'})`
- `frontend/src/lib/api.ts` — bearer token interceptor reading from Keycloak instance
- Role chip in TopStatusBar reads from JWT claim instead of zustand store
- Backend: flip PREFLIGHT_MODE=0, restart

---

## Tier 3 — Operational maturity

### 3.1 Continuous retraining + drift detection

**What it is** — A nightly cron in the backend that:
1. Pulls last-24h labeled outcomes from `audit_log` (analyst-confirmed alerts → positives, dismissed → negatives)
2. Detects feature distribution drift via Evidently AI / Alibi Detect
3. If drift > threshold OR labels accumulated > 100, kicks off a retrain in the background
4. Logs to MLflow, A/B tests new model vs current via shadow mode for 48h
5. Auto-promotes if metrics hold

**Why it matters** — Models degrade. Insider tactics evolve. A static model
trained Q1 2026 will be at 80% of original AUC by Q4. Without continuous
retraining, the system's "live" claim is hollow at month 3.

**Effort** — Medium. ~1 week.

**Pitch line**
> *"Continuous retraining with drift detection. Models stay sharp; no manual
> intervention. Every retrain logged to MLflow with A/B shadow validation."*

---

### 3.2 Adversarial robustness testing (red team automation)

**What it is** — Integrate ART (Adversarial Robustness Toolbox) or Foolbox.
Generate FGSM / PGD perturbations of mule transaction patterns; verify the
model still flags them. Log any successful evasion as a model bug.

**Why it matters** — Sophisticated insiders will probe the model. RBI
FREE-AI requires "adversarial testing pipeline" specifically.

**Effort** — Medium. ~1 week.

**Pitch line**
> *"Continuous adversarial red-team testing — every model release passes
> through automated PGD/FGSM evasion attempts before promotion."*

---

### 3.3 Federated learning across multiple banks

**What it is** — Each bank trains its own model locally on its own data.
Periodically the model gradients (not the data) are aggregated via Flower
or NVIDIA FLARE → a global model improves without any bank exposing its
data. Each bank then fine-tunes the global model locally.

**Why it matters** — Industry-wide insider patterns (mule rings spanning
multiple banks) are invisible to single-bank models. Federated learning lets
40 PSBs collectively train a model none could train alone — without sharing
a single transaction.

**Effort** — High. ~3-4 weeks. Requires Flower deployment, multi-tenant
auth on the aggregator, careful attention to differential privacy budgets
across rounds.

**Pitch line**
> *"Federated learning across 40+ scheduled commercial banks. Cross-bank
> threat intelligence without cross-bank data movement. DPDP-compliant
> privacy budgets enforced per round. The first national-scale insider
> threat model — no single bank could train it alone."*

---

### 3.4 Model card + AI Bill of Materials (AIBOM)

**What it is** — Formal Google Model Card for HAWKEYE LightGBM blend
(intended use, training data, eval metrics, ethical considerations, known
limitations). Plus an AIBOM listing every model version, training data
checksum, dependency version (akin to SBOM for software).

**Why it matters** — RBI FREE-AI calls out "model lineage" as required
documentation. SOC2 + ISO/IEC 23053 reference AIBOMs as a control. Easy
audit win.

**Effort** — Low. ~2 days.

---

## Tier 4 — Future / 6+ months out

### 4.1 Multi-modal detection (voice + text + behaviour)

Round 1 mentioned this. Voice-stress detection on bank call recordings,
text sentiment on internal chat, combined with the behavioural model.
Pitch is strong; execution is research-grade.

### 4.2 Deepfake KYC detection (extension to customer-facing fraud)

Out of scope for HAWKEYE proper but pitched as "future scope". Not in the
critical path.

### 4.3 Confidential containers + Intel TDX (defense-in-depth)

Layered on top of Tier 1.1. Each container in compose runs in its own
TDX-attested isolation. Diminishing returns over the TEE base case unless
threat-modelled around lateral movement on the host.

---

## How to prioritise (panel asks: "if you had 4 weeks, what would you do?")

The honest answer:

| Week | Focus | Why |
|---|---|---|
| **Week 1** | Self-hosted LLM (Tier 1.2) + Keycloak SSO (Tier 2.3) | Removes the two biggest "but you're sending data to Groq" / "but there's no real auth" objections in a single sprint. Both are low-effort. |
| **Week 2** | TEE deployment (Tier 1.1) | Massive trust narrative win. Move backend to a confidential VM. |
| **Week 3-4** | T-HGNN (Tier 2.1) — actually deliver the Round 1 headline | Now you can pitch "the only deployed banking insider-threat system with a temporal graph neural network." That's defensible. |

After that:

| Sprint 2 (weeks 5-8) | Continuous retraining + drift detection (3.1), adversarial testing (3.2), differential privacy on SHAP (1.3), model card + AIBOM (3.4) |
|---|---|
| Sprint 3 (weeks 9-12) | SimCLR cold-start (2.2), federated learning prototype with 2 PSB partners (3.3) |
| Sprint 4 (weeks 13-16) | Quantum-safe crypto (1.4), production hardening, SOC 2 Type II prep |

---

## Tech buzzwords that test well in panel pitches (use sparingly, deploy actually)

- **Trusted Execution Environment (TEE)** — Intel SGX / AMD SEV-SNP / Azure Confidential Computing
- **Self-hosted LLM** / "no data leaves the bank perimeter"
- **Differential privacy (ε)** — quantified privacy guarantee
- **Federated learning** — multi-bank without data sharing
- **Quantum-safe / post-quantum cryptography (PQC)** — NIST CRYSTALS-Kyber/Dilithium
- **Model card + AIBOM** — formal model documentation
- **Adversarial robustness (PGD/FGSM)** — red-team-tested model
- **Drift detection (Evidently / Alibi)** — continuous health monitoring
- **Confidential containers (Kata + TDX)** — layered runtime isolation
- **Zero-trust architecture (mTLS + SPIFFE)** — service-to-service identity
- **Crypto-agility** — RBI FREE-AI buzzword for "swappable crypto suite"

The pattern that wins: name a real industry standard, demonstrate
implementation in our codebase, point at where it's wired up. Anything
else is hand-waving.
