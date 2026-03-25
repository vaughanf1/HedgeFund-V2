"""Abstract DataConnector interface — all concrete connectors must implement this."""

from abc import ABC, abstractmethod
from datetime import date

from app.schemas.financial import FinancialSnapshot


class DataConnector(ABC):
    """Base class for all financial data connectors.

    Each concrete connector maps a third-party data source to the canonical
    FinancialSnapshot schema.  Methods return plain lists so they can be called
    directly from synchronous Celery tasks.
    """

    @abstractmethod
    def fetch_ohlcv(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[FinancialSnapshot]:
        """Fetch OHLCV bars for *ticker* between *from_date* and *to_date* (inclusive)."""

    @abstractmethod
    def fetch_fundamentals(
        self,
        ticker: str,
    ) -> list[FinancialSnapshot]:
        """Fetch the most recent fundamental ratios / financials for *ticker*."""

    @abstractmethod
    def fetch_insider_trades(
        self,
        ticker: str,
        limit: int = 50,
    ) -> list[FinancialSnapshot]:
        """Fetch recent insider-trading records for *ticker*."""

    @abstractmethod
    def fetch_news(
        self,
        ticker: str,
        limit: int = 20,
    ) -> list[FinancialSnapshot]:
        """Fetch recent news articles for *ticker*."""
