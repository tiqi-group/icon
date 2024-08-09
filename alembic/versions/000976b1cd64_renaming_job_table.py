"""Renaming job table

Revision ID: 000976b1cd64
Revises: e53ce613a1ed
Create Date: 2024-08-09 08:37:27.557753

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "000976b1cd64"
down_revision: str | None = "e53ce613a1ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("jobs", "job_submissions")


def downgrade() -> None:
    op.rename_table("job_submissions", "jobs")
