"""Celery task: ingest OHLCV price data from MassiveConnector into TimescaleDB."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta

from app.connectors.massive import MassiveConnector
from app.db.engine import SyncSessionLocal
from app.db.models import PriceOHLCV
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)

_DEFAULT_WATCHLIST = "AAPL,MSFT,GOOGL,AMZN,NVDA"


@app.task(name="app.tasks.ingest_price.run", bind=True, max_retries=3)
def run(self: object, days_back: int = 1) -> dict:
    """Fetch OHLCV bars for every ticker in WATCHLIST and upsert into DB.

    Args:
        days_back: Number of days of history to fetch (default 1 = yesterday only).
    """
    watchlist_raw = os.environ.get("WATCHLIST", _DEFAULT_WATCHLIST)
    tickers = [t.strip() for t in watchlist_raw.split(",") if t.strip()]

    today = date.today()
    yesterday = today - timedelta(days=days_back)

    connector = MassiveConnector()
    total_rows = 0
    errors: list[str] = []

    for ticker in tickers:
        try:
            snapshots = connector.fetch_ohlcv(ticker, from_date=yesterday, to_date=today)

            with SyncSessionLocal() as session:
                for snap in snapshots:
                    row = PriceOHLCV(
                        timestamp=snap.timestamp,
                        ticker=snap.ticker,
                        open=snap.open,
                        high=snap.high,
                        low=snap.low,
                        close=snap.close,
                        volume=snap.volume,
                        source=snap.source,
                    )
                    session.merge(row)
                session.commit()

            count = len(snapshots)
            total_rows += count
            logger.info("ingest_price: %s — upserted %d rows", ticker, count)

        except Exception as exc:  # noqa: BLE001
            logger.error("ingest_price: %s — error: %s", ticker, exc, exc_info=True)
            errors.append(f"{ticker}: {exc}")

    result = {"tickers": len(tickers), "rows_upserted": total_rows, "errors": errors}
    logger.info("ingest_price complete: %s", result)
    return result
