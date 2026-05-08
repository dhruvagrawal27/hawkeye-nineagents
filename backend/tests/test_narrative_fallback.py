"""Narrative fallback path — verify it produces a valid memo without Groq."""

import pytest

from app.services.narrative_service import _audit_footer, _fallback_narrative


def test_fallback_contains_all_four_sections():
    body = _fallback_narrative(
        employee_id="EMP_TEST",
        score=0.92,
        risk_level="CRITICAL",
        factors=[
            {
                "name": "pass_rate",
                "name_human": "Balance pass-through rate",
                "value": 0.97,
                "value_human": "97%",
                "contribution": 0.31,
                "normal": "<5%",
            }
        ],
        behaviour={
            "n_txn": 388,
            "pass_rate_pct": 97,
            "pngt_pct": 69,
            "ps49_pct": 17,
            "fan_ratio": 6.2,
            "shared_systems": 3,
            "flagged_peers": 2,
        },
    )
    for header in ("**Risk Summary**", "**What We Observed**", "**Why It Matters**", "**Recommended Next Step**"):
        assert header in body, f"missing header: {header}"
    assert "Audit trail" in body
    assert "EMP_TEST" in body


def test_audit_footer_contains_factor_lines():
    footer = _audit_footer(
        [
            {"name": "g_ncp", "name_human": "Graph counterparty count", "value": 40, "contribution": 0.26},
            {"name": "ps49", "name_human": "Structuring share", "value": 0.17, "contribution": 0.22},
        ]
    )
    assert "g_ncp" in footer
    assert "0.260" in footer or "+0.2600" in footer
    assert "Structuring" in footer


def test_fallback_works_with_empty_factors():
    body = _fallback_narrative(
        employee_id="EMP_EMPTY",
        score=0.5,
        risk_level="MEDIUM",
        factors=[],
        behaviour={},
    )
    assert "EMP_EMPTY" in body
    assert "Audit trail" in body
