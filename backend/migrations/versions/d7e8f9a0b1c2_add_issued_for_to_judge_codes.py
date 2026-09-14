"""record which judge a replacement card was issued for

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d7e8f9a0b1c2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "judge_codes",
        sa.Column("issued_for_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_judge_codes_issued_for_id_users",
        "judge_codes",
        "users",
        ["issued_for_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_judge_codes_issued_for_id_users", "judge_codes", type_="foreignkey"
    )
    op.drop_column("judge_codes", "issued_for_id")
