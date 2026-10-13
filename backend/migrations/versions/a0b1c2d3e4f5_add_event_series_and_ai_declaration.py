"""event series managed in the browser, and AI declarations on projects

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
"""

from alembic import op
import sqlalchemy as sa


revision = "a0b1c2d3e4f5"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_series",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_series_slug", "event_series", ["slug"], unique=True)
    # At most one current series
    op.create_index(
        "uq_event_series_one_current",
        "event_series",
        ["is_current"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.add_column(
        "events",
        sa.Column(
            "require_ai_declaration", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "projects",
        sa.Column("ai_declaration", sa.String(length=1000), nullable=False, server_default=""),
    )
    op.add_column("projects", sa.Column("ai_under_limit", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "ai_under_limit")
    op.drop_column("projects", "ai_declaration")
    op.drop_column("events", "require_ai_declaration")
    op.drop_index("uq_event_series_one_current", table_name="event_series")
    op.drop_index("ix_event_series_slug", table_name="event_series")
    op.drop_table("event_series")
