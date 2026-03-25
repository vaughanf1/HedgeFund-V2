"""Initial schema — create all four hypertables

Revision ID: 0001
Revises:
Create Date: 2026-03-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # price_ohlcv table
    op.create_table(
        "price_ohlcv",
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=True),
        sa.Column("high", sa.Numeric(), nullable=True),
        sa.Column("low", sa.Numeric(), nullable=True),
        sa.Column("close", sa.Numeric(), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("timestamp", "ticker"),
    )
    op.execute(
        "SELECT create_hypertable('price_ohlcv', 'timestamp', "
        "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )
    op.create_index(
        "ix_price_ohlcv_ticker_timestamp",
        "price_ohlcv",
        ["ticker", "timestamp"],
    )

    # fundamentals table
    op.create_table(
        "fundamentals",
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("pe_ratio", sa.Numeric(), nullable=True),
        sa.Column("revenue", sa.Numeric(), nullable=True),
        sa.Column("net_income", sa.Numeric(), nullable=True),
        sa.Column("eps", sa.Numeric(), nullable=True),
        sa.Column("debt_to_equity", sa.Numeric(), nullable=True),
        sa.Column("free_cash_flow", sa.Numeric(), nullable=True),
        sa.Column("market_cap", sa.Numeric(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("timestamp", "ticker"),
    )
    op.execute(
        "SELECT create_hypertable('fundamentals', 'timestamp', "
        "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )
    op.create_index(
        "ix_fundamentals_ticker_timestamp",
        "fundamentals",
        ["ticker", "timestamp"],
    )

    # insider_trades table
    op.create_table(
        "insider_trades",
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("insider_name", sa.String(200), nullable=True),
        sa.Column("trade_type", sa.String(10), nullable=True),
        sa.Column("shares", sa.BigInteger(), nullable=True),
        sa.Column("trade_value", sa.Numeric(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("timestamp", "ticker"),
    )
    op.execute(
        "SELECT create_hypertable('insider_trades', 'timestamp', "
        "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )
    op.create_index(
        "ix_insider_trades_ticker_timestamp",
        "insider_trades",
        ["ticker", "timestamp"],
    )

    # news_items table
    op.create_table(
        "news_items",
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.String(20), nullable=True),
        sa.Column("article_url", sa.Text(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("timestamp", "ticker"),
    )
    op.execute(
        "SELECT create_hypertable('news_items', 'timestamp', "
        "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )
    op.create_index(
        "ix_news_items_ticker_timestamp",
        "news_items",
        ["ticker", "timestamp"],
    )


def downgrade() -> None:
    op.drop_table("news_items")
    op.drop_table("insider_trades")
    op.drop_table("fundamentals")
    op.drop_table("price_ohlcv")
