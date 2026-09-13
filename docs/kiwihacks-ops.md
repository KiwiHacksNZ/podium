# Kiwihacks Podium Ops

This file is the fast handoff for maintainers and future agents.

## Environments

- Frontend: Vercel project `kiwihacks-podium` (root dir: `frontend/`)
- Backend: self-hosted Docker deployment (SSH + `docker compose`)
- Public app URL: `https://vote.kiwihacks.com`

## Required Backend Env Vars

- `PODIUM_DATABASE_URL`
- `PODIUM_JWT_SECRET`
- `PODIUM_PRODUCTION_URL`
- `PODIUM_ACTIVE_EVENT_SERIES` (for production this should be `flagship`)
- `PODIUM_TURNSTILE_SECRET_KEY`
- `PODIUM_TURNSTILE_HOSTNAMES` (`vote.kiwihacks.com` in production)
- `PODIUM_CORS_ORIGINS` (for example `https://vote.kiwihacks.com`)
- `PODIUM_ALLOWED_HOSTS` (the backend hostname, without a scheme)
- `PODIUM_TRUSTED_PROXY_HOSTS` (explicit cloudflared/container proxy IPs or CIDRs)

The image sets `ENV_FOR_DYNACONF=production`. Do not override it in production.
Remote PostgreSQL URLs must use certificate-verified TLS. Add
`sslmode=verify-full`; add `sslrootcert=/path/to/ca.pem` for a private CA.

Optional but important:

- `PODIUM_SSO_CLIENT_ID`
- `PODIUM_SSO_CLIENT_SECRET`
- `PODIUM_LOOPS_API_KEY`
- `PODIUM_LOOPS_TRANSACTIONAL_ID`
- `PODIUM_SENTRY_DSN`
- Frontend `PUBLIC_SENTRY_DSN` in Vercel

Required frontend variables in Vercel:

- `PUBLIC_API_URL`
- `PUBLIC_TURNSTILE_SITE_KEY` only when overriding the built-in production site key

The Cloudflare Turnstile widget must allow `vote.kiwihacks.com` as a hostname.

## Critical Event Rule

The event's `feature_flags_csv` must include the same value as `PODIUM_ACTIVE_EVENT_SERIES`.

Production expectation:

- `PODIUM_ACTIVE_EVENT_SERIES=flagship`
- active event `feature_flags_csv=flagship`

If these do not match, the event will not appear as expected.

## Deploy Frontend

```bash
cd frontend
vercel --prod --yes
```

## Deploy Backend (Podium)

```bash
ssh -o StrictHostKeyChecking=accept-new <ssh-user>@<backend-host>
cd <repo-path-on-server>
docker compose up -d --build podium-backend
```

The backend runs `alembic upgrade head` before starting. The host uploads
directory must be writable by container UID `1000`.

## Check Backend Health

```bash
curl -fsS https://<backend-domain>/health/ready
```

Expected: HTTP `200`.

## Make User Superadmin

```bash
ssh -o StrictHostKeyChecking=accept-new <ssh-user>@<backend-host>
cd <repo-path-on-server>
docker compose exec -T podium-backend python - <<'PY'
import asyncio
from sqlmodel import select
from podium.db.postgres.base import async_session_factory
from podium.db.postgres import User

EMAIL = "replace@domain.com"

async def main():
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.email == EMAIL))).scalars().first()
        if user is None:
            print("NOT_FOUND")
            return
        user.is_superadmin = True
        s.add(user)
        await s.commit()
        print("OK", user.email, user.is_superadmin)

asyncio.run(main())
PY
```

## Common Failures

- `502` from backend domain: backend container down or reverse-proxy route issue.
- Magic link says sent but no email arrives: missing `PODIUM_LOOPS_API_KEY` or wrong `PODIUM_LOOPS_TRANSACTIONAL_ID`.
- OAuth button present but fails: missing `PODIUM_SSO_CLIENT_ID/SECRET` or callback URL mismatch.
