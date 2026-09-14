"""add judge_email to event_judges

Revision ID: b5c6d7e8f9a0
Revises: e5f6a7b8c9d0
"""

from alembic import op
import sqlalchemy as sa


revision = "b5c6d7e8f9a0"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event_judges",
        sa.Column("judge_email", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("event_judges", "judge_email")
