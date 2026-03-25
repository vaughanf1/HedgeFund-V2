"""Market scanner Celery task (SGNL-08 — partial).

Iterates the watchlist, runs all signal detectors, and persists raw signals
to the detected_signals hypertable. Scorer and gate are added in Plan 02.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from app.db.engine import SyncSessionLocal
from app.db.models import DetectedSignal
from app.signals.detectors.price_breakout import detect_price_breakout
from app.signals.detectors.sector_momentum import detect_sector_momentum
from app.signals.detectors.volume_spike import detect_volume_spike
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)


def _parse_watchlist() -> list[str]:
    raw = os.environ.get("WATCHLIST", "AAPL,MSFT,GOOGL,AMZN,NVDA")
    return [t.strip() for t in raw.split(",") if t.strip()]


@app.task(name="app.tasks.scan_market.run", bind=True, max_retries=2)
def run(self) -> dict:  # type: ignore[override]
    """Scan watchlist tickers, detect signals, and persist raw signals to DB."""
    watchlist = _parse_watchlist()
    signals_detected = 0
    errors: list[str] = []

    with SyncSessionLocal() as session:
        detected_at = datetime.now(tz=timezone.utc)

        for ticker in watchlist:
            try:
                detectors = [
                    detect_volume_spike(session, ticker),
                    detect_price_breakout(session, ticker),
                    detect_sector_momentum(session, ticker, watchlist),
                ]

                for signal in detectors:
                    if signal is None:
                        continue

                    record = DetectedSignal(
                        detected_at=detected_at,
                        ticker=signal["ticker"],
                        signal_type=signal["signal_type"],
                        score=signal["score"],
                        composite_score=None,   # scorer added in Plan 02
                        passed_gate=False,       # gate added in Plan 02
                        detail=json.dumps(signal.get("detail")),
                        source="scanner",
                    )
                    session.merge(record)
                    signals_detected += 1

            except Exception as exc:  # noqa: BLE001
                msg = f"{ticker}: {exc}"
                logger.error("scan_market error — %s", msg)
                errors.append(msg)

        session.commit()

    logger.info(
        "scan_market complete — tickers=%d signals=%d errors=%d",
        len(watchlist),
        signals_detected,
        len(errors),
    )

    return {
        "tickers": len(watchlist),
        "signals_detected": signals_detected,
        "errors": errors,
    }
