"""Volume spike detector (SGNL-01).

Returns a signal dict when a ticker's latest volume z-score exceeds
VOLUME_ZSCORE_THRESHOLD (default 2.0), None otherwise.
"""
from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.orm import Session

VOLUME_ZSCORE_THRESHOLD = float(os.environ.get("VOLUME_ZSCORE_THRESHOLD", "2.0"))

VOLUME_SPIKE_SQL = text(
    """
    WITH recent AS (
        SELECT
            ticker,
            timestamp,
            volume,
            AVG(volume) OVER (
                PARTITION BY ticker
                ORDER BY timestamp
                ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
            ) AS avg_vol_20d,
            STDDEV_SAMP(volume) OVER (
                PARTITION BY ticker
                ORDER BY timestamp
                ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
            ) AS std_vol_20d
        FROM price_ohlcv
        WHERE ticker = :ticker
          AND timestamp >= NOW() - INTERVAL '30 days'
    ),
    latest AS (
        SELECT
            ticker,
            timestamp,
            volume,
            avg_vol_20d,
            std_vol_20d,
            (volume - avg_vol_20d) / NULLIF(std_vol_20d, 0) AS z_score
        FROM recent
        ORDER BY timestamp DESC
        LIMIT 1
    )
    SELECT ticker, timestamp, volume, avg_vol_20d, std_vol_20d, z_score
    FROM latest
    WHERE z_score >= :threshold
    """
)


def detect_volume_spike(session: Session, ticker: str) -> dict | None:
    """Return a volume spike signal dict if z-score exceeds threshold, else None."""
    row = session.execute(
        VOLUME_SPIKE_SQL,
        {"ticker": ticker, "threshold": VOLUME_ZSCORE_THRESHOLD},
    ).fetchone()

    if row is None:
        return None

    z_score = row.z_score
    if z_score is None:
        return None

    return {
        "signal_type": "volume_spike",
        "ticker": ticker,
        "score": min(float(z_score) / 3.0, 1.0),
        "detail": {
            "z_score": float(z_score),
            "volume": int(row.volume) if row.volume is not None else None,
            "avg_vol_20d": float(row.avg_vol_20d) if row.avg_vol_20d is not None else None,
            "std_vol_20d": float(row.std_vol_20d) if row.std_vol_20d is not None else None,
            "timestamp": str(row.timestamp),
            "threshold": VOLUME_ZSCORE_THRESHOLD,
        },
    }
