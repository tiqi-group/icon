"""Add labels column to ttl_mask_states table.

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-05-18 00:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a1"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ttl_mask_states", schema=None) as batch_op:
        batch_op.add_column(sa.Column("labels", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ttl_mask_states", schema=None) as batch_op:
        batch_op.drop_column("labels")
