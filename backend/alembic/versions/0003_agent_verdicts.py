"""agent_verdicts and cio_decisions hypertables

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_verdicts",
        sa.Column("analysed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opportunity_id", sa.String(100), nullable=False),
        sa.Column("persona", sa.String(20), nullable=False),
        sa.Column("verdict", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("verdict_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("analysed_at", "opportunity_id", "persona"),
    )
    op.execute(
        "SELECT create_hypertable('agent_verdicts', 'analysed_at', "
        "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )
    op.create_index(
        "ix_agent_verdicts_opportunity_id_analysed_at",
        "agent_verdicts",
        ["opportunity_id", "analysed_at"],
    )

    op.create_table(
        "cio_decisions",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opportunity_id", sa.String(100), nullable=False),
        sa.Column("conviction_score", sa.Integer(), nullable=False),
        sa.Column("suggested_allocation_pct", sa.Numeric(), nullable=False),
        sa.Column("final_verdict", sa.String(10), nullable=False),
        sa.Column("decision_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("decided_at", "opportunity_id"),
    )
    op.execute(
        "SELECT create_hypertable('cio_decisions', 'decided_at', "
        "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )
    op.create_index(
        "ix_cio_decisions_opportunity_id_decided_at",
        "cio_decisions",
        ["opportunity_id", "decided_at"],
    )


def downgrade() -> None:
    op.drop_table("cio_decisions")
    op.drop_table("agent_verdicts")
