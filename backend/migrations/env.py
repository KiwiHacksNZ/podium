"""
Alembic Migration Environment
=============================
This file runs whenever you execute an alembic command.
It connects to the database and applies/generates migrations.

You rarely need to edit this file. The main things it does:
1. Loads all SQLModel table definitions (so Alembic knows your schema)
2. Connects to the database using PODIUM_DATABASE_URL from the environment
3. Runs the migration(s)
"""

import os
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Import all models so SQLModel.metadata is populated.
# This single import loads everything via db/postgres/__init__.py
from podium.db import postgres  # noqa: F401

# Alembic config object (reads from alembic.ini)
config = context.config
requested_sslmode: str | None = None

# Get database URL from environment (PODIUM_DATABASE_URL, e.g. from .env)
database_url = os.environ.get("PODIUM_DATABASE_URL") or os.environ.get("DATABASE_URL")
if database_url:
    # Alembic needs a sync driver. Convert asyncpg -> psycopg2
    sync_url = database_url.replace("+asyncpg", "+psycopg2")
    # Strip sslrootcert and sslmode from the URL — psycopg2 rejects sslmode=require
    # when sslrootcert=system is present. sslmode=require is re-applied via connect_args.
    parsed = urlparse(sync_url)
    if parsed.query:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        requested_sslmode = qs.get("sslmode", [None])[-1]
        qs.pop("sslrootcert", None)
        qs.pop("sslmode", None)
        sync_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))
    config.set_main_option("sqlalchemy.url", sync_url)

# Tell Alembic about our table definitions
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live database connection.
    
    Useful for generating SQL scripts to run manually.
    Usage: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live database connection.

    This is the normal mode - connects to the database and applies changes.
    """
    url = config.get_main_option("sqlalchemy.url") or ""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    local_hosts = {"localhost", "127.0.0.1", "::1", "podium-pg"}

    # Respect explicit sslmode=disable from PODIUM_DATABASE_URL.
    # Otherwise keep existing behavior: require SSL for non-local hosts.
    connect_args: dict = {}
    if requested_sslmode != "disable" and (
        requested_sslmode == "require" or (requested_sslmode is None and host and host not in local_hosts)
    ):
        connect_args["sslmode"] = "require"

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


# Run in appropriate mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
