"""Side-by-side compare of LightGBM-only vs fused score for sample accounts.

Run from the `backend/` directory:
    python -m app.scripts.verify_fusion

Loads the model + embedding artifacts directly (no container needed) and
prints a table showing how T-HGNN + SimCLR fusion shifts scores for known
mules and known benigns. Useful as a one-shot demo of the fusion impact.
"""

import os
import sys

sys.path.insert(0, ".")
os.environ.setdefault("GROQ_API_KEY", "sk-test")
os.environ.setdefault("ARTIFACTS_DIR", os.environ.get("ARTIFACTS_DIR", "../artifacts"))

import pandas as pd

from app.services.embedding_service import embedding_service
from app.services.scoring import scoring_service

scoring_service.load()
embedding_service.load()

print("--- embedding state ---")
print(f"  enabled: {embedding_service.enabled}")
print(f"  weights: {embedding_service.fusion_weights}")
print(f"  thgnn accts: {embedding_service.metadata.n_accounts_thgnn:,}")
print(f"  simclr accts: {embedding_service.metadata.n_accounts_simclr:,}")

# Pull mule + benign accounts so we can see fusion behaviour on both
df = pd.read_parquet("../artifacts/account_feature_matrix.parquet")
df["account_id"] = df["account_id"].astype(str)
mules = df[df["is_mule"] == 1.0].head(4)
benigns = df[df["is_mule"] == 0.0].head(4)

print()
hdr = f'{"account_id":<14} {"label":>6} {"lgb_only":>10} {"thgnn":>10} {"simclr":>10} {"fused":>10} {"delta":>10}'
print(hdr)
print("-" * len(hdr))
for label, sub in [("mule", mules), ("benign", benigns)]:
    for _, row in sub.iterrows():
        aid = row["account_id"]
        feats = row.to_dict()
        r_off = scoring_service.score(feats, account_id=None)
        r_on = scoring_service.score(feats, account_id=aid)
        thgnn = r_on.thgnn_proba or 0
        simclr = r_on.simclr_proba or 0
        delta = r_on.score - r_off.score
        print(
            f"{str(aid)[:14]:<14} {label[:5]:>6} {r_off.score:>10.4f} "
            f"{thgnn:>10.4f} {simclr:>10.4f} {r_on.score:>10.4f} {delta:>+10.4f}"
        )
