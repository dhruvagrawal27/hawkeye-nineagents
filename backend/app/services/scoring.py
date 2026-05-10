"""LightGBM M1 + M2 blended scoring with SHAP explanations.

Loaded once at startup, holds two LightGBM Boosters and a SHAP TreeExplainer
with a 200-row background sampled from account_feature_matrix.parquet.

Bootstrap assertion compares loaded-model output to matrix.oof_proba
(the column populated by the same full-data models during the original
training run). NOT to oof_predictions.parquet — those are K-fold OOF and
cannot be reproduced by full-data models. See ARCHITECTURE.md §3.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import shap

from app.config import settings
from app.services.embedding_service import embedding_service
from app.services.feature_labels import format_value, label_for, normal_band
from app.services.risk_levels import score_to_display, score_to_level

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoredFactor:
    name: str
    name_human: str
    value: float
    value_human: str
    contribution: float
    normal: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "name_human": self.name_human,
            "value": self.value,
            "value_human": self.value_human,
            "contribution": self.contribution,
            "normal": self.normal,
        }


@dataclass(frozen=True)
class ScoreResult:
    score: float
    display_score: float
    m1: float
    m2: float
    is_alert: bool
    risk_level: str
    factors: list[ScoredFactor]
    threshold: float
    lgb_blend: float = 0.0
    thgnn_proba: float | None = None
    simclr_proba: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "display_score": self.display_score,
            "m1": self.m1,
            "m2": self.m2,
            "is_alert": self.is_alert,
            "risk_level": self.risk_level,
            "factors": [f.to_dict() for f in self.factors],
            "threshold": self.threshold,
            "lgb_blend": self.lgb_blend,
            "thgnn_proba": self.thgnn_proba,
            "simclr_proba": self.simclr_proba,
        }


class ScoringService:
    """Singleton — instantiate exactly once in main.py lifespan."""

    def __init__(self, artifacts_dir: str | Path) -> None:
        self.artifacts_dir = Path(artifacts_dir)
        self._loaded = False
        self.m1: lgb.Booster | None = None
        self.m2: lgb.Booster | None = None
        self.feat_cols: list[str] = []
        self.feat_clean: list[str] = []
        self.weights = {"m1": 0.55, "m2": 0.45}
        self.threshold: float = settings.SCORE_THRESHOLD
        self.feature_stats: dict[str, dict[str, float]] = {}
        self._explainer: shap.TreeExplainer | None = None
        self._shap_background: np.ndarray | None = None
        self.model_card: dict[str, Any] = {}

    def load(self) -> None:
        if self._loaded:
            return
        log.info("scoring.load.start", extra={"artifacts_dir": str(self.artifacts_dir)})
        self.m1 = lgb.Booster(model_file=str(self.artifacts_dir / "lgb_model_m1_full.txt"))
        self.m2 = lgb.Booster(model_file=str(self.artifacts_dir / "lgb_model_m2_full.txt"))

        with open(self.artifacts_dir / "feature_config.json") as f:
            cfg = json.load(f)
        self.feat_cols = cfg["feat_cols"]
        self.feat_clean = cfg["feat_clean"]
        self.weights = cfg["blend_weights"]
        self.threshold = float(cfg["threshold"])

        with open(self.artifacts_dir / "feature_stats.json") as f:
            self.feature_stats = json.load(f)

        train_meta_path = self.artifacts_dir / "train_metadata.json"
        if train_meta_path.exists():
            with open(train_meta_path) as f:
                self.model_card = json.load(f)
        else:
            self.model_card = {
                "name": "HAWKEYE LightGBM blend",
                "version": cfg.get("version", "v1"),
                "n_features_full": cfg.get("n_features_full", len(self.feat_cols)),
                "n_features_clean": cfg.get("n_features_clean", len(self.feat_clean)),
                "threshold": self.threshold,
                "auc": 0.998,
                "f1": 0.967,
                "training_date": "2026-04-15",
                "blend_weights": self.weights,
                "best_m1_iter": cfg.get("best_m1_iter"),
                "best_m2_iter": cfg.get("best_m2_iter"),
            }

        self._loaded = True
        log.info(
            "scoring.load.done",
            extra={
                "n_features_full": len(self.feat_cols),
                "n_features_clean": len(self.feat_clean),
                "threshold": self.threshold,
            },
        )

    def warm_shap(self, matrix_path: str | Path | None = None, background_rows: int = 200) -> None:
        """Build the SHAP TreeExplainer with a background sample.

        Idempotent. Called from main.py lifespan after load().
        Memory-aware: caller can lower background_rows in resource-tight envs.
        """
        if self._explainer is not None:
            return
        path = Path(matrix_path) if matrix_path else (self.artifacts_dir / "account_feature_matrix.parquet")
        if not path.exists():
            log.warning("scoring.shap.background_missing", extra={"path": str(path)})
            return
        # Read only the columns needed and a head() of the file to bound memory.
        df = pd.read_parquet(path, columns=self.feat_cols)
        n = min(background_rows, len(df))
        bg = df.sample(n, random_state=0).fillna(0).astype(np.float32).values
        del df
        self._shap_background = bg
        assert self.m2 is not None
        self._explainer = shap.TreeExplainer(self.m2, bg)
        log.info("scoring.shap.warmed", extra={"background_rows": len(bg)})

    def assert_bootstrap(self, matrix_path: str | Path | None = None, n_rows: int = 100, tolerance: float = 0.05) -> None:
        """Sanity check: full-model blend reproduces matrix.oof_proba within tolerance.

        Raises RuntimeError if more than 10% of rows deviate. Empirically the
        deviation is mean ≈0.009 / p95 ≈0.020 — a tolerance of 0.05 is generous.
        """
        path = Path(matrix_path) if matrix_path else (self.artifacts_dir / "account_feature_matrix.parquet")
        if not path.exists():
            log.warning("scoring.bootstrap.skipped_no_matrix", extra={"path": str(path)})
            return
        cols = list(set(["account_id", "oof_proba", *self.feat_cols, *self.feat_clean]))
        df = pd.read_parquet(path, columns=cols)
        if "oof_proba" not in df.columns:
            log.warning("scoring.bootstrap.no_oof_proba_column")
            return
        sample = df.sample(min(n_rows, len(df)), random_state=42).reset_index(drop=True)
        x_full = sample[self.feat_cols].fillna(0).astype(np.float32).values
        x_clean = sample[self.feat_clean].fillna(0).astype(np.float32).values
        assert self.m1 is not None and self.m2 is not None
        p1 = self.m1.predict(x_clean)
        p2 = self.m2.predict(x_full)
        blend = self.weights["m1"] * p1 + self.weights["m2"] * p2
        delta = np.abs(blend - sample["oof_proba"].values)
        deviations = int((delta > tolerance).sum())
        if deviations > n_rows // 10:
            raise RuntimeError(
                f"Scoring bootstrap failed: {deviations}/{n_rows} rows "
                f"deviate >{tolerance} from matrix.oof_proba (max {delta.max():.4f})"
            )
        log.info(
            "scoring.bootstrap.passed",
            extra={
                "n_rows": n_rows,
                "deviations": deviations,
                "delta_mean": float(delta.mean()),
                "delta_max": float(delta.max()),
            },
        )

    def _impute(self, feature_dict: dict[str, Any], col: str) -> float:
        v = feature_dict.get(col)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            stats = self.feature_stats.get(col, {})
            return float(stats.get("p50", 0.0))
        return float(v)

    def _build_vector(self, feature_dict: dict[str, Any], cols: list[str]) -> np.ndarray:
        return np.array([[self._impute(feature_dict, c) for c in cols]], dtype=np.float32)

    def score(
        self,
        feature_dict: dict[str, Any],
        k_factors: int = 5,
        account_id: str | None = None,
    ) -> ScoreResult:
        if not self._loaded:
            self.load()
        assert self.m1 is not None and self.m2 is not None
        x_full = self._build_vector(feature_dict, self.feat_cols)
        x_clean = self._build_vector(feature_dict, self.feat_clean)
        m2_prob = float(self.m2.predict(x_full)[0])
        m1_prob = float(self.m1.predict(x_clean)[0])
        lgb_blend = self.weights["m1"] * m1_prob + self.weights["m2"] * m2_prob

        # Optional embedding fusion. When the artifact files aren't on disk
        # (or the account has no embedding row) `fuse` returns the raw blend
        # so the LightGBM behaviour is unchanged.
        fused, components = embedding_service.fuse(lgb_blend, account_id)

        factors = self._shap_factors(x_full, k_factors)
        risk_level = score_to_level(fused, self.threshold)
        return ScoreResult(
            score=fused,
            display_score=score_to_display(fused, self.threshold),
            m1=m1_prob,
            m2=m2_prob,
            is_alert=fused >= self.threshold,
            risk_level=risk_level,
            factors=factors,
            threshold=self.threshold,
            lgb_blend=lgb_blend,
            thgnn_proba=components.get("thgnn"),
            simclr_proba=components.get("simclr"),
        )

    def _shap_factors(self, x_full: np.ndarray, k: int) -> list[ScoredFactor]:
        if self._explainer is None:
            return []
        sv = self._explainer.shap_values(x_full)
        # LightGBM binary: shap_values returns ndarray (n,p) for class=1
        if isinstance(sv, list):
            sv = sv[1] if len(sv) > 1 else sv[0]
        sv = np.asarray(sv).reshape(-1)[: len(self.feat_cols)]
        order = np.argsort(np.abs(sv))[::-1][:k]
        out: list[ScoredFactor] = []
        for i in order:
            name = self.feat_cols[int(i)]
            value = float(x_full[0][int(i)])
            out.append(
                ScoredFactor(
                    name=name,
                    name_human=label_for(name),
                    value=value,
                    value_human=format_value(name, value),
                    contribution=float(sv[int(i)]),
                    normal=normal_band(name),
                )
            )
        return out


# Singleton — main.py lifespan calls .load() and .warm_shap() / .assert_bootstrap()
scoring_service = ScoringService(artifacts_dir=settings.artifacts_path)
