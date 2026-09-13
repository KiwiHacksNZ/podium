from io import BytesIO
import ssl

import httpx
import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.requests import Request
from starlette.datastructures import Headers

from podium.routers import projects
from podium.routers.auth import safe_redirect_path
from podium.db.postgres import base as postgres_base
from podium.db.postgres import Vote, VoteAuditLog
from podium.validators import turnstile


def upload(filename: str, content_type: str, body: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(body),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def turnstile_request(token: str | None = None) -> Request:
    headers = [] if token is None else [(b"x-turnstile-token", token.encode())]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": headers,
            "client": ("203.0.113.10", 12345),
        }
    )


class FakeTurnstileClient:
    def __init__(self, result: dict, status_code: int = 200, **_kwargs) -> None:
        self.response = httpx.Response(
            status_code,
            json=result,
            request=httpx.Request("POST", turnstile.SITEVERIFY_URL),
        )
        self.post_data: dict | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def post(self, _url: str, data: dict) -> httpx.Response:
        self.post_data = data
        return self.response


def enable_turnstile(monkeypatch) -> None:
    values = {
        "turnstile_secret_key": "secret",
        "turnstile_hostnames": "vote.kiwihacks.com",
    }
    monkeypatch.setattr(
        turnstile.settings,
        "get",
        lambda name, default="": values.get(name, default),
    )


@pytest.mark.asyncio
async def test_turnstile_skips_verification_without_secret(monkeypatch) -> None:
    monkeypatch.setattr(turnstile.settings, "get", lambda *_args: "")

    await turnstile.require_turnstile(turnstile_request())


@pytest.mark.asyncio
async def test_turnstile_requires_token_when_configured(monkeypatch) -> None:
    enable_turnstile(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        await turnstile.require_turnstile(turnstile_request())

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_turnstile_validates_token_and_action(monkeypatch) -> None:
    enable_turnstile(monkeypatch)
    client = FakeTurnstileClient(
        {
            "success": True,
            "action": "authenticate",
            "hostname": "vote.kiwihacks.com",
        }
    )
    monkeypatch.setattr(turnstile.httpx, "AsyncClient", lambda **_kwargs: client)

    await turnstile.require_turnstile(turnstile_request("valid-token"))

    assert client.post_data == {
        "secret": "secret",
        "response": "valid-token",
        "remoteip": "203.0.113.10",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        {"success": False, "error-codes": ["timeout-or-duplicate"]},
        {
            "success": True,
            "action": "different-action",
            "hostname": "vote.kiwihacks.com",
        },
        {
            "success": True,
            "action": "authenticate",
            "hostname": "attacker.example",
        },
    ],
)
async def test_turnstile_rejects_failed_or_wrong_metadata(monkeypatch, result) -> None:
    enable_turnstile(monkeypatch)
    client = FakeTurnstileClient(result)
    monkeypatch.setattr(turnstile.httpx, "AsyncClient", lambda **_kwargs: client)

    with pytest.raises(HTTPException) as exc:
        await turnstile.require_turnstile(turnstile_request("invalid-token"))

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_turnstile_fails_closed_when_siteverify_is_unavailable(monkeypatch) -> None:
    enable_turnstile(monkeypatch)
    client = FakeTurnstileClient({}, status_code=503)
    monkeypatch.setattr(turnstile.httpx, "AsyncClient", lambda **_kwargs: client)

    with pytest.raises(HTTPException) as exc:
        await turnstile.require_turnstile(turnstile_request("valid-token"))

    assert exc.value.status_code == 403


def test_redirect_accepts_only_same_origin_paths() -> None:
    assert safe_redirect_path("/events/123?tab=votes") == "/events/123?tab=votes"
    assert safe_redirect_path("https://evil.example/steal") == "/"
    assert safe_redirect_path("//evil.example/steal") == "/"


def test_remote_database_tls_verifies_certificate(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        postgres_base,
        "create_async_engine",
        lambda url, **kwargs: captured.update(url=url, **kwargs),
    )

    postgres_base._build_async_engine("postgresql+asyncpg://user:pass@db.example/test")

    context = captured["connect_args"]["ssl"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_local_database_can_explicitly_disable_tls(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        postgres_base,
        "create_async_engine",
        lambda url, **kwargs: captured.update(url=url, **kwargs),
    )

    postgres_base._build_async_engine(
        "postgresql+asyncpg://user:pass@localhost/test?sslmode=disable"
    )

    assert captured["connect_args"] == {}


def test_vote_timestamps_are_timezone_aware_in_model_metadata() -> None:
    assert Vote.__table__.c.created_at.type.timezone is True
    assert VoteAuditLog.__table__.c.created_at.type.timezone is True


@pytest.mark.asyncio
async def test_image_upload_rejects_svg(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECT_IMAGE_DIR", tmp_path)
    file = upload("attack.svg", "image/svg+xml", b"<svg><script>alert(1)</script></svg>")

    with pytest.raises(HTTPException) as exc:
        await projects._save_project_image(file)

    assert exc.value.status_code == 422
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_image_upload_rejects_fake_png(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECT_IMAGE_DIR", tmp_path)
    file = upload("fake.png", "image/png", b"not actually a png")

    with pytest.raises(HTTPException) as exc:
        await projects._save_project_image(file)

    assert exc.value.status_code == 422
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_image_upload_verifies_and_saves_png(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECT_IMAGE_DIR", tmp_path)
    contents = BytesIO()
    Image.new("RGB", (2, 2), color="red").save(contents, format="PNG")
    file = upload("valid.png", "image/png", contents.getvalue())

    filename = await projects._save_project_image(file)

    assert filename.endswith(".png")
    assert (tmp_path / filename).is_file()
