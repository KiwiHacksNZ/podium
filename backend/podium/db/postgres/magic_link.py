from datetime import datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


class MagicLink(SQLModel, table=True):
    """Single-use bearer record for email login links."""

    __tablename__: str = "magic_links"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    email: str = Field(max_length=255, index=True)
    expires_at: datetime
    used_at: datetime | None = None
