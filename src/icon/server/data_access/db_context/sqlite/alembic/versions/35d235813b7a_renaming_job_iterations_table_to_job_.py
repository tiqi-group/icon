"""Renaming job_iterations table to job_runs

Revision ID: 35d235813b7a
Revises: 000976b1cd64
Create Date: 2024-08-09 10:30:48.742182

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "35d235813b7a"
down_revision: str | None = "000976b1cd64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("job_iterations", "job_runs")


def downgrade() -> None:
    op.rename_table("job_runs", "job_iterations")
