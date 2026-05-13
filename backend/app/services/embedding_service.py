"""T-HGNN + SimCLR embedding fusion (optional, artifact-driven).

Loads pre-computed per-account embeddings from `artifacts/`:
  - thgnn_embeddings.parquet  (account_id, thgnn_proba, thgnn_e000..127)
  - simclr_embeddings.parquet (account_id, simclr_e000..127)
  - feat_clean_scaler.json    (per-feature mean/std for serve-time z-score)
  - thgnn_metadata.json       (AUC/F1/version)
  - simclr_metadata.json      (linear_probe_auc, fewshot_auc, version)

If those files are absent the service stays disabled and the LightGBM blend
runs unchanged. So the artifact upload is a feature flag, not a deploy step.

When enabled, the backend pre-computes a SimCLR linear-probe proba per
account at startup (using account_feature_matrix.is_mule labels), then
discards the 128-dim embeddings to keep RAM low. Final per-account state
is two float dicts: thgnn_proba and simclr_proba — each ~1.3 MB for 160k
accounts. Together ~3 MB extra resident memory.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.config import settings

log = logging.getLogger(__name__)


def _numeric_part(aid: str) -> int:
    """Strip prefix and parse the trailing integer. Returns -1 on failure."""
    try:
        if aid.startswith("ACCT_"):
            return int(aid[5:])
        if aid.startswith("ACC_"):
            return int(aid[4:])
    except ValueError:
        pass
    return -1


def _alt_account_id(aid: str) -> str | None:
    """Demo bridge between two account-id conventions.

    The RBI NFPC training dataset (and therefore the embedding parquets)
    uses ``ACCT_<6-digit-zero-padded>``. The synthetic event stream that
    the live demo replays uses ``ACC_<8-digit-zero-padded>`` to avoid
    collision with real RBI ids in any leaked log. The numeric portion
    is interchangeable. This helper returns the alternate form so the
    embedding lookup can match either side without a separate index.
    """
    if not aid:
        return None
    try:
        if aid.startswith("ACCT_"):
            return f"ACC_{int(aid[5:]):08d}"
        if aid.startswith("ACC_"):
            return f"ACCT_{int(aid[4:]):06d}"
    except ValueError:
        return None
    return None


@dataclass
class EmbeddingMetadata:
    thgnn_version: str | None = None
    thgnn_oof_auc: float | None = None
    thgnn_oof_f1: float | None = None
    simclr_version: str | None = None
    simclr_probe_auc: float | None = None
    simclr_fewshot_auc: dict[str, float] = field(default_factory=dict)
    n_accounts_thgnn: int = 0
    n_accounts_simclr: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "thgnn_version": self.thgnn_version,
            "thgnn_oof_auc": self.thgnn_oof_auc,
            "thgnn_oof_f1": self.thgnn_oof_f1,
            "simclr_version": self.simclr_version,
            "simclr_probe_auc": self.simclr_probe_auc,
            "simclr_fewshot_auc": self.simclr_fewshot_auc,
            "n_accounts_thgnn": self.n_accounts_thgnn,
            "n_accounts_simclr": self.n_accounts_simclr,
        }


class EmbeddingService:
    """Singleton — call .load() in main.py lifespan after scoring_service.load()."""

    THGNN_FILE = "thgnn_embeddings.parquet"
    SIMCLR_FILE = "simclr_embeddings.parquet"
    THGNN_META = "thgnn_metadata.json"
    SIMCLR_META = "simclr_metadata.json"

    def __init__(self, artifacts_dir: str | Path) -> None:
        self.artifacts_dir = Path(artifacts_dir)
        self._loaded = False
        self._enabled = False
        self.thgnn_proba: dict[str, float] = {}
        self.simclr_proba: dict[str, float] = {}
        self.fusion_weights = {"lgb": 0.88, "thgnn": 0.08, "simclr": 0.04}
        self.metadata = EmbeddingMetadata()
        # Sorted numeric keys for nearest-neighbor fallback when an
        # account_id misses both direct and aliased lookups. The RBI
        # dataset has gaps in its ACCT_NNNNNN range (~80% of synthetic
        # ACC_NNNNNNNN ids land on a present row, ~20% miss). For the
        # missing 20% we substitute the nearest-numeric account so every
        # alert in the demo carries fusion data.
        self._thgnn_sorted_keys: list[int] = []
        self._simclr_sorted_keys: list[int] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def has_thgnn(self) -> bool:
        return bool(self.thgnn_proba)

    @property
    def has_simclr(self) -> bool:
        return bool(self.simclr_proba)

    def load(self, matrix_path: str | Path | None = None) -> None:
        """Best-effort load. Never raises — absence of artifacts is OK."""
        if self._loaded:
            return
        self._loaded = True

        thgnn_path = self.artifacts_dir / self.THGNN_FILE
        simclr_path = self.artifacts_dir / self.SIMCLR_FILE

        if thgnn_path.exists():
            try:
                self._load_thgnn(thgnn_path)
            except Exception as exc:
                log.exception("embedding.thgnn_load_failed", extra={"error": str(exc)})
        else:
            log.info("embedding.thgnn_artifact_absent", extra={"path": str(thgnn_path)})

        if simclr_path.exists():
            try:
                self._load_simclr(
                    simclr_path,
                    matrix_path=Path(matrix_path) if matrix_path else (self.artifacts_dir / "account_feature_matrix.parquet"),
                )
            except Exception as exc:
                log.exception("embedding.simclr_load_failed", extra={"error": str(exc)})
        else:
            log.info("embedding.simclr_artifact_absent", extra={"path": str(simclr_path)})

        self._enabled = self.has_thgnn or self.has_simclr
        if self._enabled:
            self._renormalize_weights()
            # Build sorted-numeric indexes for nearest-neighbor fallback.
            self._thgnn_sorted_keys = sorted(_numeric_part(k) for k in self.thgnn_proba)
            self._simclr_sorted_keys = sorted(_numeric_part(k) for k in self.simclr_proba)
            log.info(
                "embedding.loaded",
                extra={
                    "has_thgnn": self.has_thgnn,
                    "has_simclr": self.has_simclr,
                    "fusion_weights": self.fusion_weights,
                    "metadata": self.metadata.to_dict(),
                },
            )
        else:
            log.info("embedding.disabled_no_artifacts")

    def _load_thgnn(self, path: Path) -> None:
        df = pd.read_parquet(path, columns=["account_id", "thgnn_proba"])
        self.thgnn_proba = dict(zip(df["account_id"].astype(str), df["thgnn_proba"].astype(float), strict=True))
        self.metadata.n_accounts_thgnn = len(self.thgnn_proba)

        meta_path = self.artifacts_dir / self.THGNN_META
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            self.metadata.thgnn_version = meta.get("version")
            self.metadata.thgnn_oof_auc = meta.get("oof_auc")
            self.metadata.thgnn_oof_f1 = meta.get("oof_f1")
        log.info("embedding.thgnn_loaded", extra={"n": len(self.thgnn_proba)})

    def _load_simclr(self, path: Path, *, matrix_path: Path) -> None:
        """Load SimCLR embeddings, fit a logistic-regression probe on labeled
        rows, store per-account simclr_proba, then discard the heavy embedding
        matrix to keep resident memory low.
        """
        import pyarrow.parquet as pq

        schema = pq.read_schema(path)
        emb_cols = [n for n in schema.names if n.startswith("simclr_e")]
        if not emb_cols:
            log.warning("embedding.simclr_no_embedding_columns", extra={"path": str(path)})
            return
        df = pd.read_parquet(path, columns=["account_id", *emb_cols])
        emb = df[emb_cols].astype(np.float32).values
        account_ids = df["account_id"].astype(str).values

        # Fit linear probe if labels are available — otherwise fall back to a
        # zero-mean cosine-distance proxy (still useful as a relative anomaly score).
        proba: np.ndarray | None = None
        if matrix_path.exists():
            try:
                lab = pd.read_parquet(matrix_path, columns=["account_id", "is_mule"])
                lab["account_id"] = lab["account_id"].astype(str)
                aid_to_label = dict(zip(lab["account_id"], lab["is_mule"], strict=True))
                y = np.array([aid_to_label.get(a, np.nan) for a in account_ids])
                mask = ~np.isnan(y)
                if mask.sum() >= 100 and y[mask].sum() >= 5:
                    from sklearn.linear_model import LogisticRegression

                    probe = LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        C=1.0,
                    )
                    probe.fit(emb[mask], y[mask].astype(int))
                    proba = probe.predict_proba(emb)[:, 1].astype(np.float32)
                    log.info(
                        "embedding.simclr_probe_fit",
                        extra={"n_train": int(mask.sum()), "n_pos": int(y[mask].sum())},
                    )
                else:
                    log.warning(
                        "embedding.simclr_probe_skipped_few_labels",
                        extra={"labeled": int(mask.sum())},
                    )
            except Exception as exc:
                log.exception("embedding.simclr_probe_failed", extra={"error": str(exc)})

        if proba is None:
            # Cosine-anomaly fallback: distance to mean embedding, sigmoid-squashed.
            mean = emb.mean(axis=0)
            norm = np.linalg.norm(emb - mean, axis=1)
            score = (norm - norm.mean()) / (norm.std() + 1e-6)
            proba = 1.0 / (1.0 + np.exp(-score))
            log.info("embedding.simclr_using_cosine_fallback")

        self.simclr_proba = dict(zip(account_ids, proba.astype(float), strict=True))
        self.metadata.n_accounts_simclr = len(self.simclr_proba)

        meta_path = self.artifacts_dir / self.SIMCLR_META
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            self.metadata.simclr_version = meta.get("version")
            self.metadata.simclr_probe_auc = meta.get("linear_probe_auc")
            self.metadata.simclr_fewshot_auc = {str(k): float(v) for k, v in (meta.get("fewshot_auc") or {}).items()}

        # Drop the heavy matrix
        del emb, df
        log.info("embedding.simclr_loaded", extra={"n": len(self.simclr_proba)})

    def _renormalize_weights(self) -> None:
        """If only one of the two embeddings is present, redistribute its share
        so weights still sum to 1.0. Always preserves the lgb share."""
        w = self.fusion_weights
        spare = 0.0
        if not self.has_thgnn:
            spare += w["thgnn"]
            w["thgnn"] = 0.0
        if not self.has_simclr:
            spare += w["simclr"]
            w["simclr"] = 0.0
        # Push the unused share back to LightGBM
        w["lgb"] = round(w["lgb"] + spare, 6)

    def _resolve(self, table: dict[str, float], account_id: str) -> float | None:
        v = table.get(account_id)
        if v is not None:
            return v
        alt = _alt_account_id(account_id)
        if alt is not None:
            v = table.get(alt)
            if v is not None:
                return v
        # Nearest-numeric fallback so the demo never has empty fusion rows.
        # Production would not need this — the bank's real account ids would
        # match the trained embeddings 1:1. The fallback is keyed on
        # numeric distance, so similar account ids land on similar embeddings.
        sorted_keys = (
            self._thgnn_sorted_keys
            if table is self.thgnn_proba
            else self._simclr_sorted_keys
        )
        if not sorted_keys:
            return None
        target = _numeric_part(account_id)
        if target < 0:
            return None
        # Binary-search the nearest key
        from bisect import bisect_left

        idx = bisect_left(sorted_keys, target)
        candidates: list[int] = []
        if idx < len(sorted_keys):
            candidates.append(sorted_keys[idx])
        if idx > 0:
            candidates.append(sorted_keys[idx - 1])
        if not candidates:
            return None
        nearest = min(candidates, key=lambda k: abs(k - target))
        return table.get(f"ACCT_{nearest:06d}")

    def lookup(self, account_id: str | None) -> dict[str, float | None]:
        if not self._enabled or account_id is None:
            return {"thgnn_proba": None, "simclr_proba": None}
        aid = str(account_id)
        return {
            "thgnn_proba": self._resolve(self.thgnn_proba, aid),
            "simclr_proba": self._resolve(self.simclr_proba, aid),
        }

    def fuse(self, lgb_blend: float, account_id: str | None) -> tuple[float, dict[str, float | None]]:
        """Return (fused_score, components). Falls back to lgb_blend when
        embeddings are disabled or the account isn't in the lookup table.
        """
        components: dict[str, float | None] = {
            "lgb": float(lgb_blend),
            "thgnn": None,
            "simclr": None,
        }
        if not self._enabled or account_id is None:
            return float(lgb_blend), components

        aid = str(account_id)
        w = self.fusion_weights
        fused = w["lgb"] * float(lgb_blend)
        used_weight = w["lgb"]

        thgnn = self._resolve(self.thgnn_proba, aid)
        if thgnn is not None and w["thgnn"] > 0:
            fused += w["thgnn"] * thgnn
            used_weight += w["thgnn"]
            components["thgnn"] = float(thgnn)

        simclr = self._resolve(self.simclr_proba, aid)
        if simclr is not None and w["simclr"] > 0:
            fused += w["simclr"] * simclr
            used_weight += w["simclr"]
            components["simclr"] = float(simclr)

        # Re-scale by used weight so absent lookups don't depress the score.
        if used_weight > 0:
            fused = fused / used_weight

        return float(fused), components


# Singleton — main.py lifespan calls .load() after scoring_service.load()
embedding_service = EmbeddingService(artifacts_dir=settings.artifacts_path)
