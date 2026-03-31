"""YFinanceConnector — free financial data via the yfinance library.

Replaces both FMPConnector (fundamentals, insider trades, news) and
MassiveConnector (OHLCV, news) with a single zero-cost connector.
No API key required.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

import yfinance as yf

from app.connectors.base import DataConnector
from app.schemas.financial import FinancialSnapshot

logger = logging.getLogger(__name__)


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        d = Decimal(str(value))
        return None if d != d else d  # NaN check
    except (InvalidOperation, ValueError):
        return None


class YFinanceConnector(DataConnector):
    """Concrete connector using yfinance (Yahoo Finance). No API key needed."""

    def fetch_ohlcv(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[FinancialSnapshot]:
        logger.debug("YFinanceConnector.fetch_ohlcv %s %s->%s", ticker, from_date, to_date)
        t = yf.Ticker(ticker)
        df = t.history(start=str(from_date), end=str(to_date), auto_adjust=True)

        results: list[FinancialSnapshot] = []
        for idx, row in df.iterrows():
            ts = idx.to_pydatetime().replace(tzinfo=timezone.utc)
            results.append(
                FinancialSnapshot(
                    ticker=ticker,
                    timestamp=ts,
                    data_type="ohlcv",
                    source="yfinance",
                    open=_to_decimal(row.get("Open")),
                    high=_to_decimal(row.get("High")),
                    low=_to_decimal(row.get("Low")),
                    close=_to_decimal(row.get("Close")),
                    price=_to_decimal(row.get("Close")),
                    volume=int(row["Volume"]) if row.get("Volume") is not None else None,
                )
            )
        logger.info("YFinanceConnector.fetch_ohlcv %s: %d bars", ticker, len(results))
        return results

    def fetch_fundamentals(self, ticker: str) -> list[FinancialSnapshot]:
        logger.debug("YFinanceConnector.fetch_fundamentals %s", ticker)
        t = yf.Ticker(ticker)
        info = t.info or {}

        snapshot = FinancialSnapshot(
            ticker=ticker,
            timestamp=datetime.now(tz=timezone.utc),
            data_type="fundamentals",
            source="yfinance",
            pe_ratio=_to_decimal(info.get("trailingPE")),
            revenue=_to_decimal(info.get("totalRevenue")),
            net_income=_to_decimal(info.get("netIncomeToCommon")),
            eps=_to_decimal(info.get("trailingEps")),
            debt_to_equity=_to_decimal(info.get("debtToEquity")),
            free_cash_flow=_to_decimal(info.get("freeCashflow")),
            market_cap=_to_decimal(info.get("marketCap")),
        )
        logger.info("YFinanceConnector.fetch_fundamentals %s: done", ticker)
        return [snapshot]

    def fetch_insider_trades(self, ticker: str, limit: int = 50) -> list[FinancialSnapshot]:
        logger.debug("YFinanceConnector.fetch_insider_trades %s limit=%d", ticker, limit)
        t = yf.Ticker(ticker)
        df = t.insider_transactions
        if df is None or df.empty:
            logger.info("YFinanceConnector.fetch_insider_trades %s: no data", ticker)
            return []

        results: list[FinancialSnapshot] = []
        for _, row in df.head(limit).iterrows():
            raw_date = row.get("Start Date") or row.get("Date")
            if raw_date is not None:
                try:
                    ts = raw_date.to_pydatetime().replace(tzinfo=timezone.utc)
                except (ValueError, AttributeError):
                    ts = datetime.now(tz=timezone.utc)
            else:
                ts = datetime.now(tz=timezone.utc)

            transaction = str(row.get("Transaction", "")).lower()
            if "purchase" in transaction or "buy" in transaction:
                trade_type = "buy"
            elif "sale" in transaction or "sell" in transaction:
                trade_type = "sell"
            else:
                trade_type = transaction or None

            results.append(
                FinancialSnapshot(
                    ticker=ticker,
                    timestamp=ts,
                    data_type="insider_trade",
                    source="yfinance",
                    insider_name=row.get("Insider") or row.get("Name"),
                    trade_type=trade_type,
                    shares=int(row["Shares"]) if row.get("Shares") is not None else None,
                    trade_value=_to_decimal(row.get("Value")),
                )
            )
        logger.info("YFinanceConnector.fetch_insider_trades %s: %d records", ticker, len(results))
        return results

    def fetch_news(self, ticker: str, limit: int = 20) -> list[FinancialSnapshot]:
        logger.debug("YFinanceConnector.fetch_news %s limit=%d", ticker, limit)
        t = yf.Ticker(ticker)
        news_items = t.news or []

        results: list[FinancialSnapshot] = []
        for item in news_items[:limit]:
            pub_ts = item.get("providerPublishTime")
            if pub_ts:
                ts = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
            else:
                ts = datetime.now(tz=timezone.utc)

            results.append(
                FinancialSnapshot(
                    ticker=ticker,
                    timestamp=ts,
                    data_type="news",
                    source="yfinance",
                    headline=item.get("title"),
                    summary=item.get("summary") or item.get("description"),
                    article_url=item.get("link"),
                )
            )
        logger.info("YFinanceConnector.fetch_news %s: %d items", ticker, len(results))
        return results
