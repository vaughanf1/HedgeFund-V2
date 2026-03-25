"""Celery task: ingest insider-trading data from FMPConnector into TimescaleDB.

Cache-first: skips tickers where insider trades are already fresh (< 7 days old).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.connectors.fmp import FMPConnector
from app.db.engine import SyncSessionLocal
from app.db.models import InsiderTrade
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)

_DEFAULT_WATCHLIST = "AAPL,MSFT,GOOGL,AMZN,NVDA"
_FRESHNESS_TTL = timedelta(days=7)


@app.task(name="app.tasks.ingest_insider.run", bind=True, max_retries=3)
def run(self: object) -> dict:
    """Fetch insider-trading records for every WATCHLIST ticker and persist to DB.

    Skips a ticker if its most recent insider-trade row is < 7 days old.
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
                    select(InsiderTrade)
                    .where(InsiderTrade.ticker == ticker)
                    .where(InsiderTrade.timestamp >= cutoff)
                    .limit(1)
                )
                fresh = session.execute(stmt).scalars().first()
                if fresh is not None:
                    logger.info("ingest_insider: %s — fresh data found, skipping", ticker)
                    skipped += 1
                    continue

                snapshots = connector.fetch_insider_trades(ticker)

                for snap in snapshots:
                    row = InsiderTrade(
                        timestamp=snap.timestamp,
                        ticker=snap.ticker,
                        insider_name=snap.insider_name,
                        trade_type=snap.trade_type,
                        shares=snap.shares,
                        trade_value=snap.trade_value,
                        source=snap.source,
                    )
                    session.merge(row)
                session.commit()

                count = len(snapshots)
                inserted += count
                logger.info("ingest_insider: %s — upserted %d rows", ticker, count)

        except Exception as exc:  # noqa: BLE001
            logger.error("ingest_insider: %s — error: %s", ticker, exc, exc_info=True)
            errors.append(f"{ticker}: {exc}")

    result = {
        "tickers": len(tickers),
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors,
    }
    logger.info("ingest_insider complete: %s", result)
    return result
