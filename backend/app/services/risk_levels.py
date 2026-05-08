"""Risk-level bands relative to the trained threshold.

Empirically the LightGBM full-data blend lives in [0.026, 0.190] for our dataset
with threshold 0.16032509. Display scores are rescaled to [0, 1] for UI gauges.
Constants live here so backend, frontend (via /stats/overview), and tests agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


@dataclass(frozen=True)
class RiskBands:
    threshold: float

    @property
    def low_high(self) -> float:
        return self.threshold * 0.5

    @property
    def medium_low(self) -> float:
        return self.threshold

    @property
    def high_low(self) -> float:
        return self.threshold + 0.01

    @property
    def critical_low(self) -> float:
        return self.threshold + 0.02


def score_to_level(score: float, threshold: float) -> RiskLevel:
    bands = RiskBands(threshold=threshold)
    if score >= bands.critical_low:
        return "CRITICAL"
    if score >= bands.high_low:
        return "HIGH"
    if score >= bands.medium_low:
        return "MEDIUM"
    return "LOW"


def score_to_display(score: float, threshold: float) -> float:
    """Piecewise-linear rescale of raw score → [0, 1] for the UI gauge.

    < 0.5 * threshold     → linearly maps [0, 0.5*threshold) → [0.0, 0.30]
    0.5*threshold..thresh → maps to [0.30, 0.50]
    thresh..thresh+0.01   → maps to [0.50, 0.70]
    thresh+0.01..+0.02    → maps to [0.70, 0.85]
    >= thresh + 0.02      → maps to [0.85, 1.00] (clamped at 1.0 by score=thresh+0.05)
    """
    bands = RiskBands(threshold=threshold)
    s = max(score, 0.0)
    if s < bands.low_high:
        return _lerp(s, 0.0, bands.low_high, 0.0, 0.30)
    if s < bands.medium_low:
        return _lerp(s, bands.low_high, bands.medium_low, 0.30, 0.50)
    if s < bands.high_low:
        return _lerp(s, bands.medium_low, bands.high_low, 0.50, 0.70)
    if s < bands.critical_low:
        return _lerp(s, bands.high_low, bands.critical_low, 0.70, 0.85)
    return min(_lerp(s, bands.critical_low, bands.critical_low + 0.03, 0.85, 1.0), 1.0)


def _lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x1 <= x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + max(0.0, min(1.0, t)) * (y1 - y0)
