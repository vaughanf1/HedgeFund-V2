"""MassiveConnector — wraps the Massive.com (Polygon.io-compatible) REST API.

Massive.com exposes a Polygon-compatible REST interface. This connector calls
it synchronously via httpx so it can be used directly from Celery tasks.

NOTE: OHLCV and News are supported. Fundamentals and InsiderTrades are not
available on this feed — use FMPConnector for those.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.connectors.base import DataConnector
from app.schemas.financial import FinancialSnapshot

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.massive.com/v2"  # Polygon-compatible endpoint


class MassiveConnector(DataConnector):
    """Concrete connector for the Massive.com market-data feed."""

    def __init__(self) -> None:
        self.api_key = os.environ["MASSIVE_API_KEY"]
        self._client = httpx.Client(
            base_url=_BASE_URL,
            timeout=30.0,
            params={"apiKey": self.api_key},
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def fetch_ohlcv(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[FinancialSnapshot]:
        """Fetch daily OHLCV bars from Massive.com (Polygon /aggs endpoint)."""
        url = f"/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
        logger.debug("MassiveConnector.fetch_ohlcv %s %s→%s", ticker, from_date, to_date)

        response = self._client.get(url, params={"adjusted": "true", "sort": "asc"})
        response.raise_for_status()
        data = response.json()

        results: list[FinancialSnapshot] = []
        for agg in data.get("results") or []:
            ts_ms = agg.get("t", 0)
            ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            results.append(
                FinancialSnapshot(
                    ticker=ticker,
                    timestamp=ts,
                    data_type="ohlcv",
                    source="massive",
                    open=Decimal(str(agg["o"])) if agg.get("o") is not None else None,
                    high=Decimal(str(agg["h"])) if agg.get("h") is not None else None,
                    low=Decimal(str(agg["l"])) if agg.get("l") is not None else None,
                    close=Decimal(str(agg["c"])) if agg.get("c") is not None else None,
                    price=Decimal(str(agg["c"])) if agg.get("c") is not None else None,
                    volume=int(agg["v"]) if agg.get("v") is not None else None,
                )
            )
        logger.info("MassiveConnector.fetch_ohlcv %s: %d bars", ticker, len(results))
        return results

    def fetch_fundamentals(
        self,
        ticker: str,
    ) -> list[FinancialSnapshot]:
        raise NotImplementedError("MassiveConnector does not support fundamentals — use FMPConnector.")

    def fetch_insider_trades(
        self,
        ticker: str,
        limit: int = 50,
    ) -> list[FinancialSnapshot]:
        raise NotImplementedError("MassiveConnector does not support insider trades — use FMPConnector.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def fetch_news(
        self,
        ticker: str,
        limit: int = 20,
    ) -> list[FinancialSnapshot]:
        """Fetch recent news articles from Massive.com (Polygon /reference/news endpoint)."""
        url = "/reference/news"
        logger.debug("MassiveConnector.fetch_news %s limit=%d", ticker, limit)

        response = self._client.get(url, params={"ticker": ticker, "limit": limit, "order": "desc"})
        response.raise_for_status()
        data = response.json()

        results: list[FinancialSnapshot] = []
        for item in data.get("results") or []:
            published_utc = item.get("published_utc", "")
            try:
                ts = datetime.fromisoformat(published_utc.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ts = datetime.now(tz=timezone.utc)

            # A single article may mention multiple tickers — only keep this ticker's row.
            results.append(
                FinancialSnapshot(
                    ticker=ticker,
                    timestamp=ts,
                    data_type="news",
                    source="massive",
                    headline=item.get("title"),
                    summary=item.get("description"),
                    article_url=item.get("article_url"),
                )
            )
        logger.info("MassiveConnector.fetch_news %s: %d items", ticker, len(results))
        return results
