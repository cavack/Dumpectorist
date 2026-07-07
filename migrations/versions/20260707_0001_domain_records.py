"""Create domain records table.

Revision ID: 20260707_0001
Revises:
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260707_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "domain_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("record_type", sa.String(length=50), nullable=False),
        sa.Column("symbol", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_domain_records_symbol_created",
        "domain_records",
        ["symbol", "created_at"],
    )
    op.create_index(
        "ix_domain_records_type_state",
        "domain_records",
        ["record_type", "state"],
    )


def downgrade() -> None:
    op.drop_index("ix_domain_records_type_state", table_name="domain_records")
    op.drop_index("ix_domain_records_symbol_created", table_name="domain_records")
    op.drop_table("domain_records")
