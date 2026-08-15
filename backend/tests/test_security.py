from io import BytesIO
import ssl

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers

from podium.routers import projects
from podium.routers.auth import safe_redirect_path
from podium.db.postgres import base as postgres_base
from podium.db.postgres import Vote, VoteAuditLog


def upload(filename: str, content_type: str, body: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(body),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


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
