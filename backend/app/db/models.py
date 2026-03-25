from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PriceOHLCV(Base):
    """OHLCV price data — TimescaleDB hypertable on timestamp."""

    __tablename__ = "price_ohlcv"
    __table_args__ = {
        "timescaledb_hypertable": {"time_column_name": "timestamp"},
    }

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    open: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    high: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    low: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    close: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class Fundamentals(Base):
    """Fundamental financial data — TimescaleDB hypertable on timestamp."""

    __tablename__ = "fundamentals"
    __table_args__ = {
        "timescaledb_hypertable": {"time_column_name": "timestamp"},
    }

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    pe_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    net_income: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    eps: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    debt_to_equity: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    free_cash_flow: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    market_cap: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class InsiderTrade(Base):
    """Insider trading records — TimescaleDB hypertable on timestamp."""

    __tablename__ = "insider_trades"
    __table_args__ = {
        "timescaledb_hypertable": {"time_column_name": "timestamp"},
    }

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    insider_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    trade_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    shares: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    trade_value: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class NewsItem(Base):
    """News items with sentiment — TimescaleDB hypertable on timestamp."""

    __tablename__ = "news_items"
    __table_args__ = {
        "timescaledb_hypertable": {"time_column_name": "timestamp"},
    }

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    headline: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    article_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
