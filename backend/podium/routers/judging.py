"""
Judging endpoints.

Judges score every project in an event 1-10 on four criteria while the event's
judging round is open. Organizers then lock in the top FINALIST_COUNT projects by
mean judge score; those finalists are what attendees rank.

Judging access is per event: an organizer either adds a judge directly or hands
out the event's 6-digit judge code, which the judge redeems here.
"""

from hashlib import sha256
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload

from podium.authz import get_judged_event
from podium.config import settings
from podium.constants import BAD_ACCESS, JudgingCriterion
from podium.limiter import limiter
from podium.db.postgres import (
    Event,
    EventJudgeLink,
    JudgeScore,
    JudgeScorePublic,
    JudgeScoreUpsert,
    Project,
    User,
    get_session,
    scalar_all,
    scalar_one_or_none,
)
from podium.routers.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    _set_access_cookie,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/judging", tags=["judging"])


class JudgeProject(BaseModel):
    """A project as the judge sees it, with their own score if already given."""

    id: UUID
    name: str
    repo: str
    demo: str
    description: str
    image_url: str
    owner_display_name: str
    my_score: JudgeScorePublic | None = None


class JudgeProjects(BaseModel):
    projects: list[JudgeProject]


class RedeemJudgeCode(BaseModel):
    code: str
    name: str
    email: str


class JudgeCodeRedeemed(BaseModel):
    access_token: str
    token_type: str
    event_id: UUID
    event_name: str
    event_slug: str


class JudgeResult(BaseModel):
    """Aggregate judge standing for one project."""

    project_id: UUID
    name: str
    judge_score: float
    judge_count: int
    is_finalist: bool
    averages: dict[str, float]


def _score_to_public(score: JudgeScore) -> JudgeScorePublic:
    return JudgeScorePublic(
        project_id=score.project_id,
        originality=score.originality,
        technicality=score.technicality,
        theme=score.theme,
        usability=score.usability,
        total=score.total,
        updated_at=score.updated_at,
    )


@router.post("/redeem")
# Codes are only 6 digits, so throttle guessing.
@limiter.limit("5/minute")
async def redeem_judge_code(
    request: Request,
    body: RedeemJudgeCode,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JudgeCodeRedeemed:
    """Claim judge access with the 6-digit code, a name and an email — no sign-in.

    Provisions a lightweight, code-only judge account keyed by (event, email) so
    re-entering the same code and email resumes prior scoring, then returns an
    access token the frontend uses like a normal login. The email is also kept
    against the event so organisers can contact their judges.
    """
    code = body.code.strip()
    if not (len(code) == 6 and code.isdigit()):
        raise HTTPException(status_code=400, detail="Judge codes are 6 digits")

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Enter your name")

    contact_email = body.email.strip().lower()
    if "@" not in contact_email or "." not in contact_email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email address")

    event = await scalar_one_or_none(
        session, select(Event).where(Event.judge_code == code)
    )
    if not event or event.deleted_at is not None:
        raise HTTPException(status_code=404, detail="That judge code isn't valid")

    # Deterministic placeholder identity: the same email redeeming the same
    # event resumes prior scoring. Deliberately NOT keyed on the address itself
    # — a judge code must never mint a session for someone's real account, so
    # the login identity stays inside the unroutable @judge.invalid namespace
    # and the address they gave is kept on the link row instead.
    digest = sha256(f"{contact_email}:{event.id}".encode()).hexdigest()[:32]
    email = f"judge-{digest}@judge.invalid"

    judge = await scalar_one_or_none(
        session, select(User).where(User.email == email)
    )
    if judge is None:
        judge = User(email=email, first_name=name[:50], display_name=name[:255])
        session.add(judge)
        await session.commit()
        await session.refresh(judge)

    already = await scalar_one_or_none(
        session,
        select(EventJudgeLink).where(
            EventJudgeLink.event_id == event.id, EventJudgeLink.user_id == judge.id
        ),
    )
    if already:
        already.judge_email = contact_email
    else:
        session.add(
            EventJudgeLink(
                event_id=event.id, user_id=judge.id, judge_email=contact_email
            )
        )
    await session.commit()

    token = create_access_token(
        data={"sub": email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
    )
    _set_access_cookie(response, token)
    return JudgeCodeRedeemed(
        access_token=token,
        token_type="access",
        event_id=event.id,
        event_name=event.name,
        event_slug=event.slug,
    )


@router.get("/{event_id}/projects")
async def list_projects_to_judge(
    event_id: Annotated[UUID, Path(title="Event ID")],
    judge: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JudgeProjects:
    """Every project in the event, with this judge's existing scores."""
    event = await get_judged_event(event_id, judge, session)
    if not event.judging_open:
        raise HTTPException(
            status_code=403, detail="Judging is not open for this event"
        )

    projects = await scalar_all(
        session,
        select(Project)
        .where(Project.event_id == event_id)
        .options(selectinload(Project.owner))
        .order_by(Project.name),
    )
    my_scores = {
        s.project_id: s
        for s in await scalar_all(
            session,
            select(JudgeScore).where(
                JudgeScore.event_id == event_id, JudgeScore.judge_id == judge.id
            ),
        )
    }

    return JudgeProjects(
        projects=[
            JudgeProject(
                id=p.id,
                name=p.name,
                repo=p.repo,
                demo=p.demo,
                description=p.description,
                image_url=p.image_url,
                owner_display_name=p.owner_display_name,
                my_score=(
                    _score_to_public(my_scores[p.id]) if p.id in my_scores else None
                ),
            )
            for p in projects
        ]
    )


@router.put("/{event_id}/scores/{project_id}")
async def score_project(
    event_id: Annotated[UUID, Path(title="Event ID")],
    project_id: Annotated[UUID, Path(title="Project ID")],
    scores: JudgeScoreUpsert,
    judge: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JudgeScorePublic:
    """Create or replace this judge's score for one project."""
    event = await get_judged_event(event_id, judge, session)
    if not event.judging_open:
        raise HTTPException(
            status_code=403, detail="Judging is not open for this event"
        )

    project = await scalar_one_or_none(
        session,
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.collaborators)),
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.event_id != event_id:
        raise HTTPException(status_code=400, detail="Project is not in the event")
    if judge.id == project.owner_id or judge in project.collaborators:
        raise HTTPException(
            status_code=403, detail="Judges cannot score their own project"
        )

    existing = await scalar_one_or_none(
        session,
        select(JudgeScore).where(
            JudgeScore.judge_id == judge.id, JudgeScore.project_id == project_id
        ),
    )
    if existing:
        for criterion in JudgingCriterion:
            setattr(existing, criterion.value, getattr(scores, criterion.value))
        existing.updated_at = datetime.now(timezone.utc)
        score = existing
    else:
        score = JudgeScore.model_validate(
            scores,
            update={
                "judge_id": judge.id,
                "project_id": project_id,
                "event_id": event_id,
            },
        )
        session.add(score)

    await session.commit()
    await session.refresh(score)
    return _score_to_public(score)


@router.get("/{event_id}/results")
async def judging_results(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[JudgeResult]:
    """Aggregate judge standings, best first. This event's judges, its owner, and
    superadmins can see this."""
    stmt = (
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.judges))
    )
    event = await scalar_one_or_none(session, stmt)
    if not event or event.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Event not found")
    is_organizer = event.owner_id == user.id or user.is_superadmin
    if not is_organizer and user.id not in {j.id for j in event.judges}:
        raise BAD_ACCESS

    projects = await scalar_all(
        session,
        select(Project)
        .where(Project.event_id == event_id)
        .options(selectinload(Project.judge_scores)),
    )

    results = [
        JudgeResult(
            project_id=p.id,
            name=p.name,
            judge_score=p.judge_score,
            judge_count=p.judge_count,
            is_finalist=p.is_finalist,
            averages={
                criterion.value: (
                    round(
                        sum(getattr(s, criterion.value) for s in p.judge_scores)
                        / len(p.judge_scores),
                        2,
                    )
                    if p.judge_scores
                    else 0.0
                )
                for criterion in JudgingCriterion
            },
        )
        for p in projects
    ]
    results.sort(key=lambda r: (r.judge_score, r.judge_count), reverse=True)
    return results


# =============================================================================
# TEST-ONLY ENDPOINT
# =============================================================================


@router.post("/test/{event_id}/grant-judge")
async def grant_self_judge(
    event_id: Annotated[UUID, Path(title="Event ID")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    """Make the calling user a judge for this event, so e2e tests don't need the
    code-redemption dance. Only available when enable_test_endpoints is true."""
    if not getattr(settings, "enable_test_endpoints", False):
        raise HTTPException(status_code=404, detail="Not found")

    event = await session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    already = await scalar_one_or_none(
        session,
        select(EventJudgeLink).where(
            EventJudgeLink.event_id == event_id, EventJudgeLink.user_id == user.id
        ),
    )
    if not already:
        session.add(EventJudgeLink(event_id=event_id, user_id=user.id))
        await session.commit()
    return {"granted": True}
