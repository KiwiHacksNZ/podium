import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import sentry_sdk
from fastapi import FastAPI, HTTPException
from fastapi_pagination import add_pagination
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from podium.limiter import limiter, get_user_or_ip_for_sentry
from podium.config import comma_separated_setting, settings, validate_runtime_security

sentry_sdk.init(
    dsn=settings.get("sentry_dsn", ""),
    send_default_pii=False,
    traces_sample_rate=float(settings.get("sentry_traces_sample_rate", 0.1)),
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    from podium.db.postgres import engine
    from podium.cache import init_redis, close_redis
    validate_runtime_security()
    if not engine:
        raise RuntimeError("PostgreSQL is not configured. Set PODIUM_DATABASE_URL.")

    await init_redis()

    yield

    await close_redis()


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Required for request.base_url to reflect https behind the configured reverse proxy.
trusted_proxy_hosts = comma_separated_setting("trusted_proxy_hosts")
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted_proxy_hosts)

allowed_hosts = comma_separated_setting("allowed_hosts")
if allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

class SentryUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        user_key = get_user_or_ip_for_sentry(request)
        if "@" in user_key:
            sentry_sdk.set_user({"email": user_key})
        else:
            sentry_sdk.set_user({"ip_address": user_key})
        return await call_next(request)


app.add_middleware(SentryUserMiddleware)

origins = comma_separated_setting("cors_origins", str(settings.production_url))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Cache-Control",
        "Content-Type",
        "Pragma",
        "X-Turnstile-Token",
    ],
)

uploads_dir = Path(os.getenv("PODIUM_UPLOADS_DIR", "./uploads")) / "project-images"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/project-images", StaticFiles(directory=uploads_dir), name="project-images")


@app.get("/health/live", include_in_schema=False)
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
async def health_ready() -> dict[str, str]:
    from podium.db.postgres import async_session_factory

    if not async_session_factory:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


# Dynamically import all routers from the routers directory
routers_dir = Path(__file__).parent / "routers"
for router_file in routers_dir.glob("*.py"):
    if router_file.stem != "__init__":
        module = __import__(
            f"podium.routers.{router_file.stem}", fromlist=["router"]
        )
        if hasattr(module, "router"):
            app.include_router(module.router)

add_pagination(app)


def main():
    import uvicorn

    uvicorn.run("podium.main:app", host="0.0.0.0", port=8000, reload=True)
