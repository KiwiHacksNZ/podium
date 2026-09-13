"""
Cloudflare Turnstile CAPTCHA verification.

Used as a FastAPI dependency on unauthenticated endpoints (login, signup).
Skipped when turnstile_secret_key is empty (local development and tests).
"""

import logging

from fastapi import HTTPException, Request
import httpx

from podium.config import comma_separated_setting, settings

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
EXPECTED_ACTION = "authenticate"
logger = logging.getLogger(__name__)


async def require_turnstile(request: Request) -> None:
    """FastAPI dependency that verifies a Turnstile token from the X-Turnstile-Token header.
    Skips verification if no secret key is configured (local development)."""
    secret = settings.get("turnstile_secret_key", "")
    if not secret:
        return  # Dev mode — no verification

    expected_hostnames = {
        hostname.casefold()
        for hostname in comma_separated_setting("turnstile_hostnames")
    }
    if not expected_hostnames:
        raise HTTPException(status_code=403, detail="Security check failed — please refresh the page and try again")

    token = request.headers.get("X-Turnstile-Token", "")
    if not token:
        raise HTTPException(status_code=403, detail="Security check required — please complete the CAPTCHA and try again")
    if len(token) > 2048:
        raise HTTPException(status_code=403, detail="Security check failed — please refresh the page and try again")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            data = {"secret": secret, "response": token}
            if request.client:
                data["remoteip"] = request.client.host
            response = await client.post(SITEVERIFY_URL, data=data)
            response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Security check failed — please refresh the page and try again") from exc

    if (
        not result.get("success")
        or result.get("action") != EXPECTED_ACTION
        or str(result.get("hostname", "")).casefold() not in expected_hostnames
    ):
        logger.warning(
            "Turnstile validation rejected: error_codes=%s action=%r hostname=%r",
            result.get("error-codes", []),
            result.get("action"),
            result.get("hostname"),
        )
        raise HTTPException(status_code=403, detail="Security check failed — please refresh the page and try again")
