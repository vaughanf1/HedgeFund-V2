"""Canonical FinancialSnapshot schema — the single data contract between connectors and database."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

DataType = Literal["ohlcv", "fundamentals", "insider_trade", "news"]


class FinancialSnapshot(BaseModel):
    """Normalised financial data record produced by all connectors.

    Fields are Optional where they only apply to a subset of data types:
    - ohlcv:          open, high, low, close, volume, price
    - fundamentals:   pe_ratio, revenue, net_income, eps, debt_to_equity,
                      free_cash_flow, market_cap
    - insider_trade:  insider_name, trade_type, shares, trade_value
    - news:           headline, summary, sentiment, article_url
    """

    model_config = ConfigDict(json_encoders={Decimal: str})

    # --- Core identity fields (always present) ---
    ticker: str
    timestamp: datetime
    data_type: DataType
    source: str  # e.g. "massive", "fmp"

    # --- OHLCV ---
    price: Optional[Decimal] = None   # close / last price
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Optional[int] = None

    # --- Fundamentals ---
    pe_ratio: Optional[Decimal] = None
    revenue: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    eps: Optional[Decimal] = None
    debt_to_equity: Optional[Decimal] = None
    free_cash_flow: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None

    # --- Insider trade ---
    insider_name: Optional[str] = None
    trade_type: Optional[str] = None   # "buy" | "sell"
    shares: Optional[int] = None
    trade_value: Optional[Decimal] = None

    # --- News ---
    headline: Optional[str] = None
    summary: Optional[str] = None
    sentiment: Optional[str] = None   # "positive" | "negative" | "neutral"
    article_url: Optional[str] = None
