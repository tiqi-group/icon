"""Add ttl_mask_states table.

Revision ID: a1b2c3d4e5f6
Revises: fc9af856df20
Create Date: 2026-05-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "fc9af856df20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ttl_mask_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("high_mask", sa.Integer(), nullable=False),
        sa.Column("low_mask", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ttl_mask_states")
