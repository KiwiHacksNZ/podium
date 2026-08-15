"""
Application configuration using Dynaconf.

All settings are loaded from environment variables with PODIUM_ prefix,
or from settings.toml/.secrets.toml files. Dynaconf strips the prefix,
so PODIUM_DATABASE_URL becomes settings.database_url.
"""

import os
import sys
from dynaconf import Dynaconf, Validator

# type: ignore

print(f"Using environment: {os.getenv('ENV_FOR_DYNACONF', '')}")
settings = Dynaconf(
    envvar_prefix="PODIUM",
    load_dotenv=True,
    settings_files=["settings.toml", ".secrets.toml"],
    merge_enabled=True,
    environments=True,
)
settings.validators.register(
    validators=[
        # Airtable settings - optional, only needed for scripts/migrate_from_airtable.py
        # Can be removed after production cutover is complete
        Validator(
            "airtable_token",
            default="",
        ),
        Validator(
            "airtable_base_id",
            default="",
        ),
        Validator(
            "airtable_events_table_id",
            default="",
        ),
        Validator(
            "airtable_users_table_id",
            default="",
        ),
        Validator(
            "airtable_referrals_table_id",
            default="",
        ),
        Validator(
            "airtable_votes_table_id",
            default="",
        ),
        Validator(
            "loops_api_key",
            default="",
        ),
        Validator(
            "loops_transactional_id",
            must_exist=True,
        ),
        Validator(
            "jwt_secret",
            must_exist=True,
        ),
        Validator(
            "jwt_algorithm",
            default="HS256",
        ),
        Validator(
            "jwt_expire_minutes",
            # 2 days. People can always log in again
            default=2880,
        ),
        Validator(
            "active_event_series",
            # default="",
            must_exist=True,
        ),
        Validator(
            "database_url",
            must_exist=True,
        ),
        Validator(
            "production_url",
            default="http://localhost:5173",
        ),
        # Cloudflare Turnstile — empty string disables verification (for local dev)
        Validator(
            "turnstile_secret_key",
            default="",
        ),
        # Redis — empty string disables caching (app works normally without it)
        Validator(
            "redis_url",
            default="",
        ),
        # Read-only database endpoint for production replicas.
        # Default "" means the consuming code (db/postgres/base.py) falls back to database_url.
        Validator(
            "database_url_ro",
            default="",
        ),
        Validator(
            "cors_origins",
            default="",
        ),
        Validator(
            "allowed_hosts",
            default="",
        ),
        Validator(
            "trusted_proxy_hosts",
            default="",
        ),
        Validator(
            "sentry_dsn",
            default="",
        ),
        Validator(
            "sentry_traces_sample_rate",
            default=0.1,
        ),
        # OAuth SSO — empty client_id disables the SSO login option entirely
        Validator(
            "sso_client_id",
            default="",
        ),
        Validator(
            "sso_client_secret",
            default="",
        ),
        Validator(
            "oauth_authorize_url",
            default="",
        ),
        Validator(
            "oauth_token_url",
            default="",
        ),
        Validator(
            "oauth_me_url",
            default="",
        ),
    ],
)

try:
    settings.validators.validate()
except Exception as e:
    sys.stderr.write("\n⚠️  Configuration validation failed. Check that:\n  - Doppler is configured correctly (run 'doppler setup')\n  - No stale DOPPLER_TOKEN exists in .env\n  - Required secrets are set in Doppler\n\n")
    raise RuntimeError(str(e)) from None


def comma_separated_setting(name: str, fallback: str = "") -> list[str]:
    """Return a normalized list from a comma-separated or Dynaconf list setting."""
    value = settings.get(name, "") or fallback
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def validate_runtime_security() -> None:
    """Fail closed when production-only security controls are missing or unsafe."""
    if str(settings.current_env).upper() != "PRODUCTION":
        return

    problems: list[str] = []
    if settings.get("enable_test_endpoints", False):
        problems.append("test endpoints must be disabled")
    if not settings.get("turnstile_secret_key", ""):
        problems.append("PODIUM_TURNSTILE_SECRET_KEY is required")

    cors_origins = comma_separated_setting("cors_origins")
    if not cors_origins or "*" in cors_origins:
        problems.append("PODIUM_CORS_ORIGINS must contain explicit origins")

    allowed_hosts = comma_separated_setting("allowed_hosts")
    if not allowed_hosts or "*" in allowed_hosts:
        problems.append("PODIUM_ALLOWED_HOSTS must contain explicit hosts")

    trusted_proxies = comma_separated_setting("trusted_proxy_hosts")
    if not trusted_proxies or "*" in trusted_proxies:
        problems.append("PODIUM_TRUSTED_PROXY_HOSTS must contain explicit proxy IPs")

    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
