"""Celery task: ingest fundamental data from FMPConnector into TimescaleDB.

Cache-first: skips tickers where fundamentals are already fresh (< 24 h old).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.connectors.fmp import FMPConnector
from app.db.engine import SyncSessionLocal
from app.db.models import Fundamentals
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)

_DEFAULT_WATCHLIST = "AAPL,MSFT,GOOGL,AMZN,NVDA"
_FRESHNESS_TTL = timedelta(hours=24)


@app.task(name="app.tasks.ingest_fundamentals.run", bind=True, max_retries=3)
def run(self: object) -> dict:
    """Fetch fundamental ratios for every WATCHLIST ticker and persist to DB.

    Skips a ticker if its most recent fundamentals row is < 24 hours old.
    """
    watchlist_raw = os.environ.get("WATCHLIST", _DEFAULT_WATCHLIST)
    tickers = [t.strip() for t in watchlist_raw.split(",") if t.strip()]

    connector = FMPConnector()
    cutoff = datetime.now(tz=timezone.utc) - _FRESHNESS_TTL
    skipped = 0
    inserted = 0
    errors: list[str] = []

    for ticker in tickers:
        try:
            with SyncSessionLocal() as session:
                # Cache-first: is there a fresh row?
                stmt = (
                    select(Fundamentals)
                    .where(Fundamentals.ticker == ticker)
                    .where(Fundamentals.timestamp >= cutoff)
                    .limit(1)
                )
                fresh = session.execute(stmt).scalars().first()
                if fresh is not None:
                    logger.info("ingest_fundamentals: %s — fresh data found, skipping", ticker)
                    skipped += 1
                    continue

                snapshots = connector.fetch_fundamentals(ticker)

                for snap in snapshots:
                    row = Fundamentals(
                        timestamp=snap.timestamp,
                        ticker=snap.ticker,
                        pe_ratio=snap.pe_ratio,
                        revenue=snap.revenue,
                        net_income=snap.net_income,
                        eps=snap.eps,
                        debt_to_equity=snap.debt_to_equity,
                        free_cash_flow=snap.free_cash_flow,
                        market_cap=snap.market_cap,
                        source=snap.source,
                    )
                    session.merge(row)
                session.commit()

                count = len(snapshots)
                inserted += count
                logger.info("ingest_fundamentals: %s — upserted %d rows", ticker, count)

        except Exception as exc:  # noqa: BLE001
            logger.error("ingest_fundamentals: %s — error: %s", ticker, exc, exc_info=True)
            errors.append(f"{ticker}: {exc}")

    result = {
        "tickers": len(tickers),
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors,
    }
    logger.info("ingest_fundamentals complete: %s", result)
    return result
