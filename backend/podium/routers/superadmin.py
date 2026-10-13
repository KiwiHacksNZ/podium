"""
Superadmin endpoints. Requires is_superadmin=True on the authenticated user.

Superadmins can:
  - List all events (including soft-deleted)
  - Create real events (not limited to test endpoints)
  - Soft-delete events (sets deleted_at, hides from public listings)
  - Update any event field including owner (by email)
  - List all users
  - Create event series and choose the current one

Regular admin endpoints (admin.py) already grant superadmins full owner access
to any event via the get_owned_event helper.
"""

import csv
from datetime import datetime, UTC
from io import StringIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import ConfigDict
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from secrets import token_urlsafe
from slugify import slugify
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload

from podium.db.postgres import (
    User,
    Event,
    Project,
    EventPrivate,
    EventUpdate,
    EventSeries,
    EventSeriesCreate,
    EventSeriesPublic,
    get_session,
    scalar_all,
    scalar_one_or_none,
)
from podium.routers.auth import get_current_user
from podium.constants import BAD_ACCESS, EventPhase, PlatformAdminPermission
from podium.authz import normalize_permissions_csv, parse_permissions_csv

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


async def require_superadmin(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Dependency: raise 403 if the user is not a superadmin."""
    if not user.is_superadmin:
        raise BAD_ACCESS
    return user


class EventCreate(BaseModel):
    name: str
    description: str = ""
    phase: str = EventPhase.DRAFT
    demo_links_optional: bool = False
    repo_validation: str = "github"
    demo_validation: str = "none"
    custom_validator: str | None = None
    feature_flags_csv: str = ""


class SuperadminEventUpdate(EventUpdate):
    """EventUpdate extended with superadmin-only fields."""
    owner_email: str | None = None


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    display_name: str
    is_superadmin: bool
    is_admin: bool
    admin_permissions_csv: str


class UserAccessUpdate(BaseModel):
    is_superadmin: bool | None = None
    is_admin: bool | None = None
    admin_permissions_csv: str | None = None


def _validate_permissions_csv(value: str) -> str:
    permissions = parse_permissions_csv(value)
    valid_permissions = {permission.value for permission in PlatformAdminPermission}
    invalid = sorted(p for p in permissions if p not in valid_permissions)
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid admin permission(s): {', '.join(invalid)}",
        )
    return normalize_permissions_csv(permissions)


@router.get("/events")
async def list_all_events(
    user: Annotated[User, Depends(require_superadmin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Page[EventPrivate]:
    """List all events, including soft-deleted ones."""
    return await paginate(session, select(Event).options(selectinload(Event.projects)))


@router.post("/events")
async def create_event(
    event_data: EventCreate,
    user: Annotated[User, Depends(require_superadmin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventPrivate:
    """Create a real event as the requesting superadmin user."""
    base_slug = slugify(event_data.name)[:40] or "event"
    slug = f"{base_slug}-{token_urlsafe(4)}"

    event = Event(
        **event_data.model_dump(),
        slug=slug,
        owner_id=user.id,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)

    stmt = select(Event).where(Event.id == event.id).options(selectinload(Event.projects))
    event = await scalar_one_or_none(session, stmt)
    return EventPrivate.model_validate(event)


@router.delete("/events/{event_id}")
async def soft_delete_event(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(require_superadmin)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Soft-delete an event (sets deleted_at). The event is hidden from public listings."""
    event = await session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Event is already deleted")

    event.deleted_at = datetime.now(UTC)
    await session.commit()
    return {"message": "Event soft-deleted", "deleted_at": event.deleted_at.isoformat()}


@router.patch("/events/{event_id}")
async def update_event(
    event_id: Annotated[UUID, Path(title="Event ID")],
    update: SuperadminEventUpdate,
    user: Annotated[User, Depends(require_superadmin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventPrivate:
    """Update any event field. Use owner_email to transfer ownership."""
    event = await session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    data = update.model_dump(exclude_unset=True)

    if "owner_email" in data:
        owner_email = data.pop("owner_email")
        new_owner = await scalar_one_or_none(session, select(User).where(User.email == owner_email))
        if not new_owner:
            raise HTTPException(status_code=404, detail=f"User '{owner_email}' not found")
        event.owner_id = new_owner.id

    for field, value in data.items():
        setattr(event, field, value)

    await session.commit()

    stmt = select(Event).where(Event.id == event.id).options(selectinload(Event.projects))
    event = await scalar_one_or_none(session, stmt)
    return EventPrivate.model_validate(event)


@router.get("/series")
async def list_series(
    user: Annotated[User, Depends(require_superadmin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[EventSeriesPublic]:
    """List every event series, current one first."""
    series = await scalar_all(session, select(EventSeries))
    series.sort(key=lambda s: (not s.is_current, s.name.lower()))
    return [EventSeriesPublic.model_validate(s) for s in series]


@router.post("/series")
async def create_series(
    body: EventSeriesCreate,
    user: Annotated[User, Depends(require_superadmin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventSeriesPublic:
    """Create a series. Events join it by carrying its slug in feature_flags_csv."""
    slug = slugify(body.slug or body.name)[:50]
    if not slug:
        raise HTTPException(status_code=400, detail="Series needs a name")
    if await scalar_one_or_none(session, select(EventSeries).where(EventSeries.slug == slug)):
        raise HTTPException(status_code=400, detail=f"A series called '{slug}' already exists")
    series = EventSeries(slug=slug, name=body.name.strip())
    session.add(series)
    await session.commit()
    await session.refresh(series)
    return EventSeriesPublic.model_validate(series)


@router.post("/series/{series_id}/current")
async def make_series_current(
    series_id: Annotated[UUID, Path(title="Series ID")],
    user: Annotated[User, Depends(require_superadmin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventSeriesPublic:
    """Make this the current series: its events become the official event list."""
    target = await session.get(EventSeries, series_id)
    if not target:
        raise HTTPException(status_code=404, detail="Series not found")
    # Clear first: a unique index allows only one current series at a time
    for s in await scalar_all(session, select(EventSeries).where(EventSeries.is_current)):
        s.is_current = False
    await session.flush()
    target.is_current = True
    await session.commit()
    await session.refresh(target)
    return EventSeriesPublic.model_validate(target)


@router.get("/users")
async def list_users(
    user: Annotated[User, Depends(require_superadmin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Page[UserSummary]:
    """List all users."""
    return await paginate(session, select(User))


@router.patch("/users/{user_id}/access")
async def update_user_access(
    user_id: Annotated[UUID, Path(title="User ID")],
    update: UserAccessUpdate,
    user: Annotated[User, Depends(require_superadmin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserSummary:
    """Grant/revoke admin and superadmin access for a user."""
    target = await session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    data = update.model_dump(exclude_unset=True)

    if (
        target.id == user.id
        and "is_superadmin" in data
        and data["is_superadmin"] is False
    ):
        raise HTTPException(status_code=400, detail="You cannot revoke your own superadmin access")

    if "is_superadmin" in data:
        target.is_superadmin = data["is_superadmin"]
    if "is_admin" in data:
        target.is_admin = data["is_admin"]
    if "admin_permissions_csv" in data:
        target.admin_permissions_csv = _validate_permissions_csv(data["admin_permissions_csv"] or "")

    await session.commit()
    await session.refresh(target)
    return UserSummary.model_validate(target)


@router.get("/events/{event_id}/projects/csv")
async def export_projects_csv(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(require_superadmin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Export one event's projects as a CSV attachment for superadmin backups/analysis."""
    event = await session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    stmt = (
        select(Project)
        .options(
            selectinload(Project.owner),
            selectinload(Project.event),
            selectinload(Project.collaborators),
            selectinload(Project.votes),
        )
        .where(Project.event_id == event_id)
        .order_by(Project.name, Project.id)
    )
    result = await session.exec(stmt)
    projects = result.all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "project_id",
            "project_name",
            "event_id",
            "event_name",
            "event_slug",
            "event_phase",
            "event_deleted_at",
            "owner_id",
            "owner_email",
            "owner_display_name",
            "collaborator_count",
            "collaborator_emails",
            "collaborator_display_names",
            "repo",
            "demo",
            "image_url",
            "description",
            "hours_spent",
            "join_code",
            "validation_status",
            "validation_message",
            "points",
            "vote_count",
        ]
    )

    for project in projects:
        collaborators = project.collaborators or []
        collaborator_emails = ";".join(
            c.email for c in collaborators if c and c.email
        )
        collaborator_names = ";".join(
            c.display_name for c in collaborators if c and c.display_name
        )
        writer.writerow(
            [
                str(project.id),
                project.name,
                str(project.event_id),
                project.event.name if project.event else "",
                project.event.slug if project.event else "",
                project.event.phase if project.event else "",
                project.event.deleted_at.isoformat()
                if project.event and project.event.deleted_at
                else "",
                str(project.owner_id),
                project.owner.email if project.owner else "",
                project.owner.display_name if project.owner else "",
                len(collaborators),
                collaborator_emails,
                collaborator_names,
                project.repo,
                project.demo,
                project.image_url,
                project.description,
                project.hours_spent,
                project.join_code,
                project.validation_status,
                project.validation_message,
                project.points,
                len(project.votes or []),
            ]
        )

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"podium_projects_{event.slug}_{timestamp}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
