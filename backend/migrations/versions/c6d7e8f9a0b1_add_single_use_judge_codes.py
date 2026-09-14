"""add single-use judge codes

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c6d7e8f9a0b1"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "judge_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["redeemed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_judge_codes_event_id", "judge_codes", ["event_id"])
    op.create_index("ix_judge_codes_code", "judge_codes", ["code"])


def downgrade() -> None:
    op.drop_index("ix_judge_codes_code", table_name="judge_codes")
    op.drop_index("ix_judge_codes_event_id", table_name="judge_codes")
    op.drop_table("judge_codes")
