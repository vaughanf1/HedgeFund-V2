"""Celery task: ingest news from both MassiveConnector and FMPConnector into TimescaleDB.

Deduplicates by headline before insert to avoid duplicate rows from overlapping sources.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from app.connectors.fmp import FMPConnector
from app.connectors.massive import MassiveConnector
from app.db.engine import SyncSessionLocal
from app.db.models import NewsItem
from app.schemas.financial import FinancialSnapshot
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)

_DEFAULT_WATCHLIST = "AAPL,MSFT,GOOGL,AMZN,NVDA"


def _dedup(snapshots: list[FinancialSnapshot]) -> list[FinancialSnapshot]:
    """Deduplicate snapshots by headline (case-insensitive). First occurrence wins."""
    seen: set[str] = set()
    result: list[FinancialSnapshot] = []
    for snap in snapshots:
        key = (snap.headline or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(snap)
        elif not key:
            # No headline — keep it (can't deduplicate without a key)
            result.append(snap)
    return result


@app.task(name="app.tasks.ingest_news.run", bind=True, max_retries=3)
def run(self: object) -> dict:
    """Fetch news for every WATCHLIST ticker from Massive + FMP, deduplicate, and persist."""
    watchlist_raw = os.environ.get("WATCHLIST", _DEFAULT_WATCHLIST)
    tickers = [t.strip() for t in watchlist_raw.split(",") if t.strip()]

    massive = MassiveConnector()
    fmp = FMPConnector()
    total_inserted = 0
    total_dupes = 0
    errors: list[str] = []

    for ticker in tickers:
        try:
            all_snapshots: list[FinancialSnapshot] = []

            # Fetch from Massive
            try:
                all_snapshots.extend(massive.fetch_news(ticker))
            except Exception as exc:  # noqa: BLE001
                logger.warning("ingest_news: %s Massive fetch failed: %s", ticker, exc)

            # Fetch from FMP
            try:
                all_snapshots.extend(fmp.fetch_news(ticker))
            except Exception as exc:  # noqa: BLE001
                logger.warning("ingest_news: %s FMP fetch failed: %s", ticker, exc)

            before_dedup = len(all_snapshots)
            unique_snapshots = _dedup(all_snapshots)
            dupes = before_dedup - len(unique_snapshots)
            total_dupes += dupes

            with SyncSessionLocal() as session:
                for snap in unique_snapshots:
                    row = NewsItem(
                        timestamp=snap.timestamp,
                        ticker=snap.ticker,
                        headline=snap.headline,
                        summary=snap.summary,
                        article_url=snap.article_url,
                        source=snap.source,
                    )
                    session.merge(row)
                session.commit()

            count = len(unique_snapshots)
            total_inserted += count
            logger.info(
                "ingest_news: %s — inserted %d items (%d dupes removed)", ticker, count, dupes
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("ingest_news: %s — error: %s", ticker, exc, exc_info=True)
            errors.append(f"{ticker}: {exc}")

    result = {
        "tickers": len(tickers),
        "inserted": total_inserted,
        "duplicates_removed": total_dupes,
        "errors": errors,
    }
    logger.info("ingest_news complete: %s", result)
    return result
