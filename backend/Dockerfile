FROM python:3.13-slim

ENV UV_LINK_MODE=copy \
    ENV_FOR_DYNACONF=production \
    PODIUM_UPLOADS_DIR=/app/uploads \
    PATH="/app/.venv/bin:$PATH"

COPY . /app
WORKDIR /app

# Install Doppler CLI
# ENV DOPPLER_ENV=1
RUN apt-get update && apt-get install -y --no-install-recommends apt-transport-https ca-certificates curl gnupg && \
    curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" | tee /etc/apt/sources.list.d/doppler-cli.list && \
    apt-get update && \
    apt-get -y install --no-install-recommends doppler && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.11 /uv /uvx /bin/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable && \
    useradd --create-home --shell /usr/sbin/nologin podium && \
    mkdir -p /app/uploads && \
    chown -R podium:podium /app/uploads

USER podium

# Use Doppler to inject runtime secrets at container start. Ensure DOPPLER_TOKEN or an agent is available at runtime.
ENTRYPOINT ["doppler", "run", "--"]
CMD ["/bin/bash", "-c", "alembic upgrade head && exec python -m uvicorn podium.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/health/ready >/dev/null || exit 1

# To debug:
# docker build -t podium .
# Example runtime using Doppler token:
# docker run -e DOPPLER_TOKEN=$DOPPLER_TOKEN --env-file .env -p 8000:8000 podium
