"""
Magic link authentication and JWT session management.

Flow: POST /request-login → email with magic link → GET /verify?token=... → JWT access token
The access token is a short-lived JWT (default 2 days) stored in localStorage by the frontend.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
import jwt
from jwt.exceptions import PyJWTError
import httpx

from podium.config import settings
from podium.constants import BAD_AUTH
from podium.validators.email import is_disposable_email
from sqlalchemy.orm import selectinload
from podium.db.postgres import User, UserPrivate, get_session, scalar_one_or_none, user_to_private, default_display_name
from podium.limiter import limiter

router = APIRouter(tags=["auth"])

SECRET_KEY = settings.jwt_secret
ALGORITHM = str(settings.jwt_algorithm)
ACCESS_TOKEN_EXPIRE_MINUTES: int = settings.jwt_expire_minutes  # type: ignore
MAGIC_LINK_EXPIRE_MINUTES = 30

OAUTH_AUTHORIZE_URL = settings.oauth_authorize_url
OAUTH_TOKEN_URL = settings.oauth_token_url
OAUTH_ME_URL = settings.oauth_me_url


class UserLoginPayload(BaseModel):
    email: str


class LoginRequested(BaseModel):
    message: str


def safe_redirect_path(redirect: str) -> str:
    """Accept only same-origin absolute paths for post-login navigation."""
    redirect = redirect.strip()
    if not redirect.startswith("/") or redirect.startswith("//"):
        return "/"
    return redirect[:2048]


def create_access_token(
    data: dict, expires_delta: timedelta | None = None, token_type: str = "access"
) -> str:
    to_encode = data.copy()
    to_encode.update({"token_type": token_type})
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=MAGIC_LINK_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def send_magic_link(email: str, redirect: str = ""):
    token = create_access_token(
        data={"sub": email},
        expires_delta=timedelta(minutes=15),
        token_type="magic_link",
    )

    query = urlencode({"token": token, "redirect": safe_redirect_path(redirect)})
    # URL fragments are not sent to frontend hosting/CDN logs or referrers.
    magic_link = f"{settings.production_url}/login#{query}"

    if settings.loops_api_key:
        payload = {
            "email": email,
            "transactionalId": settings.loops_transactional_id,
            "dataVariables": {"auth_link": magic_link},
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://app.loops.so/api/v1/transactional",
                    headers={
                        "Authorization": f"Bearer {settings.loops_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to send auth email")
    else:
        print("[WARNING] No Loops API key set. Not sending magic link email.")

    if str(settings.current_env).upper() == "DEVELOPMENT":
        print(f"Development magic link for {email}: {magic_link}")


@router.post("/request-login")
@limiter.limit("5/minute")
async def request_login(
    request: Request,
    user: UserLoginPayload,
    redirect: Annotated[str, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LoginRequested:
    """Send a magic link to the user's email.

    Turnstile is intentionally not required here: the signup flow sends the
    same single-use Turnstile token to both create_user and request_login, so
    validating it twice would break the second call. The rate limiter (keyed
    on user email / IP) provides bot protection instead.
    """
    email = user.email.strip().lower()
    # Block disposable emails from requesting magic links
    if is_disposable_email(email):
        raise HTTPException(status_code=400, detail="Temporary/disposable email addresses aren't allowed — please use your real email")
    existing = await scalar_one_or_none(session, select(User).where(User.email == email))
    if existing is not None:
        await send_magic_link(email, redirect=redirect)
    return LoginRequested(message="If that account exists, a login link has been sent")


class AuthenticatedUser(BaseModel):
    access_token: str
    token_type: str
    user: UserPrivate


@router.get("/verify")
async def verify_token(
    token: Annotated[str, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthenticatedUser:
    """Verify a magic link token and return an access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("token_type")
        if email is None or token_type != "magic_link":
            raise HTTPException(status_code=400, detail="Invalid token")
    except PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid token")

    stmt = select(User).where(User.email == email).options(selectinload(User.votes))
    user = await scalar_one_or_none(session, stmt)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    access_token = create_access_token(
        data={"sub": email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
    )
    return AuthenticatedUser(
        access_token=access_token,
        token_type="access",
        user=user_to_private(user),
    )


@router.get("/auth/sso")
async def sso_login(request: Request) -> RedirectResponse:
    """Initiate OAuth login. Redirects the browser to the authorization page."""
    if not settings.sso_client_id:
        raise HTTPException(status_code=501, detail="OAuth auth is not configured")
    if not OAUTH_AUTHORIZE_URL:
        raise HTTPException(status_code=501, detail="OAuth provider URLs are not configured")
    state = create_access_token(
        data={"sub": "csrf"},
        expires_delta=timedelta(minutes=10),
        token_type="oauth_state",
    )
    # Derived from request so it works in all environments without an env var.
    # Normalize 127.0.0.1 → localhost so the URI matches what's registered with OAuth provider.
    redirect_uri = str(request.base_url).replace("127.0.0.1", "localhost") + "auth/sso/callback"
    params = urlencode({
        "client_id": settings.sso_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "email name",
        "state": state,
    })
    return RedirectResponse(f"{OAUTH_AUTHORIZE_URL}?{params}")


@router.get("/auth/sso/callback")
async def sso_callback(
    request: Request,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RedirectResponse:
    """Handle the OAuth callback, issue a magic-link token, and redirect to the frontend."""
    # Validate CSRF state token
    try:
        state_payload = jwt.decode(state, SECRET_KEY, algorithms=[ALGORITHM])
        if state_payload.get("token_type") != "oauth_state":
            raise HTTPException(status_code=400, detail="Invalid OAuth state")
    except PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    # Exchange authorization code for access token, then fetch user email
    try:
        if not OAUTH_TOKEN_URL or not OAUTH_ME_URL:
            raise HTTPException(status_code=501, detail="OAuth provider URLs are not configured")
        async with httpx.AsyncClient() as hc:
            redirect_uri = str(request.base_url).replace("127.0.0.1", "localhost") + "auth/sso/callback"
            token_resp = await hc.post(OAUTH_TOKEN_URL, data={
                "client_id": settings.sso_client_id,
                "client_secret": settings.sso_client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
                "grant_type": "authorization_code",
            })
            token_resp.raise_for_status()
            hc_access_token = token_resp.json()["access_token"]

            me_resp = await hc.get(OAUTH_ME_URL, headers={"Authorization": f"Bearer {hc_access_token}"})
            me_resp.raise_for_status()
            me = me_resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to authenticate with OAuth provider")
    # OAuth token is discarded — only the email is kept

    identity: dict = me.get("identity", {})
    email: str = identity.get("primary_email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="No email returned from OAuth provider")

    first_name: str = identity.get("first_name", "").strip()
    last_name: str = identity.get("last_name", "").strip()

    stmt = select(User).where(User.email == email).options(selectinload(User.votes))
    user = await scalar_one_or_none(session, stmt)
    if user is None:
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            display_name=default_display_name(first_name, last_name),
        )
        session.add(user)
        await session.commit()
        stmt = select(User).where(User.email == email).options(selectinload(User.votes))
        user = await scalar_one_or_none(session, stmt)
    elif not user.first_name and first_name:
        # Backfill name for existing users who registered before SSO name scope was added
        user.first_name = first_name
        user.last_name = last_name
        user.display_name = default_display_name(first_name, last_name)
        await session.commit()
        stmt = select(User).where(User.email == email).options(selectinload(User.votes))
        user = await scalar_one_or_none(session, stmt)

    # Issue a short-lived magic-link token so the existing frontend /verify flow handles the rest
    token = create_access_token(
        data={"sub": email},
        expires_delta=timedelta(minutes=15),
        token_type="magic_link",
    )
    return RedirectResponse(
        f"{settings.production_url}/login#{urlencode({'token': token})}"
    )


security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Decode JWT and return the authenticated user."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("token_type")
        if email is None or token_type != "access":
            raise HTTPException(status_code=400, detail="Bad JWT")
    except PyJWTError:
        raise BAD_AUTH

    stmt = select(User).where(User.email == email).options(selectinload(User.votes))
    user = await scalar_one_or_none(session, stmt)
    if user is None:
        raise BAD_AUTH
    return user
