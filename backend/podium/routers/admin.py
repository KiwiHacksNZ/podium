"""
Admin/organizer endpoints. All routes require the requesting user to own the event
(or be a superadmin, which bypasses the ownership check).
Organizers can view event details, attendees, votes, referrals, and the leaderboard,
and can remove attendees.
"""

from datetime import datetime
from secrets import randbelow
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import func
from sqlalchemy.orm import selectinload, Load

from podium.db.postgres import (
    User,
    Event,
    EventJudgeLink,
    EventPrivate,
    EventUpdate,
    Project,
    ProjectPrivate,
    Vote,
    VoteAuditLog,
    Referral,
    get_session,
    scalar_one_or_none,
    scalar_all,
)
from podium.routers.auth import get_current_user
from podium.constants import BAD_ACCESS, FINALIST_COUNT
from podium.cache import cache_delete

router = APIRouter(prefix="/events/admin", tags=["events"])


class UserAttendee(BaseModel):
    id: UUID
    email: str
    display_name: str
    first_name: str
    last_name: str
    # Only set for code-only judges, whose `email` is an unroutable placeholder.
    judge_email: str | None = None


class VoteResponse(BaseModel):
    id: UUID
    voter_id: UUID
    project_id: UUID
    event_id: UUID
    created_at: datetime | None = None
    ip_address: str = ""
    user_agent: str = ""


class VoteAuditResponse(BaseModel):
    id: UUID
    event_id: UUID
    project_id: UUID
    voter_id: UUID
    actor_id: UUID
    vote_id: UUID | None = None
    action: str
    ip_address: str
    user_agent: str
    reason: str
    created_at: datetime


class VoteSuspicionResponse(BaseModel):
    kind: str
    message: str
    voter_id: UUID | None = None
    ip_address: str = ""
    count: int = 0


class JudgeEmail(BaseModel):
    email: str


class JudgeCodeResponse(BaseModel):
    judge_code: str


class FinalistResponse(BaseModel):
    project_id: UUID
    name: str
    judge_score: float
    judge_count: int


class ReferralResponse(BaseModel):
    id: UUID
    content: str
    user_id: UUID
    event_id: UUID


async def get_owned_event(
    event_id: UUID, user: User, session: AsyncSession, *extra_loads: Load
) -> Event:
    """Load an event by ID, asserting ownership (or superadmin).

    Pass additional selectinload() calls to load relationships in the same query,
    avoiding a second round-trip:
        event = await get_owned_event(id, user, session, selectinload(Event.attendees))
    """
    stmt = (
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.projects), *extra_loads)
    )
    event = await scalar_one_or_none(session, stmt)
    if not event or (event.owner_id != user.id and not user.is_superadmin):
        raise BAD_ACCESS
    return event


@router.get("/{event_id}")
async def get_event_admin(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventPrivate:
    event = await get_owned_event(event_id, user, session)
    return EventPrivate.model_validate(event)


@router.patch("/{event_id}")
async def update_event_admin(
    event_id: Annotated[UUID, Path(title="Event ID")],
    update: EventUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventPrivate:
    """Update an event you own. Only fields provided in the body are changed."""
    event = await get_owned_event(event_id, user, session)

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(event, field, value)

    await session.commit()
    await session.refresh(event)
    return EventPrivate.model_validate(event)


@router.get("/{event_id}/attendees")
async def get_event_attendees(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[UserAttendee]:
    """Get attendees of an event."""
    event = await get_owned_event(event_id, user, session, selectinload(Event.attendees))
    return [
        UserAttendee(
            id=a.id,
            email=a.email,
            display_name=a.display_name,
            first_name=a.first_name,
            last_name=a.last_name,
        )
        for a in event.attendees
    ]


@router.post("/{event_id}/remove-attendee")
async def remove_attendee(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user_id: Annotated[UUID, Body(embed=True)],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Remove an attendee from an event."""
    event = await get_owned_event(event_id, user, session, selectinload(Event.attendees))
    event.attendees = [a for a in event.attendees if a.id != user_id]
    await session.commit()
    return {"message": "Attendee removed"}


@router.get("/{event_id}/judges")
async def get_event_judges(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[UserAttendee]:
    """The users judging this event, with the contact email code-only judges gave."""
    event = await get_owned_event(event_id, user, session, selectinload(Event.judges))
    contact = {
        link.user_id: link.judge_email
        for link in await scalar_all(
            session,
            select(EventJudgeLink).where(EventJudgeLink.event_id == event_id),
        )
    }
    return [
        UserAttendee(
            id=j.id,
            email=j.email,
            display_name=j.display_name,
            first_name=j.first_name,
            last_name=j.last_name,
            judge_email=contact.get(j.id),
        )
        for j in event.judges
    ]


@router.post("/{event_id}/add-judge")
async def add_judge(
    event_id: Annotated[UUID, Path(title="Event ID")],
    body: JudgeEmail,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserAttendee:
    """Add an existing user as a judge for this event, by email."""
    event = await get_owned_event(event_id, user, session, selectinload(Event.judges))

    email = body.email.strip().lower()
    judge = await scalar_one_or_none(session, select(User).where(User.email == email))
    if not judge:
        raise HTTPException(
            status_code=404, detail="No account with that email — ask them to sign up first"
        )
    if judge.id == event.owner_id:
        raise HTTPException(
            status_code=400, detail="The event owner already sees everything a judge does"
        )

    if judge.id not in {j.id for j in event.judges}:
        session.add(EventJudgeLink(event_id=event_id, user_id=judge.id))
        await session.commit()

    return UserAttendee(
        id=judge.id,
        email=judge.email,
        display_name=judge.display_name,
        first_name=judge.first_name,
        last_name=judge.last_name,
    )


@router.post("/{event_id}/remove-judge")
async def remove_judge(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user_id: Annotated[UUID, Body(embed=True)],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Remove a judge from this event. Any scores they already gave are kept."""
    event = await get_owned_event(event_id, user, session, selectinload(Event.judges))
    event.judges = [j for j in event.judges if j.id != user_id]
    await session.commit()
    return {"message": "Judge removed"}


@router.post("/{event_id}/judge-code")
async def rotate_judge_code(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JudgeCodeResponse:
    """Generate a fresh 6-digit judge code for this event, replacing any existing one.

    Hand the code to your judges; they claim judge access with it at /judge.
    Rotating invalidates the old code but does not revoke anyone's judge access.
    """
    event = await get_owned_event(event_id, user, session)

    for _ in range(10):
        code = f"{randbelow(1_000_000):06d}"
        taken = await scalar_one_or_none(
            session, select(Event).where(Event.judge_code == code)
        )
        if not taken:
            event.judge_code = code
            await session.commit()
            return JudgeCodeResponse(judge_code=code)

    raise HTTPException(
        status_code=500, detail="Could not generate an unused judge code"
    )


@router.post("/{event_id}/finalists")
async def lock_in_finalists(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[FinalistResponse]:
    """Lock in the top-scoring projects from judging as the attendee ballot.

    Ranks every project by mean judge score (ties broken by how many judges scored
    it) and marks the top FINALIST_COUNT as finalists, clearing any previous set.
    Only finalists appear on the ballot once this has run.

    Can be re-run while judges are still scoring, but not once attendees have started
    voting — changing the ballot then would leave already-cast votes on projects that
    are no longer finalists.
    """
    await get_owned_event(event_id, user, session)

    votes_cast = await scalar_one_or_none(
        session, select(Vote).where(Vote.event_id == event_id).limit(1)
    )
    if votes_cast:
        raise HTTPException(
            status_code=400,
            detail="Attendees have already started voting — finalists are locked",
        )

    projects = await scalar_all(
        session,
        select(Project)
        .where(Project.event_id == event_id)
        .options(selectinload(Project.judge_scores)),
    )
    scored = [p for p in projects if p.judge_count]
    if not scored:
        raise HTTPException(
            status_code=400, detail="No judge scores yet — nothing to rank"
        )

    scored.sort(key=lambda p: (p.judge_score, p.judge_count), reverse=True)
    finalists = scored[:FINALIST_COUNT]
    finalist_ids = {p.id for p in finalists}
    for project in projects:
        project.is_finalist = project.id in finalist_ids

    await session.commit()
    await cache_delete(f"leaderboard:{event_id}")
    return [
        FinalistResponse(
            project_id=p.id,
            name=p.name,
            judge_score=p.judge_score,
            judge_count=p.judge_count,
        )
        for p in finalists
    ]


@router.get("/{event_id}/leaderboard", response_model=list[ProjectPrivate])
async def get_event_leaderboard(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProjectPrivate]:
    """Get leaderboard for an event (admin only)."""
    await get_owned_event(event_id, user, session)

    projects = await scalar_all(
        session,
        select(Project)
        .where(Project.event_id == event_id)
        .options(
            selectinload(Project.votes),
            selectinload(Project.owner),
            selectinload(Project.collaborators),
        ),
    )
    projects.sort(key=lambda p: p.points, reverse=True)
    return [ProjectPrivate.model_validate(p) for p in projects]


@router.get("/{event_id}/votes")
async def get_event_votes(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[VoteResponse]:
    """Get all votes for an event (admin only)."""
    await get_owned_event(event_id, user, session)
    votes = await scalar_all(session, select(Vote).where(Vote.event_id == event_id))
    return [
        VoteResponse(
            id=v.id,
            voter_id=v.voter_id,
            project_id=v.project_id,
            event_id=v.event_id,
            created_at=v.created_at,
            ip_address=v.ip_address,
            user_agent=v.user_agent,
        )
        for v in votes
    ]


@router.get("/{event_id}/vote-audit")
async def get_event_vote_audit(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[VoteAuditResponse]:
    """Get vote audit log entries for an event (admin only)."""
    await get_owned_event(event_id, user, session)
    logs = await scalar_all(
        session,
        select(VoteAuditLog)
        .where(VoteAuditLog.event_id == event_id)
        .order_by(VoteAuditLog.created_at.desc()),
    )
    return [
        VoteAuditResponse(
            id=log.id,
            event_id=log.event_id,
            project_id=log.project_id,
            voter_id=log.voter_id,
            actor_id=log.actor_id,
            vote_id=log.vote_id,
            action=log.action,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            reason=log.reason,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/{event_id}/vote-suspicion")
async def get_event_vote_suspicion(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[VoteSuspicionResponse]:
    """Return lightweight anti-abuse signals for admin review."""
    event = await get_owned_event(event_id, user, session)
    findings: list[VoteSuspicionResponse] = []

    over_limit_rows = (
        await session.exec(
            select(Vote.voter_id, func.count(Vote.id))
            .where(Vote.event_id == event_id)
            .group_by(Vote.voter_id)
            .having(func.count(Vote.id) > event.max_votes_per_user)
        )
    ).all()
    for voter_id, count in over_limit_rows:
        findings.append(
            VoteSuspicionResponse(
                kind="over_limit",
                voter_id=voter_id,
                count=count,
                message=f"Voter has {count} votes; event allows {event.max_votes_per_user}.",
            )
        )

    shared_ip_rows = (
        await session.exec(
            select(Vote.ip_address, func.count(func.distinct(Vote.voter_id)))
            .where(Vote.event_id == event_id, Vote.ip_address != "")
            .group_by(Vote.ip_address)
            .having(func.count(func.distinct(Vote.voter_id)) >= 4)
        )
    ).all()
    for ip_address, count in shared_ip_rows:
        findings.append(
            VoteSuspicionResponse(
                kind="shared_ip",
                ip_address=ip_address,
                count=count,
                message=f"{count} voters used this IP address.",
            )
        )

    burst_rows = (
        await session.exec(
            select(Vote.voter_id, func.count(Vote.id))
            .where(Vote.event_id == event_id)
            .group_by(Vote.voter_id, func.date_trunc("minute", Vote.created_at))
            .having(func.count(Vote.id) >= 3)
        )
    ).all()
    for voter_id, count in burst_rows:
        findings.append(
            VoteSuspicionResponse(
                kind="vote_burst",
                voter_id=voter_id,
                count=count,
                message=f"Voter cast {count} votes in one minute.",
            )
        )

    return findings


@router.get("/{event_id}/referrals")
async def get_event_referrals(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ReferralResponse]:
    """Get all referrals for an event (admin only)."""
    await get_owned_event(event_id, user, session)
    referrals = await scalar_all(
        session, select(Referral).where(Referral.event_id == event_id)
    )
    return [
        ReferralResponse(id=r.id, content=r.content, user_id=r.user_id, event_id=r.event_id)
        for r in referrals
    ]
