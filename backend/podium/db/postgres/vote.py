"""
Vote model.

A Vote records when a user ranks a project in an event. `rank` is the ballot
position: 1 = first choice, 2 = second, 3 = third, weighted by RANK_POINTS.
Each user can only vote once per project, and can only use each rank once per
event (both enforced by unique constraints).
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Relationship, UniqueConstraint
from sqlalchemy import DateTime

from podium.constants import MAX_RANK

if TYPE_CHECKING:
    from podium.db.postgres.user import User
    from podium.db.postgres.event import Event
    from podium.db.postgres.project import Project


class Vote(SQLModel, table=True):
    """Vote for a project - maps to 'votes' table."""

    __tablename__: str = "votes"
    __table_args__ = (
        UniqueConstraint("voter_id", "project_id"),
        UniqueConstraint("voter_id", "event_id", "rank"),
    )

    # Primary key - auto-generated UUID
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    # Ballot position: 1 = first choice ... MAX_RANK = last. See RANK_POINTS.
    rank: int = Field(default=1, ge=1, le=MAX_RANK)
    ip_address: str = Field(default="", max_length=255)
    user_agent: str = Field(default="", max_length=500)

    # Foreign keys
    voter_id: UUID = Field(foreign_key="users.id")
    project_id: UUID = Field(foreign_key="projects.id")
    event_id: UUID = Field(foreign_key="events.id")  # denormalized for faster queries

    # Relationships
    voter: "User" = Relationship(back_populates="votes")
    project: "Project" = Relationship(back_populates="votes")
    event: "Event" = Relationship(back_populates="votes")
