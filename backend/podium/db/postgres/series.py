"""
Event series model and API schemas.

A series groups a flagship event and its satellites (e.g. "KiwiHacks 2026").
Events join a series by carrying its slug in feature_flags_csv. Exactly one
series is current; it drives the official event list and attending rules.
"""

from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class EventSeries(SQLModel, table=True):
    """Event series — maps to 'event_series' table."""

    __tablename__: str = "event_series"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    slug: str = Field(max_length=50, unique=True, index=True)
    name: str = Field(max_length=100)
    is_current: bool = Field(default=False)


class EventSeriesPublic(SQLModel):
    id: UUID
    slug: str
    name: str
    is_current: bool


class EventSeriesCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    # Derived from the name when omitted
    slug: str | None = Field(default=None, max_length=50)
