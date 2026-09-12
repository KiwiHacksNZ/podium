FROM python:3.13-slim

ENV UV_LINK_MODE=copy \
    ENV_FOR_DYNACONF=production \
    PODIUM_UPLOADS_DIR=/app/uploads \
    PATH="/app/.venv/bin:$PATH"

COPY . /app
WORKDIR /app

# curl + ca-certificates are needed for the healthcheck below.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.11 /uv /uvx /bin/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable && \
    useradd --create-home --shell /usr/sbin/nologin podium && \
    mkdir -p /app/uploads && \
    chown -R podium:podium /app/uploads

USER podium

# Secrets are provided as environment variables (see docker-compose.portainer.yml,
# which exports them from a mounted env file, or `docker run --env-file`).
CMD ["/bin/bash", "-c", "alembic upgrade head && exec python -m uvicorn podium.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/health/ready >/dev/null || exit 1

# To debug:
# docker build -t podium .
# docker run --env-file .env -p 8000:8000 podium
