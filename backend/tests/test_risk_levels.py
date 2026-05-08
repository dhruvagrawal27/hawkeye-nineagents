"""Risk-level band correctness."""

import pytest

from app.services.risk_levels import RiskBands, score_to_display, score_to_level

THRESHOLD = 0.16032509


@pytest.mark.parametrize(
    "score,expected_level",
    [
        (0.00, "LOW"),
        (0.10, "LOW"),
        (THRESHOLD - 0.001, "LOW"),
        (THRESHOLD, "MEDIUM"),
        (THRESHOLD + 0.005, "MEDIUM"),
        (THRESHOLD + 0.01, "HIGH"),
        (THRESHOLD + 0.015, "HIGH"),
        (THRESHOLD + 0.025, "CRITICAL"),
        (0.99, "CRITICAL"),
    ],
)
def test_score_to_level(score, expected_level):
    assert score_to_level(score, THRESHOLD) == expected_level


def test_display_score_monotone_in_threshold_band():
    """Display score must be non-decreasing in raw score."""
    prev = -1.0
    for raw in [0.0, 0.05, THRESHOLD * 0.5, THRESHOLD - 0.001, THRESHOLD, THRESHOLD + 0.005, THRESHOLD + 0.01, THRESHOLD + 0.02, 0.5]:
        d = score_to_display(raw, THRESHOLD)
        assert d >= prev, f"display non-monotone at raw={raw}: {d} < {prev}"
        prev = d


def test_display_score_clamped_to_unit_interval():
    assert score_to_display(0.0, THRESHOLD) == 0.0
    assert 0.0 <= score_to_display(0.5, THRESHOLD) <= 1.0
    assert score_to_display(THRESHOLD, THRESHOLD) == pytest.approx(0.5, abs=0.01)


def test_riskbands_ordering():
    b = RiskBands(threshold=THRESHOLD)
    assert b.low_high < b.medium_low < b.high_low < b.critical_low
