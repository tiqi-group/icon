"""add unit column to scan_parameters.

Revision ID: c3a91f0b7d2e
Revises: f60d837b7263
Create Date: 2026-08-24 15:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a91f0b7d2e"
down_revision: str | None = "f60d837b7263"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("scan_parameters", schema=None) as batch_op:
        batch_op.add_column(sa.Column("unit", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scan_parameters", schema=None) as batch_op:
        batch_op.drop_column("unit")
