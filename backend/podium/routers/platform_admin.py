"""
Platform-admin endpoints.

Admins (and superadmins) can be granted scoped permissions by superadmins.
Default admin capabilities include:
  - view all events
  - remove projects
  - export project CSVs
"""

import csv
from datetime import UTC, datetime
from io import StringIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from podium.authz import require_admin_permission
from podium.constants import EventPhase, PlatformAdminPermission
from podium.db.postgres.queries import resolve_event_slug
from podium.db.postgres import (
    Event,
    EventPrivate,
    EventUpdate,
    Project,
    ProjectPrivate,
    User,
    get_session,
    scalar_all,
    scalar_one_or_none,
)
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])


class EventCreate(BaseModel):
    name: str
    description: str = ""
    phase: str = EventPhase.DRAFT
    demo_links_optional: bool = False
    repo_validation: str = "github"
    demo_validation: str = "none"
    custom_validator: str | None = None
    feature_flags_csv: str = ""
    # Custom URL slug; generated from the name when omitted
    slug: str | None = None


async def _get_event_or_404(session: AsyncSession, event_id: UUID) -> Event:
    event = await session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/events")
async def list_all_events(
    user: Annotated[
        User,
        Depends(require_admin_permission(PlatformAdminPermission.VIEW_ALL_EVENTS.value)),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Page[EventPrivate]:
    """List all events, including soft-deleted ones."""
    return await paginate(session, select(Event).options(selectinload(Event.projects)))


@router.get("/events/{event_id}")
async def get_event(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[
        User,
        Depends(require_admin_permission(PlatformAdminPermission.VIEW_ALL_EVENTS.value)),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventPrivate:
    """Get one event, including admin-only fields."""
    stmt = (
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.projects))
    )
    event = await scalar_one_or_none(session, stmt)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventPrivate.model_validate(event)


@router.get("/events/{event_id}/projects")
async def get_event_projects(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[
        User,
        Depends(require_admin_permission(PlatformAdminPermission.VIEW_ALL_EVENTS.value)),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProjectPrivate]:
    """List projects for one event."""
    await _get_event_or_404(session, event_id)

    projects = await scalar_all(
        session,
        select(Project)
        .where(Project.event_id == event_id)
        .options(
            selectinload(Project.votes),
            selectinload(Project.owner),
            selectinload(Project.collaborators),
        )
        .order_by(Project.name, Project.id),
    )
    return [ProjectPrivate.model_validate(project) for project in projects]


@router.get("/events/{event_id}/projects/csv")
async def export_projects_csv(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[
        User,
        Depends(require_admin_permission(PlatformAdminPermission.EXPORT_PROJECTS_CSV.value)),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Export one event's projects as a CSV attachment."""
    event = await _get_event_or_404(session, event_id)

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
        collaborator_emails = ";".join(c.email for c in collaborators if c and c.email)
        collaborator_names = ";".join(c.display_name for c in collaborators if c and c.display_name)
        writer.writerow(
            [
                str(project.id),
                project.name,
                str(project.event_id),
                project.event.name if project.event else "",
                project.event.slug if project.event else "",
                project.event.phase if project.event else "",
                project.event.deleted_at.isoformat() if project.event and project.event.deleted_at else "",
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


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: Annotated[UUID, Path(title="Project ID")],
    user: Annotated[
        User,
        Depends(require_admin_permission(PlatformAdminPermission.REMOVE_PROJECTS.value)),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Delete any project (admin permission: remove_projects)."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await session.delete(project)
    await session.commit()
    return {"message": "Project deleted"}


@router.post("/events")
async def create_event(
    event_data: EventCreate,
    user: Annotated[
        User,
        Depends(require_admin_permission(PlatformAdminPermission.CREATE_EVENTS.value)),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventPrivate:
    """Create a real event (admin permission: create_events)."""
    try:
        slug = await resolve_event_slug(session, event_data.slug, event_data.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    event = Event(
        **event_data.model_dump(exclude={"slug"}),
        slug=slug,
        owner_id=user.id,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)

    stmt = select(Event).where(Event.id == event.id).options(selectinload(Event.projects))
    event = await scalar_one_or_none(session, stmt)
    return EventPrivate.model_validate(event)


@router.patch("/events/{event_id}")
async def update_event(
    event_id: Annotated[UUID, Path(title="Event ID")],
    update: EventUpdate,
    user: Annotated[
        User,
        Depends(require_admin_permission(PlatformAdminPermission.EDIT_EVENTS.value)),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventPrivate:
    """Update event fields (admin permission: edit_events)."""
    event = await _get_event_or_404(session, event_id)

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(event, field, value)

    await session.commit()

    stmt = select(Event).where(Event.id == event.id).options(selectinload(Event.projects))
    event = await scalar_one_or_none(session, stmt)
    return EventPrivate.model_validate(event)


@router.delete("/events/{event_id}")
async def soft_delete_event(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[
        User,
        Depends(require_admin_permission(PlatformAdminPermission.DELETE_EVENTS.value)),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Soft-delete an event (admin permission: delete_events)."""
    event = await _get_event_or_404(session, event_id)
    if event.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Event is already deleted")

    event.deleted_at = datetime.now(UTC)
    await session.commit()
    return {"message": "Event soft-deleted", "deleted_at": event.deleted_at.isoformat()}
