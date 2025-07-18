"""Adds unique constraint on scheduled_time

Revision ID: 027f86f1812b
Revises: 35d235813b7a
Create Date: 2024-08-09 10:56:39.093926

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "027f86f1812b"
down_revision: str | None = "35d235813b7a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("job_runs", schema=None) as batch_op:
        batch_op.create_unique_constraint("unique_scheduled_time", ["scheduled_time"])

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("job_runs", schema=None) as batch_op:
        batch_op.drop_constraint("unique_scheduled_time", type_="unique")

    # ### end Alembic commands ###
