"""add single-use magic link records

Revision ID: c4f5a6b7c8d9
Revises: a7c8d9e0f1b2
"""

from alembic import op
import sqlalchemy as sa


revision = "c4f5a6b7c8d9"
down_revision = "a7c8d9e0f1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "magic_links",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_magic_links_email", "magic_links", ["email"])


def downgrade() -> None:
    op.drop_index("ix_magic_links_email", table_name="magic_links")
    op.drop_table("magic_links")
