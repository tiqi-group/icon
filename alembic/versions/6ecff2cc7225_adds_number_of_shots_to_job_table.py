"""Adds number_of_shots to Job table

Revision ID: 6ecff2cc7225
Revises: 5b41d0d6c856
Create Date: 2025-05-16 14:11:09.535385

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6ecff2cc7225"
down_revision: str | None = "5b41d0d6c856"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("job_submissions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "number_of_shots", sa.Integer(), server_default="50", nullable=False
            )
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("job_submissions", schema=None) as batch_op:
        batch_op.drop_column("number_of_shots")

    # ### end Alembic commands ###
