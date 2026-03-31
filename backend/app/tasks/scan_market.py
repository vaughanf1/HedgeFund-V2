"""Market scanner Celery task (SGNL-08 — complete).

Iterates the watchlist, runs all five signal detectors, computes a composite
score, applies the quality gate, and persists signals to the detected_signals
hypertable. Writes Redis instrumentation keys at end of each scan.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import redis

from app.db.engine import SyncSessionLocal
from app.db.models import DetectedSignal
from app.signals.detectors.insider_cluster import detect_insider_cluster
from app.signals.detectors.news_catalyst import detect_news_catalyst
from app.signals.detectors.price_breakout import detect_price_breakout
from app.signals.detectors.sector_momentum import detect_sector_momentum
from app.signals.detectors.volume_spike import detect_volume_spike
from app.signals.quality_gate import passes_gate
from app.signals.queue import enqueue_opportunity
from app.signals.scorer import compute_composite_score
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)

_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
_INSTRUMENTATION_TTL = 3600  # 1 hour


def _parse_watchlist() -> list[str]:
    raw = os.environ.get("WATCHLIST", "SMR,OKLO,LEU,NNE,VST,IONQ,RGTI,QUBT,PLTR,RKLB,SMCI,VRT,CRSP,FSLR,CCJ,LUNR,ANET,NBIS,HIMS,KULR")
    return [t.strip() for t in raw.split(",") if t.strip()]


@app.task(name="app.tasks.scan_market.run", bind=True, max_retries=2)
def run(self) -> dict:  # type: ignore[override]
    """Scan watchlist tickers, detect signals, score, gate, and persist."""
    r = redis.from_url(_REDIS_URL)

    watchlist = _parse_watchlist()
    passed = 0
    rejected = 0
    enqueued_count = 0
    errors: list[str] = []

    with SyncSessionLocal() as session:
        detected_at = datetime.now(tz=timezone.utc)

        for ticker in watchlist:
            try:
                raw_signals: list[dict] = []

                for result in [
                    detect_volume_spike(session, ticker),
                    detect_price_breakout(session, ticker),
                    detect_sector_momentum(session, ticker, watchlist),
                    detect_insider_cluster(session, ticker),
                    detect_news_catalyst(session, ticker),
                ]:
                    if result is not None:
                        raw_signals.append(result)

                if raw_signals:
                    composite = compute_composite_score(raw_signals)
                    gate_passed = passes_gate(composite)
                else:
                    composite = 0.0
                    gate_passed = False

                if gate_passed:
                    passed += 1
                    enqueued = enqueue_opportunity(
                        r,
                        ticker,
                        {
                            "ticker": ticker,
                            "composite_score": composite,
                            "signals": raw_signals,
                            "detected_at": detected_at.isoformat(),
                        },
                    )
                    if enqueued:
                        enqueued_count += 1
                        logger.info("scan_market: enqueued opportunity — %s", ticker)
                    else:
                        logger.info(
                            "scan_market: duplicate — skipped enqueue for %s", ticker
                        )
                else:
                    rejected += 1

                for signal in raw_signals:
                    record = DetectedSignal(
                        detected_at=detected_at,
                        ticker=signal["ticker"],
                        signal_type=signal["signal_type"],
                        score=signal["score"],
                        composite_score=composite,
                        passed_gate=gate_passed,
                        detail=json.dumps(signal.get("detail")),
                        source="scanner",
                    )
                    session.merge(record)

            except Exception as exc:  # noqa: BLE001
                msg = f"{ticker}: {exc}"
                logger.error("scan_market error — %s", msg)
                errors.append(msg)

        session.commit()

    total = len(watchlist)
    pass_rate = round(passed / total, 4) if total > 0 else 0.0

    try:
        r.setex("scanner:last_pass_rate", _INSTRUMENTATION_TTL, str(pass_rate))
        r.setex("scanner:last_scan_at", _INSTRUMENTATION_TTL, detected_at.isoformat())
        r.setex("scanner:last_total", _INSTRUMENTATION_TTL, str(total))
    except Exception as exc:  # noqa: BLE001
        logger.warning("scan_market: Redis instrumentation write failed — %s", exc)

    logger.info(
        "scan_market complete — tickers=%d passed=%d rejected=%d enqueued=%d errors=%d pass_rate=%.2f",
        total,
        passed,
        rejected,
        enqueued_count,
        len(errors),
        pass_rate,
    )

    return {
        "tickers": total,
        "passed": passed,
        "rejected": rejected,
        "enqueued": enqueued_count,
        "errors": errors,
    }
