"""
Reusable query helpers for common DB access patterns.

These functions centralize cross-cutting concerns like soft-delete filtering
so routers don't scatter `.where(Model.deleted_at.is_(None))` everywhere.
Add per-model helpers here as new models adopt soft-deletion or other patterns.

Usage:
    from podium.db.postgres.queries import get_active_event, list_active_events
"""

from secrets import token_urlsafe
from uuid import UUID

from slugify import slugify

from sqlalchemy.orm import Load
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from podium.db.postgres.base import scalar_one_or_none, scalar_all
from podium.config import settings
from podium.db.postgres.event import Event
from podium.db.postgres.series import EventSeries


async def get_active_event(
    session: AsyncSession, event_id: UUID, *extra_loads: Load
) -> Event | None:
    """Fetch a non-deleted event by ID.

    Pass additional selectinload() calls to eagerly load relationships in the
    same query (avoids a second round-trip):
        event = await get_active_event(session, id, selectinload(Event.projects))
    """
    stmt = (
        select(Event)
        .where(Event.id == event_id, Event.deleted_at.is_(None))
        .options(*extra_loads)
    )
    return await scalar_one_or_none(session, stmt)


async def list_active_events(
    session: AsyncSession, *extra_loads: Load
) -> list[Event]:
    """Fetch all non-deleted events."""
    stmt = (
        select(Event)
        .where(Event.deleted_at.is_(None))
        .options(*extra_loads)
    )
    return await scalar_all(session, stmt)


async def get_current_series_slug(session: AsyncSession) -> str:
    """The current series, as set by a superadmin. Falls back to the
    ACTIVE_EVENT_SERIES setting until a series has been made current."""
    current = await scalar_one_or_none(
        session, select(EventSeries).where(EventSeries.is_current)
    )
    if current:
        return current.slug
    return settings.active_event_series or ""


async def series_names(session: AsyncSession) -> dict[str, str]:
    """Map of series slug -> display name."""
    return {s.slug: s.name for s in await scalar_all(session, select(EventSeries))}


async def resolve_event_slug(
    session: AsyncSession,
    requested: str | None,
    name: str,
    exclude_event_id: UUID | None = None,
) -> str:
    """The slug an event should use: a cleaned-up custom one if given, else
    one generated from the name with a random suffix.

    Raises ValueError with a user-facing message if the custom slug is empty
    after cleaning or already taken (soft-deleted events keep their slug)."""
    if requested is None or not requested.strip():
        base = slugify(name)[:40] or "event"
        return f"{base}-{token_urlsafe(4)}"

    slug = slugify(requested)[:50]
    if not slug:
        raise ValueError("Use letters, numbers or dashes for the URL")
    stmt = select(Event).where(Event.slug == slug)
    if exclude_event_id is not None:
        stmt = stmt.where(Event.id != exclude_event_id)
    taken = await scalar_one_or_none(session, stmt)
    if taken:
        detail = " (by a deleted event)" if taken.deleted_at else ""
        raise ValueError(f"/events/{slug} is already used{detail}")
    return slug
