"""
Vote audit log.

Append-only record of vote changes and metadata useful for event ops review.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel
from sqlalchemy import DateTime


class VoteAuditLog(SQLModel, table=True):
    """Vote action audit entry - maps to 'vote_audit_logs' table."""

    __tablename__: str = "vote_audit_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    event_id: UUID = Field(foreign_key="events.id", index=True)
    project_id: UUID = Field(foreign_key="projects.id", index=True)
    voter_id: UUID = Field(foreign_key="users.id", index=True)
    actor_id: UUID = Field(foreign_key="users.id", index=True)
    vote_id: UUID | None = Field(default=None, index=True)
    action: str = Field(max_length=50)
    ip_address: str = Field(default="", max_length=255)
    user_agent: str = Field(default="", max_length=500)
    reason: str = Field(default="", max_length=500)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        index=True,
    )
