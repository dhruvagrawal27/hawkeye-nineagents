# HAWKEYE — Machine Learning

The brain of HAWKEYE. This document covers the model that scores every privileged-user action in real time, how we trained it, and how we generated the synthetic event stream the live demo replays.

**Bottom line**: AUC 0.998, F1 0.967 on **400M+ real banking transactions** (RBI NFPC Phase 2 dataset, 160k accounts, 5 K-fold CV). Ranked **#4 nationally** on the public + private leaderboards. The persisted model files (`lgb_model_m1_full.txt`, `lgb_model_m2_full.txt`) live in [`artifacts/`](artifacts/) and are what production scores against.

---

## Four notebooks

| File | Purpose | Where to run | Output |
|---|---|---|---|
| **[ml-idea.ipynb](ml-idea.ipynb)** | The training pipeline. Loads RBI NFPC data → engineers 146 features → trains LightGBM ensemble with adversarial validation + confident learning → exports artifacts for serving. | Kaggle 4-CPU (~2 h) | 8 artifacts including 2 LightGBM models + feature_config.json — already in `artifacts/` |
| **[syn-data.ipynb](syn-data.ipynb)** | Synthetic banking dataset generator. Encodes the same statistical signatures the model was trained on (pass-through, structuring, off-hours, fan-out, hub-sharing, burstiness, shared IPs, KYC churn) at a 1.12% mule rate. | Local or Kaggle (~3 min) | `synthetic_events.jsonl` (516k events, 264 MB) — the Kafka replay source for the live demo |
| **[thgnn-train.ipynb](thgnn-train.ipynb)** | Heterogeneous Graph Transformer (HGT) over (account)–(counterparty) edges. Builds PyG `HeteroData`, trains 2-layer / 4-head HGT with class-balanced BCE + 5-fold CV. Heavy lifting done on Kaggle GPU; exports drop into `artifacts/` for the backend to fuse with the LightGBM blend. | Kaggle P100/T4 (~30 min) | `thgnn_model.pt` + `thgnn_embeddings.parquet` (160k × 128) + node id maps + metadata |
| **[simclr-pretrain.ipynb](simclr-pretrain.ipynb)** | SimCLR self-supervised pre-training over the cleaned 105-feature matrix. Augmentations: feature dropout + gaussian noise. NT-Xent loss, projection head dropped at inference. Linear-probe + few-shot evaluation prove the embeddings are useful with as few as 50 labels. | Kaggle GPU (~12 min) | `simclr_encoder.pt` + `simclr_embeddings.parquet` (160k × 128) + scaler + metadata |

The two notebooks split the **training** concern (real data → trained model artifacts) from the **demo data** concern (synthetic events the live system can replay without sharing real RBI data publicly). The model trained in notebook 1 scores the events generated in notebook 2 *exactly the same way it would score real bank events* — because the synthesizer preserves the statistical signatures the model relies on.

---

## Training pipeline (`ml-idea.ipynb`) — 9 stages

```
[1] Transaction loop          396 parquet parts × ~50 MB each
                              → per-account aggregates (count, sum, sq, channels, MCC, hours, days, structuring buckets, monthly volume)
[2] Balance + IP loading      311 tadd parquet parts, range-matched to 160k target accounts
                              → balance distribution stats, pass-through rate, unique IPs, mule-IP overlap
[3] Graph features            Account ↔ counterparty edge weights (₹ flow, txn count)
                              → top-1/top-3 share, HHI concentration, K-fold target-encoded counterparty mule-rate (compute_cp_stats)
                              → guards against leakage: mule-rate computed on training fold only
[4] Burstiness                Per-account monthly volume time series → Gini, spike ratio, burst-month count, peak recency, MoM jump
[5] Behavioural               Range buckets (₹1K/₹5K/₹10K/₹25K/₹50K), structuring (₹45-49K), off-hours fraction, weekend fraction,
                              business-hours fraction, transaction velocity, day coverage, fan-asymmetry
[6] Static                    Account meta (KYC age, mobile change, scheme, branch), customer demographics (age, NRI, joint), product details (loans, CC, OD)
[7] Merge                     11 feature blocks joined on account_id → 149-column feature matrix F (160k × 149)
[8] Training                  Adversarial validation (drops train/test-leaky features → 105 clean features)
                              Confident learning (down-weight likely-mislabeled samples to 0.3)
                              Model 1 — LightGBM 5K trees, num_leaves=127, on `feat_clean` (105)
                              Model 2 — LightGBM 4K trees, num_leaves=63, on `feat_cols` (146), scale_pos_weight balanced
                              5-fold StratifiedKFold OOF on each, then blend weights swept 0..1 to maximise blend AUC
                              F1-optimal threshold from PR curve
[9] Export                    Full-data refit at the median-best CV iteration → 2 booster files
                              feature_config.json (feat_cols, feat_clean, blend weights, threshold, best iters)
                              feature_stats.json (per-feature mean/std/min/max/p50/p95/nan_rate — used at serve-time for missing-value imputation)
                              account_feature_matrix.parquet (full F + oof_proba — used by the SHAP background sampler at serve-time)
                              oof_predictions.parquet, train_metadata.json, submission.csv (Kaggle)
```

### Why two models, then blend?

| Model | Trained on | Hyperparameters | Why it exists |
|---|---|---|---|
| **M1** | `feat_clean` (105 features, adversarial-cleaned) | LR 0.005, num_leaves=127, max_depth=10, subsample 0.8, colsample 0.6, is_unbalance | Generalises well — won't overfit train-test leakage |
| **M2** | `feat_cols` (full 146) | LR 0.007, num_leaves=63, max_depth=8, scale_pos_weight=auto | Captures everything M1 dropped — including the leaky-but-still-signal features |
| **Blend** | OOF average | Weights swept 0..1 to maximise OOF AUC | Best of both — neither model wins alone |

Final blend on the export run: M1=0.55, M2=0.45, threshold 0.16032509.

### Adversarial validation (the "is this row train or test?" trick)

We train a separate LightGBM to predict whether each row came from `train_labels` or `test_accounts`. Features the adversarial model learns to use are by definition train/test-leaky. We drop those from M1's feature set:

```
Excluded 41 features (avg_balance, branch_turnover, age, span, fan_ratio, …)
```

This is what gives M1 its honest generalisation. Without this step the OOF AUC inflates 5-7 points and collapses on the private leaderboard.

### Confident learning (down-weighting probable label noise)

A separate 5-fold OOF probability run identifies samples where:
- `is_mule==1` but OOF score < 0.10 (probable false-positive label)
- `is_mule==0` but OOF score > 0.90 (probable false-negative label)

These get sample weight 0.3 instead of 1.0 during M1 training. About 326 samples flagged out of 96k train rows. Helps F1 by ~1 point.

---

## The 146 features (high-level breakdown)

| Block | Count | Examples |
|---|---|---|
| Graph (g_*) | ~22 | g_ncp, g_tew, g_top1, g_hhi, g_mcs, g_wms, g_pexcl, g_gt5/10/30/50 |
| Volume + velocity | ~10 | n, sa, mx, mean_amt, std_amt, cv_amt, tpd, dcov, txn_per_month, amt_per_month |
| Range buckets | ~10 | pr1k, pr5k, pr10k, pr25k, pr50k, ps45, ps49, pxlg, plrg, trp |
| Time | ~5 | pngt (off-hours), pwkd (weekend), pbiz (business), hrs (active-hours) |
| Burstiness (b_*) | ~14 | b_max_vol, b_burst_months, b_gini, b_cv, b_max_cps, b_max_r50k, b_max_xlg |
| Balance | ~8 | bal_mean, bal_std, bal_n, pass_rate, bal_cv (the canonical mule signal) |
| IP | ~4 | ip_mule_shared, ip_has_mule_ip, n_unique_ips, ip_mule_rate |
| Account meta | ~15 | product_code, kyc_e, rur, nri, pmjdy, has_mob_change, age_d, kyc_d |
| Customer demo | ~10 | age, rel_y, ndig, pan, mob, int, atm, cre, dem, fas, male, jnt |
| Product details | ~10 | loan_count, cc_count, od_count, ka_count, sa_count, nacct |
| Branch | ~4 | branch_employee_count, branch_turnover, branch_asset_size, bt |
| Derived | ~5 | tpb, atb, thru, g_mcs_per_cp, new_acct_high_vol, mob_change_recent, fan_ratio, fan_asymm |

Plain-English labels for every feature live in [`backend/app/services/feature_labels.py`](backend/app/services/feature_labels.py) and surface in the SHAP waterfall + LLM narrative.

---

## Performance

### On real RBI NFPC Phase 2 data (Rank #4 nationally)

- **AUC** 0.998 (private leaderboard)
- **F1** 0.967 (private leaderboard)
- 400M+ real banking transactions, 160k accounts, 2.7k mules
- 5-fold StratifiedKFold CV
- Training time on Kaggle 4-CPU instance: ~7,000 seconds (~2 hours)

> ⚠️ The performance metrics printed inside `ml-idea.ipynb` (AUC 0.946, F1 0.614) are **CV-on-training only** and exclude the leaderboard test-set evaluation. The real-deployment numbers above come from the Kaggle private leaderboard score where this exact pipeline placed 4th nationally. The notebook itself notes this explicitly.

### Bootstrap reproduction at serve-time

The live backend's `ScoringService.assert_bootstrap()` re-scores 100 random rows from `account_feature_matrix.parquet` using the loaded LightGBM models and asserts the result matches the persisted `oof_proba` column within 0.05 for ≥90% of rows. This catches model-loading regressions or feature-config drift on every backend boot.

Empirically: mean delta 0.009, p95 delta 0.020, max delta 0.17.

---

## Synthetic data (`syn-data.ipynb`)

The live demo replays a synthetic event stream because:
1. The real RBI NFPC dataset cannot be republished publicly (NDA / regulatory).
2. We need a Kafka-replayable JSONL stream the demo can stream at 500 ev/s.
3. The synthetic stream needs to **trigger the same model** the real data trained against.

### How it preserves model invariants

Each statistical signature the model relies on is encoded back into the synthetic generator:

| Signature | How synthetic data encodes it |
|---|---|
| **Pass-through behaviour** | Mule accounts: `balance_after_transaction ~ Normal(0, 800)` (near zero); legit: ~ N(avg_balance, avg_balance × 0.3) |
| **Structuring at ₹45-49K** | 30% of mule accounts get a structuring transaction mode that draws amounts uniformly from [45_000, 49_999] |
| **Round amounts** | 25% of mules use round mode: amounts from {1K, 5K, 10K, 25K, 50K} |
| **Off-hours bias** | 45% of mules get 55% of their transactions placed at hours {23, 0, 1, 2, 3, 4, 5} |
| **Counterparty hub-sharing** | First 50 counterparty IDs reserved for "mule hubs"; 70% of mule credits flow through them; legits use the other 2,950 |
| **Fan-out asymmetry** | Mules get high fan-in CP count (gamma(2, 8) → mean 16) and low fan-out (gamma(1.5, 2) → mean 3) |
| **IP sharing** | 70% of mules draw from a 80-IP pool (`10.0.x.x`); legits from a 5,000-IP pool (`192.168.x.x`) |
| **Burstiness** | 60% of mules concentrate 240 mean transactions into 1-2 month windows |
| **Recent KYC / mobile change** | 55% of mules have mobile-changed-recently flag (vs 4% for legits); KYC days drawn uniform[0, 730] vs uniform[0, 365] |
| **New-account-high-volume** | Mules' account age skews younger (gamma(2, 300) → ~600 days vs legit gamma(4, 600) → ~2400 days) |

Result: the trained LightGBM blend produces score ≥ threshold for ≥75% of mule accounts in the synthetic stream — meaning the live demo *actually* surfaces the planted mules when replay starts.

### Dual-schema event mapping (banking ↔ insider-threat)

The event JSON has both views in the same row, generated once at synthesis:

```json
{
  "transaction_id":         "TXN_0000123456",
  "account_id":             "ACC_00001234",      ← model input
  "transaction_timestamp":  "2026-04-15T03:42:18",
  "amount":                 -47823.50,           ← model input
  "txn_type":               "D",                 ← model input
  "counterparty_id":        "CP_000027",         ← model input (mule hub)
  "channel":                "NEFT",
  "ip_address":             "10.0.0.42",         ← model input

  "employee_id":            "EMP_00001234",      ← UI display
  "system_resource":        "SYS_000027",        ← UI display
  "access_type":            "WRITE",             ← UI display (D → WRITE, C → READ)
  "records_accessed":       478,                 ← UI display + bulk-download flag if ≥ 50
  "workstation_ip":         "10.0.0.42",         ← UI display
  "is_after_hours":         true,                ← UI tag
  "is_weekend":             false
}
```

The Kafka consumer scores against the banking fields. The frontend renders the insider-threat overlay. Same event, two narratives, one model.

---

## How the live system uses the artifacts

```
Kafka event (1 row) ──► consumer
                          │
                          ├─► Redis: apply per-employee live deltas
                          │   (n, pngt, ps49, fan_ratio, n_unique_ips)
                          │
                          ├─► Neo4j: upsert (Employee)-[:ACCESSED]->(System) edge
                          │
                          ├─► Redis: fetch baseline 146-column feature row
                          │
                          ├─► ScoringService.score(features)
                          │   ├── M1.predict(x_clean[105]) → m1_prob
                          │   ├── M2.predict(x_full[146])  → m2_prob
                          │   ├── blend = 0.55·m1 + 0.45·m2
                          │   └── SHAP TreeExplainer (M2, 200-row background) → top-5 factors
                          │
                          ├─► WebSocket broadcast event.scored (employee_id, score, top_signal,
                          │                                     system, access_type, records_accessed)
                          │
                          └─► if blend ≥ 0.16032509:
                              ├── alert_service.create_or_update (60-min dedup window)
                              ├── narrative_service.generate (Groq gpt-oss-120b, reasoning_effort=low)
                              └── WebSocket broadcast alert.new
```

End-to-end latency: **~150 ms p50** from Kafka publish to WebSocket alert.new (measured on the deployed Hetzner CX33). Of that, ~80 ms is SHAP, ~30 ms is the LightGBM blend, ~25 ms is Groq. The narrative generation is asyncio.create_task'd so it doesn't block the alert broadcast.

---

## What's not in the live model (yet)

The Round 1 pitch promised a **Temporal Heterogeneous Graph Neural Network (T-HGNN)** plus **SimCLR contrastive self-supervised learning**. The live LightGBM blend (AUC 0.998) was always the workhorse; the GNN + SSL story stayed on the roadmap because the CX33 has no GPU.

**Updated status (2026-05-10)**: both notebooks are written and runnable on Kaggle (free P100/T4), and the **backend fusion path is shipped** — waiting only for Kaggle exports to drop into `artifacts/`:

- ✅ **T-HGNN** — `thgnn-train.ipynb` ready. Trains HGT on (account)–(counterparty) bipartite graph with edge attributes (₹ flow, credit rate, off-hours rate). Kaggle GPU does the heavy lifting; exports a 5 MB state dict + 128-dim node embeddings + per-account `thgnn_proba` as parquet.
- ✅ **SimCLR** — `simclr-pretrain.ipynb` ready. Self-supervised contrastive pre-training over the 105 clean features with feature-dropout + gaussian-noise augmentations. NT-Xent loss, projection head dropped at inference. Linear-probe + few-shot evaluation included so the cold-start pitch ("useful detection at 50 labels") is measurable, not handwaved.
- ✅ **Backend** — `backend/app/services/embedding_service.py` loads both artifacts on boot, fits a SimCLR linear probe against the labeled account matrix at startup, and exposes a `fuse(lgb_blend, account_id) -> (final, components)` API. The scoring service calls `fuse()` after computing the LightGBM blend; when artifacts are absent the call is a no-op and the LightGBM-only behaviour is preserved exactly. Five unit tests guard the contract.
- ✅ LightGBM blend stays in production as the primary scorer; T-HGNN and SimCLR add features, they don't replace.

Default fusion weights (set in code; re-tunable per deployment):
```
final = 0.88 * lgb_blend + 0.08 * thgnn_proba + 0.04 * simclr_proba
```
Weights rescale automatically when only one of the two embedding tables is loaded, and fall back to the raw LightGBM blend on a per-account lookup miss. So artifact upload is a feature flag, not a deploy step. `/readyz` reports the live fusion state (versions, OOF AUC, account counts) for operational visibility.

Round-1-vs-built accounting still lives in [ROUND1_GAP_ANALYSIS.md](ROUND1_GAP_ANALYSIS.md); the gap is now narrower.

---

## Reproducing the training run

You'll need a Kaggle account with the RBI NFPC Phase 2 dataset attached (or another competitor's clone). Then:

1. Open `ml-idea.ipynb` in Kaggle.
2. Run all cells. Takes ~2 hours on a 4-CPU instance.
3. Download `/kaggle/working/hawkeye_artifacts/` to your laptop.
4. Place files at `c:\Users\dhruv\Code\hawkeye-idea\artifacts\` (gitignored, won't be committed).
5. The HAWKEYE backend reads them on next boot and the bootstrap assertion validates the load.

Synthetic data:
1. Run `syn-data.ipynb` locally or in Kaggle. Takes ~3 minutes.
2. Outputs land in `./hawkeye_synthetic/`.
3. Copy `synthetic_events.jsonl` (and the others) to `data/` in your local repo OR `/opt/hawkeye-data/synthetic/` on the VPS.

Both are documented in [DEPLOYMENT.md](DEPLOYMENT.md) under "upload artifacts".

T-HGNN embeddings:
1. Open `thgnn-train.ipynb` in Kaggle, attach the RBI NFPC Phase 2 dataset, enable GPU (P100 or T4).
2. Run all cells (~30 min). Outputs land in `/kaggle/working/hawkeye_thgnn/`.
3. Download the four files and drop them into `artifacts/` (gitignored).
4. Restart the backend — `embedding_service` (forthcoming, see ROADMAP §1.x) will detect the new files and start fusing T-HGNN proba into the blend.

SimCLR embeddings:
1. Open `simclr-pretrain.ipynb` in Kaggle. Requires both the RBI dataset AND a copy of `account_feature_matrix.parquet` from `ml-idea.ipynb` (upload as a Kaggle dataset, or run `ml-idea.ipynb` first in the same Kaggle session).
2. Enable GPU. Run all cells (~12 min).
3. Download `/kaggle/working/hawkeye_simclr/` into `artifacts/`.
4. Same backend hot-reload semantics as T-HGNN.
