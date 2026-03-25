"""Composite signal scorer (SGNL-06).

Produces a weighted 0.0-1.0 composite score from all fired signals for a ticker.
Weights are env-var configurable; unrecognised signal types contribute 0 weight.
"""
from __future__ import annotations

import os

WEIGHTS: dict[str, float] = {
    "volume_spike": float(os.environ.get("WEIGHT_VOLUME_SPIKE", "0.25")),
    "price_breakout": float(os.environ.get("WEIGHT_PRICE_BREAKOUT", "0.25")),
    "insider_cluster": float(os.environ.get("WEIGHT_INSIDER_CLUSTER", "0.20")),
    "news_catalyst": float(os.environ.get("WEIGHT_NEWS_CATALYST", "0.20")),
    "sector_momentum": float(os.environ.get("WEIGHT_SECTOR_MOMENTUM", "0.10")),
}


def compute_composite_score(signals: list[dict]) -> float:
    """Return a weighted composite score in [0.0, 1.0] for the given fired signals.

    Only signals whose signal_type is in WEIGHTS contribute to the score.
    An empty signals list (or all unknown types) returns 0.0.
    """
    if not signals:
        return 0.0

    total_weight = sum(
        WEIGHTS[s["signal_type"]]
        for s in signals
        if s["signal_type"] in WEIGHTS
    )

    if total_weight == 0:
        return 0.0

    weighted_sum = sum(
        s["score"] * WEIGHTS.get(s["signal_type"], 0.0) for s in signals
    )

    return weighted_sum / total_weight
