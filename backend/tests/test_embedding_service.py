"""EmbeddingService — fusion contract.

Critical invariants:
1. Absent artifacts → service stays disabled, fuse() returns lgb_blend unchanged.
2. Loaded artifacts → fuse() blends within [0,1] and reports component contributions.
3. Lookup miss for an account that exists in the index but not in embeddings →
   fuse() falls back to lgb_blend without depressing the score.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services.embedding_service import EmbeddingService


def _write_thgnn(d: Path, accts: list[str], probas: list[float]) -> None:
    df = pd.DataFrame(
        np.zeros((len(accts), 128), dtype=np.float32),
        columns=[f"thgnn_e{i:03d}" for i in range(128)],
    )
    df.insert(0, "account_id", accts)
    df["thgnn_proba"] = probas
    df.to_parquet(d / "thgnn_embeddings.parquet", index=False)
    json.dump(
        {"version": "HAWKEYE_THGNN_v1", "oof_auc": 0.91, "oof_f1": 0.55},
        (d / "thgnn_metadata.json").open("w"),
    )


def _write_simclr(d: Path, accts: list[str], with_labels: bool = True) -> None:
    rng = np.random.default_rng(0)
    emb = rng.normal(size=(len(accts), 128)).astype(np.float32)
    df = pd.DataFrame(emb, columns=[f"simclr_e{i:03d}" for i in range(128)])
    df.insert(0, "account_id", accts)
    df.to_parquet(d / "simclr_embeddings.parquet", index=False)
    if with_labels:
        y = rng.choice([0, 1, np.nan], size=len(accts), p=[0.6, 0.05, 0.35])
        afm = pd.DataFrame({"account_id": accts, "is_mule": y})
        afm.to_parquet(d / "account_feature_matrix.parquet", index=False)
    json.dump(
        {"version": "HAWKEYE_SIMCLR_v1", "linear_probe_auc": 0.78},
        (d / "simclr_metadata.json").open("w"),
    )


def test_disabled_when_no_artifacts():
    with tempfile.TemporaryDirectory() as td:
        svc = EmbeddingService(td)
        svc.load()
        assert svc.enabled is False
        assert svc.has_thgnn is False
        assert svc.has_simclr is False

        # Fuse must return raw blend unchanged
        fused, comp = svc.fuse(0.42, "ACC_001")
        assert fused == 0.42
        assert comp == {"lgb": 0.42, "thgnn": None, "simclr": None}


def test_thgnn_only_redistributes_simclr_weight():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_thgnn(d, ["A1", "A2"], [0.9, 0.1])
        svc = EmbeddingService(td)
        svc.load()
        assert svc.enabled is True
        assert svc.has_thgnn is True
        assert svc.has_simclr is False
        # SimCLR's share must redirect to lgb so weights still sum to 1.0
        w = svc.fusion_weights
        assert w["simclr"] == 0.0
        assert w["thgnn"] > 0
        assert pytest.approx(w["lgb"] + w["thgnn"] + w["simclr"], abs=1e-6) == 1.0


def test_fuse_with_both_loaded_stays_in_unit_interval():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        accts = [f"A{i:03d}" for i in range(50)]
        _write_thgnn(d, accts, [float(i) / 50 for i in range(50)])
        _write_simclr(d, accts, with_labels=True)

        svc = EmbeddingService(td)
        svc.load()
        assert svc.enabled
        for lgb in [0.0, 0.16, 0.5, 0.99]:
            for aid in ["A005", "A025", "A049"]:
                fused, comp = svc.fuse(lgb, aid)
                assert 0.0 <= fused <= 1.0
                assert comp["lgb"] == pytest.approx(lgb)


def test_fuse_lookup_miss_falls_back_to_lgb_blend():
    """If the account isn't in either embedding index, fuse must NOT depress
    the LightGBM score. This is the critical invariant — embeddings should
    only ever ADD information, never silently drag scores toward 0.
    """
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_thgnn(d, ["KNOWN"], [0.9])
        _write_simclr(d, ["KNOWN"], with_labels=False)

        svc = EmbeddingService(td)
        svc.load()
        # Account that is NOT in either embedding table
        fused, comp = svc.fuse(0.42, "UNKNOWN_ACC")
        assert fused == pytest.approx(0.42)
        assert comp == {"lgb": 0.42, "thgnn": None, "simclr": None}


def test_synthetic_to_real_account_id_bridge():
    """The synthetic event stream uses ACC_<8-digit> while the embedding parquets
    (built from RBI data) use ACCT_<6-digit>. Lookup must accept either form
    and resolve to the same row."""
    from app.services.embedding_service import _alt_account_id

    assert _alt_account_id("ACC_00006204") == "ACCT_006204"
    assert _alt_account_id("ACCT_006204") == "ACC_00006204"
    assert _alt_account_id("ACC_00000000") == "ACCT_000000"
    assert _alt_account_id("EMP_00001234") is None
    assert _alt_account_id("") is None
    assert _alt_account_id("ACCT_garbage") is None

    # End-to-end: lookup against an embedding table keyed only on ACCT_*
    # must succeed when queried with the ACC_* alias.
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_thgnn(d, ["ACCT_006204"], [0.9])
        svc = EmbeddingService(td)
        svc.load()
        # Query with the synthetic alias
        lk = svc.lookup("ACC_00006204")
        assert lk["thgnn_proba"] == 0.9
        # And direct hit still works
        lk2 = svc.lookup("ACCT_006204")
        assert lk2["thgnn_proba"] == 0.9


def test_metadata_propagates_to_readyz_payload():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_thgnn(d, ["A1"], [0.5])
        svc = EmbeddingService(td)
        svc.load()
        m = svc.metadata.to_dict()
        assert m["thgnn_version"] == "HAWKEYE_THGNN_v1"
        assert m["thgnn_oof_auc"] == 0.91
        assert m["n_accounts_thgnn"] == 1
