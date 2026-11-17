"""create fact_backtest

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-16 22:06:14.204254

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "fact_backtest",
        sa.Column("ativo_id", sa.Integer(), nullable=False),
        sa.Column("signal", sa.String(length=30), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("data_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_count", sa.Integer(), nullable=False),
        sa.Column("independent_count", sa.Integer(), nullable=False),
        sa.Column("evaluated_count", sa.Integer(), nullable=False),
        sa.Column("min_sample", sa.Integer(), nullable=False),
        sa.Column("enough_sample", sa.Boolean(), nullable=False),
        sa.Column("mean_return", sa.Float(), nullable=True),
        sa.Column("median_return", sa.Float(), nullable=True),
        sa.Column("hit_rate", sa.Float(), nullable=True),
        sa.Column("baseline_mean", sa.Float(), nullable=True),
        sa.Column("baseline_hit_rate", sa.Float(), nullable=True),
        sa.Column("first_event", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ativo_id"],
            ["dim_ativo.id"],
        ),
        sa.PrimaryKeyConstraint("ativo_id", "signal", "horizon_days"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("fact_backtest")
