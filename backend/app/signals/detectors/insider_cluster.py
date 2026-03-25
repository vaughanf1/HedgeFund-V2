"""Insider cluster detector (SGNL-03).

Returns a signal dict when 2+ distinct insiders bought within the configured
window (default 30 days), None otherwise.
"""
from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.orm import Session

MIN_INSIDER_CLUSTER_SIZE = int(os.environ.get("MIN_INSIDER_CLUSTER_SIZE", "2"))
INSIDER_CLUSTER_WINDOW_DAYS = int(os.environ.get("INSIDER_CLUSTER_WINDOW_DAYS", "30"))

# NOTE: INTERVAL cannot use a bind parameter directly in PostgreSQL.
# window_days is injected as an f-string literal; min_insiders uses a bind param.
INSIDER_CLUSTER_SQL = text(
    f"""
    SELECT
        ticker,
        COUNT(DISTINCT insider_name) AS unique_buyers,
        SUM(CASE WHEN trade_type = 'buy' THEN shares ELSE 0 END) AS total_shares_bought,
        MIN(timestamp) AS first_buy,
        MAX(timestamp) AS last_buy
    FROM insider_trades
    WHERE ticker = :ticker
      AND trade_type = 'buy'
      AND timestamp >= NOW() - INTERVAL '{INSIDER_CLUSTER_WINDOW_DAYS} days'
    GROUP BY ticker
    HAVING COUNT(DISTINCT insider_name) >= :min_insiders
    """
)


def detect_insider_cluster(session: Session, ticker: str) -> dict | None:
    """Return an insider cluster signal dict when 2+ distinct insiders bought, else None."""
    row = session.execute(
        INSIDER_CLUSTER_SQL,
        {"ticker": ticker, "min_insiders": MIN_INSIDER_CLUSTER_SIZE},
    ).fetchone()

    if row is None:
        return None

    unique_buyers = int(row.unique_buyers)

    # Normalize: 4+ insiders = max score
    score = min(unique_buyers / 4.0, 1.0)

    return {
        "signal_type": "insider_cluster",
        "ticker": ticker,
        "score": score,
        "detail": {
            "unique_buyers": unique_buyers,
            "total_shares_bought": int(row.total_shares_bought) if row.total_shares_bought is not None else 0,
            "first_buy": str(row.first_buy) if row.first_buy is not None else None,
            "last_buy": str(row.last_buy) if row.last_buy is not None else None,
            "window_days": INSIDER_CLUSTER_WINDOW_DAYS,
            "min_cluster_size": MIN_INSIDER_CLUSTER_SIZE,
        },
    }
