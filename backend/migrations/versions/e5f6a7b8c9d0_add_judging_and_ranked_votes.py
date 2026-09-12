"""Add per-event judges, judge scores, finalists, and ranked votes.

Events:
- add judge_code (6-digit judge invite code)
- add judging_open / voting_open, the two rounds as independent switches,
  backfilled from the phase they replace as gates

Projects:
- add is_finalist

Votes:
- add rank, backfilled 1..n per (voter, event) by created_at
- add unique (voter_id, event_id, rank)

New tables:
- event_judges (judging access, scoped per event)
- judge_scores
"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "c4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("is_finalist", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "events",
        sa.Column("judging_open", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "events",
        sa.Column("voting_open", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Voting used to be gated purely on phase == 'voting'; keep those events open.
    op.execute("UPDATE events SET voting_open = true WHERE phase = 'voting'")

    op.add_column("events", sa.Column("judge_code", sa.String(length=6), nullable=True))
    op.create_index(
        "ix_events_judge_code", "events", ["judge_code"], unique=True
    )

    op.add_column(
        "votes",
        sa.Column("rank", sa.Integer(), nullable=False, server_default="1"),
    )
    # Existing ballots were unordered multi-select. Turn each voter's votes into a
    # ranking by submission order so the new unique constraint holds and the
    # weighted score preserves the old ordering (every project's total scales).
    op.execute(
        """
        UPDATE votes SET rank = ranked.position
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY voter_id, event_id ORDER BY created_at, id
            ) AS position
            FROM votes
        ) AS ranked
        WHERE votes.id = ranked.id
        """
    )
    op.create_unique_constraint(
        "uq_votes_voter_id_event_id_rank", "votes", ["voter_id", "event_id", "rank"]
    )

    op.create_table(
        "event_judges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "user_id"),
    )

    op.create_table(
        "judge_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("originality", sa.Integer(), nullable=False),
        sa.Column("technicality", sa.Integer(), nullable=False),
        sa.Column("theme", sa.Integer(), nullable=False),
        sa.Column("usability", sa.Integer(), nullable=False),
        sa.Column("judge_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["judge_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("judge_id", "project_id"),
    )
    op.create_index("ix_judge_scores_judge_id", "judge_scores", ["judge_id"])
    op.create_index("ix_judge_scores_project_id", "judge_scores", ["project_id"])
    op.create_index("ix_judge_scores_event_id", "judge_scores", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_judge_scores_event_id", table_name="judge_scores")
    op.drop_index("ix_judge_scores_project_id", table_name="judge_scores")
    op.drop_index("ix_judge_scores_judge_id", table_name="judge_scores")
    op.drop_table("judge_scores")
    op.drop_table("event_judges")

    op.drop_constraint("uq_votes_voter_id_event_id_rank", "votes", type_="unique")
    op.drop_column("votes", "rank")

    op.drop_index("ix_events_judge_code", table_name="events")
    op.drop_column("events", "judge_code")
    op.drop_column("events", "voting_open")
    op.drop_column("events", "judging_open")

    op.drop_column("projects", "is_finalist")
