# Local Development

## Prerequisites

- Docker (for Postgres)
- Node.js + Bun (frontend)
- Python + uv (backend)

## Quick Start

```bash
# Start Postgres + backend API
docker compose up -d

# Run migrations (first boot + after schema changes)
cd backend && PODIUM_DATABASE_URL=postgresql+asyncpg://postgres:localpass@localhost:5432/podium?sslmode=disable uv run alembic upgrade head

# Start frontend (separate terminal)
cd frontend && bun dev
```

## Docker Compose

The root `docker-compose.yaml` starts Postgres on `5432` and backend on `8000`.

First time:
```bash
cp .env.example .env
docker compose up -d
```

Redis is optional and off by default — run it only when needed:
```bash
docker compose --profile cache up -d
```

Caching is silently disabled unless `PODIUM_REDIS_URL` is set. If backend runs in Docker, use `redis://podium-redis:6379`.

## Turnstile (CAPTCHA)

The production site key is the frontend default. Set `PUBLIC_TURNSTILE_SITE_KEY=disabled` to hide the widget locally while backend verification is disabled.

To test with Turnstile active, use [Cloudflare's test keys](https://developers.cloudflare.com/turnstile/troubleshooting/testing/) (no account needed, work on localhost):

| `PUBLIC_TURNSTILE_SITE_KEY` | Behavior |
|---|---|
| `1x00000000000000000000AA` | Always passes (visible widget) |
| `2x00000000000000000000AB` | Always blocks (visible widget) |
| `3x00000000000000000000FF` | Forces interaction |

Test keys generate dummy tokens (`XXXX.DUMMY.TOKEN.XXXX`) that your real production secret will reject. Set `PODIUM_TURNSTILE_SECRET_KEY` to a matching test secret:

Also set `PODIUM_TURNSTILE_HOSTNAMES=localhost,127.0.0.1`.

| `PODIUM_TURNSTILE_SECRET_KEY` | Behavior |
|---|---|
| `1x0000000000000000000000000000000AA` | Always passes |
| `2x0000000000000000000000000000000AA` | Always fails |
| `3x0000000000000000000000000000000AA` | Returns "token already spent" |

## Regenerate API Client

After backend API changes:
```bash
cd frontend && bun run openapi-ts
```

## Lint & Typecheck

```bash
cd backend && uv run ruff check --fix
cd frontend && bun run svelte-check
```
