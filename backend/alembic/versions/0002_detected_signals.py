"""detected_signals hypertable

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "detected_signals",
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("score", sa.Numeric(), nullable=False),
        sa.Column("composite_score", sa.Numeric(), nullable=True),
        sa.Column("passed_gate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False, server_default="scanner"),
        sa.PrimaryKeyConstraint("detected_at", "ticker", "signal_type"),
    )
    op.execute(
        "SELECT create_hypertable('detected_signals', 'detected_at', "
        "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )
    op.create_index(
        "ix_detected_signals_ticker_detected_at",
        "detected_signals",
        ["ticker", "detected_at"],
    )
    op.create_index(
        "ix_detected_signals_passed_gate_detected_at",
        "detected_signals",
        ["passed_gate", "detected_at"],
    )


def downgrade() -> None:
    op.drop_table("detected_signals")
