"""Price breakout detector (SGNL-02).

Returns a signal dict on a 20-day high/low breakout or gap move, None otherwise.
"""
from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.orm import Session

GAP_THRESHOLD = float(os.environ.get("GAP_THRESHOLD", "0.03"))

PRICE_BREAKOUT_SQL = text(
    """
    WITH windowed AS (
        SELECT
            ticker,
            timestamp,
            close,
            MAX(close) OVER (
                PARTITION BY ticker
                ORDER BY timestamp
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
            ) AS high_20d,
            MIN(close) OVER (
                PARTITION BY ticker
                ORDER BY timestamp
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
            ) AS low_20d,
            LAG(close) OVER (PARTITION BY ticker ORDER BY timestamp) AS prev_close
        FROM price_ohlcv
        WHERE ticker = :ticker
          AND timestamp >= NOW() - INTERVAL '30 days'
        ORDER BY timestamp DESC
        LIMIT 1
    )
    SELECT
        ticker,
        timestamp,
        close,
        high_20d,
        low_20d,
        prev_close,
        CASE
            WHEN close > high_20d THEN 'breakout_up'
            WHEN close < low_20d  THEN 'breakout_down'
            WHEN prev_close IS NOT NULL
                 AND (close - prev_close) / NULLIF(prev_close, 0) > :gap_threshold
                 THEN 'gap_up'
            WHEN prev_close IS NOT NULL
                 AND (close - prev_close) / NULLIF(prev_close, 0) < -:gap_threshold
                 THEN 'gap_down'
            ELSE NULL
        END AS breakout_type
    FROM windowed
    LIMIT 1
    """
)

_BREAKOUT_SCORES = {
    "breakout_up": 0.8,
    "breakout_down": 0.8,
    "gap_up": 0.6,
    "gap_down": 0.6,
}


def detect_price_breakout(session: Session, ticker: str) -> dict | None:
    """Return a price breakout signal dict if a breakout or gap is detected, else None."""
    row = session.execute(
        PRICE_BREAKOUT_SQL,
        {"ticker": ticker, "gap_threshold": GAP_THRESHOLD},
    ).fetchone()

    if row is None:
        return None

    breakout_type = row.breakout_type
    if breakout_type is None:
        return None

    score = _BREAKOUT_SCORES.get(breakout_type, 0.5)

    return {
        "signal_type": "price_breakout",
        "ticker": ticker,
        "score": score,
        "detail": {
            "breakout_type": breakout_type,
            "close": float(row.close) if row.close is not None else None,
            "high_20d": float(row.high_20d) if row.high_20d is not None else None,
            "low_20d": float(row.low_20d) if row.low_20d is not None else None,
            "prev_close": float(row.prev_close) if row.prev_close is not None else None,
            "gap_threshold": GAP_THRESHOLD,
            "timestamp": str(row.timestamp),
        },
    }
