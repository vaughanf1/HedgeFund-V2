"""Sector momentum detector (SGNL-05).

Returns a signal dict when a ticker's 5-day return exceeds its sector median
return by SECTOR_MOMENTUM_THRESHOLD, None otherwise.
"""
from __future__ import annotations

import json
import os
import statistics

from sqlalchemy import text
from sqlalchemy.orm import Session

SECTOR_MAP: dict[str, str] = json.loads(os.environ.get("SECTOR_MAP", "{}"))
SECTOR_MOMENTUM_THRESHOLD = float(
    os.environ.get("SECTOR_MOMENTUM_THRESHOLD", "0.02")
)
SECTOR_MIN_COVERAGE = float(os.environ.get("SECTOR_MIN_COVERAGE", "0.6"))

RETURN_5D_SQL = text(
    """
    WITH ranked AS (
        SELECT
            ticker,
            close,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY timestamp DESC) AS rn
        FROM price_ohlcv
        WHERE ticker = ANY(:tickers)
          AND timestamp >= NOW() - INTERVAL '10 days'
    ),
    endpoints AS (
        SELECT ticker, rn, close
        FROM ranked
        WHERE rn IN (1, 6)
    ),
    latest AS (
        SELECT ticker, close AS close_now FROM endpoints WHERE rn = 1
    ),
    prior AS (
        SELECT ticker, close AS close_5d_ago FROM endpoints WHERE rn = 6
    )
    SELECT
        l.ticker,
        (l.close_now - p.close_5d_ago) / NULLIF(p.close_5d_ago, 0) AS return_5d
    FROM latest l
    JOIN prior p ON l.ticker = p.ticker
    WHERE p.close_5d_ago IS NOT NULL
    """
)


def detect_sector_momentum(
    session: Session, ticker: str, watchlist: list[str]
) -> dict | None:
    """Return a sector momentum signal dict if ticker outperforms its sector peers, else None."""
    sector = SECTOR_MAP.get(ticker)
    if sector is None:
        return None

    sector_peers = [t for t in watchlist if SECTOR_MAP.get(t) == sector]
    if not sector_peers:
        return None

    rows = session.execute(
        RETURN_5D_SQL,
        {"tickers": sector_peers},
    ).fetchall()

    returns_by_ticker: dict[str, float] = {}
    for row in rows:
        if row.return_5d is not None:
            returns_by_ticker[row.ticker] = float(row.return_5d)

    min_required = SECTOR_MIN_COVERAGE * len(sector_peers)
    if len(returns_by_ticker) < min_required:
        return None

    ticker_return = returns_by_ticker.get(ticker)
    if ticker_return is None:
        return None

    peer_returns = list(returns_by_ticker.values())
    sector_median = statistics.median(peer_returns)

    if ticker_return - sector_median < SECTOR_MOMENTUM_THRESHOLD:
        return None

    raw_score = (ticker_return - sector_median) / 0.05
    score = min(raw_score, 1.0)

    return {
        "signal_type": "sector_momentum",
        "ticker": ticker,
        "score": score,
        "detail": {
            "ticker_return": ticker_return,
            "sector_median": sector_median,
            "sector": sector,
            "peers_with_data": len(returns_by_ticker),
            "total_peers": len(sector_peers),
            "threshold": SECTOR_MOMENTUM_THRESHOLD,
        },
    }
