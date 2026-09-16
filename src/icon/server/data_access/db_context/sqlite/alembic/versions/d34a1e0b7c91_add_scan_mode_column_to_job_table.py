"""add scan_mode column to job table.

Revision ID: d34a1e0b7c91
Revises: f60d837b7263
Create Date: 2026-07-24 14:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d34a1e0b7c91"
down_revision: str | None = "f60d837b7263"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_submissions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "scan_mode",
                sa.Enum("MESH", "CORRELATED", name="scanmode"),
                nullable=False,
                server_default="MESH",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("job_submissions", schema=None) as batch_op:
        batch_op.drop_column("scan_mode")
