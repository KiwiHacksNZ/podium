"""
JudgeScore model and API schemas.

One row per (judge, project): a judge's 1-10 score on each of the four criteria.
Judges score every project in an event during the JUDGING phase; the highest
mean totals become finalists for the attendee vote.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import computed_field
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from podium.db.postgres.event import Event
    from podium.db.postgres.project import Project
    from podium.db.postgres.user import User


class JudgeScoreBase(SQLModel):
    """The four scored criteria, 1-10 each (max total 40)."""

    originality: int = Field(ge=1, le=10)
    technicality: int = Field(ge=1, le=10)
    theme: int = Field(ge=1, le=10)
    usability: int = Field(ge=1, le=10)


class JudgeScore(JudgeScoreBase, table=True):
    """A judge's score for one project — maps to 'judge_scores' table."""

    __tablename__: str = "judge_scores"
    __table_args__ = (UniqueConstraint("judge_id", "project_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    judge_id: UUID = Field(foreign_key="users.id", index=True)
    project_id: UUID = Field(foreign_key="projects.id", index=True)
    event_id: UUID = Field(foreign_key="events.id", index=True)

    judge: "User" = Relationship(back_populates="judge_scores")
    project: "Project" = Relationship(back_populates="judge_scores")
    event: "Event" = Relationship(back_populates="judge_scores")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        return self.originality + self.technicality + self.theme + self.usability


# =============================================================================
# API SCHEMAS
# =============================================================================


class JudgeScoreUpsert(JudgeScoreBase):
    """Request body for scoring a project (full replace of this judge's score)."""


class JudgeScorePublic(JudgeScoreBase):
    """A judge's own score, echoed back to them."""

    project_id: UUID
    total: int
    updated_at: datetime
