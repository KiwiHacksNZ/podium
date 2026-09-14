"""
Single-use judge codes, one per printed card.

An event's `judge_code` is a shared code that any number of judges can redeem.
These are the opposite: a batch of codes minted for printing, each burned by the
first judge who redeems it, so a card maps to exactly one judge.

Burning a code does not destroy work. A judge's identity is derived from their
email, so handing a locked-out judge a fresh card restores their existing scores.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


class JudgeCode(SQLModel, table=True):
    __tablename__: str = "judge_codes"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    event_id: UUID = Field(foreign_key="events.id", index=True)
    # Unique across every event so a judge only ever types the six digits.
    code: str = Field(max_length=6, unique=True, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    redeemed_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), nullable=True
    )
    redeemed_by_id: UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True
    )
