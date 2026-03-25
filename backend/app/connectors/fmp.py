"""FMPConnector — wraps the Financial Modeling Prep (FMP) REST API.

FMP provides fundamentals, insider trades, and news. OHLCV is not implemented
here — use MassiveConnector for price data.

IMPORTANT: FMP endpoint paths are verified against the v3 public docs as of
2024. Always verify against live FMP documentation if responses change.
Confidence: MEDIUM — endpoint paths marked "verify against live docs" below.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.connectors.base import DataConnector
from app.schemas.financial import FinancialSnapshot

logger = logging.getLogger(__name__)

_BASE_URL = "https://financialmodelingprep.com/api/v3"


def _to_decimal(value: object) -> Decimal | None:
    """Safely convert a value to Decimal; return None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


class FMPConnector(DataConnector):
    """Concrete connector for the Financial Modeling Prep data feed."""

    def __init__(self) -> None:
        self.api_key = os.environ["FMP_API_KEY"]
        self._client = httpx.Client(
            base_url=_BASE_URL,
            timeout=30.0,
        )

    def _get(self, path: str, **params: object) -> dict | list:
        """Perform a GET request; always injects apikey."""
        params["apikey"] = self.api_key
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_ohlcv(
        self,
        ticker: str,
        from_date: object = None,
        to_date: object = None,
    ) -> list[FinancialSnapshot]:
        raise NotImplementedError("FMPConnector does not support OHLCV — use MassiveConnector.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def fetch_fundamentals(
        self,
        ticker: str,
    ) -> list[FinancialSnapshot]:
        """Fetch TTM ratios + latest income statement + balance sheet for *ticker*.

        Endpoint paths (verify against live FMP docs):
        - GET /ratios-ttm/{ticker}
        - GET /income-statement/{ticker}?limit=1
        - GET /balance-sheet-statement/{ticker}?limit=1
        """
        logger.debug("FMPConnector.fetch_fundamentals %s", ticker)

        ratios_data = self._get(f"/ratios-ttm/{ticker}")
        income_data = self._get(f"/income-statement/{ticker}", limit=1)
        balance_data = self._get(f"/balance-sheet-statement/{ticker}", limit=1)

        # Each endpoint returns a list; take first element if available.
        ratios = ratios_data[0] if isinstance(ratios_data, list) and ratios_data else {}
        income = income_data[0] if isinstance(income_data, list) and income_data else {}
        balance = balance_data[0] if isinstance(balance_data, list) and balance_data else {}

        # Use the income statement date as the snapshot timestamp; fall back to now.
        raw_date = income.get("date") or balance.get("date")
        if raw_date:
            try:
                ts = datetime.fromisoformat(str(raw_date)).replace(tzinfo=timezone.utc)
            except ValueError:
                ts = datetime.now(tz=timezone.utc)
        else:
            ts = datetime.now(tz=timezone.utc)

        snapshot = FinancialSnapshot(
            ticker=ticker,
            timestamp=ts,
            data_type="fundamentals",
            source="fmp",
            pe_ratio=_to_decimal(ratios.get("peRatioTTM")),
            revenue=_to_decimal(income.get("revenue")),
            net_income=_to_decimal(income.get("netIncome")),
            eps=_to_decimal(ratios.get("epsTTM") or income.get("eps")),
            debt_to_equity=_to_decimal(
                ratios.get("debtEquityRatioTTM") or balance.get("totalDebt")
            ),
            free_cash_flow=_to_decimal(ratios.get("freeCashFlowPerShareTTM")),
            market_cap=_to_decimal(ratios.get("marketCapTTM")),
        )
        logger.info("FMPConnector.fetch_fundamentals %s: snapshot at %s", ticker, ts)
        return [snapshot]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def fetch_insider_trades(
        self,
        ticker: str,
        limit: int = 50,
    ) -> list[FinancialSnapshot]:
        """Fetch recent insider-trading records for *ticker*.

        Endpoint (verify against live FMP docs):
        - GET /insider-trading?symbol={ticker}&limit={limit}
        """
        logger.debug("FMPConnector.fetch_insider_trades %s limit=%d", ticker, limit)

        data = self._get("/insider-trading", symbol=ticker, limit=limit)
        records = data if isinstance(data, list) else data.get("data", [])

        results: list[FinancialSnapshot] = []
        for item in records:
            raw_date = item.get("transactionDate") or item.get("filingDate")
            if raw_date:
                try:
                    ts = datetime.fromisoformat(str(raw_date)).replace(tzinfo=timezone.utc)
                except ValueError:
                    ts = datetime.now(tz=timezone.utc)
            else:
                ts = datetime.now(tz=timezone.utc)

            trade_type_raw = (item.get("transactionType") or "").lower()
            if "purchase" in trade_type_raw or "buy" in trade_type_raw:
                trade_type = "buy"
            elif "sale" in trade_type_raw or "sell" in trade_type_raw:
                trade_type = "sell"
            else:
                trade_type = trade_type_raw or None

            shares_val = item.get("securitiesTransacted") or item.get("shares")
            price_val = item.get("price") or item.get("transactionPrice")

            results.append(
                FinancialSnapshot(
                    ticker=ticker,
                    timestamp=ts,
                    data_type="insider_trade",
                    source="fmp",
                    insider_name=item.get("reportingName") or item.get("insiderName"),
                    trade_type=trade_type,
                    shares=int(shares_val) if shares_val is not None else None,
                    trade_value=_to_decimal(price_val),
                )
            )
        logger.info("FMPConnector.fetch_insider_trades %s: %d records", ticker, len(results))
        return results

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
        """Fetch recent news articles for *ticker*.

        Endpoint (verify against live FMP docs):
        - GET /stock_news?tickers={ticker}&limit={limit}
        """
        logger.debug("FMPConnector.fetch_news %s limit=%d", ticker, limit)

        data = self._get("/stock_news", tickers=ticker, limit=limit)
        records = data if isinstance(data, list) else []

        results: list[FinancialSnapshot] = []
        for item in records:
            raw_date = item.get("publishedDate")
            if raw_date:
                try:
                    ts = datetime.fromisoformat(str(raw_date)).replace(tzinfo=timezone.utc)
                except ValueError:
                    ts = datetime.now(tz=timezone.utc)
            else:
                ts = datetime.now(tz=timezone.utc)

            results.append(
                FinancialSnapshot(
                    ticker=ticker,
                    timestamp=ts,
                    data_type="news",
                    source="fmp",
                    headline=item.get("title"),
                    summary=item.get("text"),
                    article_url=item.get("url"),
                )
            )
        logger.info("FMPConnector.fetch_news %s: %d items", ticker, len(results))
        return results
