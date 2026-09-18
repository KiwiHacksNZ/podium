from io import BytesIO
import inspect
import random
import ssl

import httpx
import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageDraw
from starlette.requests import Request
from starlette.datastructures import Headers

from podium import cache
from podium.limiter import limiter
from podium.routers import auth, projects
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


# ── project image downscaling ───────────────────────────────────────────────
#
# Thumbnails are served off the VPS by uvicorn, so an unresized 8MB phone photo
# is 8MB down the wire for every person who opens the showcase page.


def _detailed(width: int, height: int) -> Image.Image:
    """An image with enough variation that re-encoding is a fair test."""
    image = Image.new("RGB", (width, height), (24, 26, 32))
    draw = ImageDraw.Draw(image)
    for i in range(0, height, 40):
        draw.rectangle([20, i, width - 20, i + 24], fill=(60 + i % 120, 90, 160))
    return image


@pytest.mark.asyncio
async def test_oversized_upload_is_downscaled(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECT_IMAGE_DIR", tmp_path)
    contents = BytesIO()
    _detailed(3000, 2000).save(contents, format="JPEG", quality=95)
    original_bytes = len(contents.getvalue())
    file = upload("big.jpg", "image/jpeg", contents.getvalue())

    saved = tmp_path / await projects._save_project_image(file)

    with Image.open(saved) as image:
        assert max(image.size) == projects.MAX_PROJECT_IMAGE_DIMENSION
    assert saved.stat().st_size < original_bytes


@pytest.mark.asyncio
async def test_small_upload_is_left_alone(tmp_path, monkeypatch) -> None:
    """Nothing to gain from re-encoding, and re-encoding costs quality."""
    monkeypatch.setattr(projects, "PROJECT_IMAGE_DIR", tmp_path)
    contents = BytesIO()
    _detailed(400, 300).save(contents, format="JPEG", quality=95)
    payload = contents.getvalue()
    file = upload("small.jpg", "image/jpeg", payload)

    saved = tmp_path / await projects._save_project_image(file)

    assert saved.read_bytes() == payload


def test_downscale_keeps_original_when_re_encoding_would_grow_it(tmp_path) -> None:
    """Fewer pixels does not guarantee fewer bytes. Bandwidth is the point, so a
    re-encode that comes out bigger must be discarded."""
    destination = tmp_path / "noise.png"
    rng = random.Random(7)
    image = Image.new("RGB", (2000, 1400))
    pixels = image.load()
    for y in range(0, 1400, 2):
        for x in range(0, 2000, 2):
            colour = (rng.randrange(256), rng.randrange(256), rng.randrange(256))
            for dy in range(2):
                for dx in range(2):
                    pixels[x + dx, y + dy] = colour
    image.save(destination, format="PNG")
    before = destination.read_bytes()

    projects._downscale_project_image(destination, "PNG")

    assert destination.read_bytes() == before


def test_downscale_preserves_gif_animation(tmp_path) -> None:
    """exif_transpose collapses a multi-frame image to its first frame, so the
    still-image path must not run for animations."""
    destination = tmp_path / "anim.gif"
    frames = []
    for i in range(4):
        frame = Image.new("RGB", (2000, 1500), (i * 60, 255 - i * 60, 128))
        ImageDraw.Draw(frame).rectangle(
            [i * 400, i * 300, i * 400 + 500, i * 300 + 400], fill=(255, 255, 0)
        )
        frames.append(frame.convert("P", palette=Image.ADAPTIVE))
    frames[0].save(
        destination, format="GIF", save_all=True, append_images=frames[1:],
        duration=150, loop=0,
    )

    projects._downscale_project_image(destination, "GIF")

    with Image.open(destination) as result:
        assert result.n_frames == 4
        assert max(result.size) == projects.MAX_PROJECT_IMAGE_DIMENSION


def test_downscale_applies_exif_rotation_and_strips_it(tmp_path) -> None:
    """Phones record rotation in EXIF rather than pixels. Re-encoding without
    applying it first would bake in a sideways thumbnail, and keeping the tag
    would publish the photo's GPS coordinates."""
    destination = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6  # rotate 90° clockwise for display
    _detailed(1500, 2400).save(destination, format="JPEG", quality=95, exif=exif)

    projects._downscale_project_image(destination, "JPEG")

    with Image.open(destination) as result:
        # Orientation 6 means the 1500x2400 source displays as landscape.
        assert result.size[0] > result.size[1]
        assert result.getexif().get(274) is None


# ── judge-code guessing throttle ────────────────────────────────────────────


class FakeRedisPipeline:
    def __init__(self, store: dict) -> None:
        self.store = store
        self.queued: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    def incr(self, key: str):
        self.queued.append(("incr", key))
        return self

    def expire(self, key: str, ttl: int, nx: bool = False):
        self.queued.append(("expire", key, ttl, nx))
        return self

    async def execute(self) -> list:
        results = []
        for op in self.queued:
            if op[0] == "incr":
                self.store[op[1]] = str(int(self.store.get(op[1], "0")) + 1)
                results.append(int(self.store[op[1]]))
            else:
                results.append(True)
        self.queued.clear()
        return results


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def pipeline(self) -> FakeRedisPipeline:
        return FakeRedisPipeline(self.store)

    async def get(self, key: str):
        return self.store.get(key)


@pytest.mark.asyncio
async def test_cache_incr_counts_and_is_readable_by_cache_get(monkeypatch):
    """cache_incr stores a bare integer; cache_get must read it back as an int,
    since the redeem throttle compares the two."""
    fake = FakeRedis()
    monkeypatch.setattr(cache, "_redis", fake)

    assert await cache.cache_incr("judge-redeem-fail:1.2.3.4", ttl=60) == 1
    assert await cache.cache_incr("judge-redeem-fail:1.2.3.4", ttl=60) == 2
    assert await cache.cache_get("judge-redeem-fail:1.2.3.4") == 2


@pytest.mark.asyncio
async def test_cache_incr_sets_expiry_only_on_first_write(monkeypatch):
    """EXPIRE must use NX, or a steady drip of failures would keep resetting the
    window and the counter would never age out."""
    fake = FakeRedis()
    seen: list = []
    monkeypatch.setattr(cache, "_redis", fake)

    real_pipeline = fake.pipeline

    def recording_pipeline():
        pipe = real_pipeline()
        original_expire = pipe.expire

        def expire(key, ttl, nx=False):
            seen.append((key, ttl, nx))
            return original_expire(key, ttl, nx)

        pipe.expire = expire
        return pipe

    fake.pipeline = recording_pipeline
    await cache.cache_incr("k", ttl=3600)
    assert seen == [("k", 3600, True)]


@pytest.mark.asyncio
async def test_cache_incr_fails_open_without_redis(monkeypatch):
    """Returning 0 keeps the throttle from locking out every judge if Redis dies."""
    monkeypatch.setattr(cache, "_redis", None)
    assert await cache.cache_incr("k", ttl=60) == 0


def test_unauthenticated_endpoints_have_no_ip_rate_limit():
    """An IP limit on these would key on the venue's shared NAT address and lock
    out everyone after the first few attempts. Login is gated by Turnstile;
    judge-code redemption throttles failed guesses instead (see judging.py)."""
    import podium.main  # noqa: F401  — importing registers every router's limits

    marked = limiter._Limiter__marked_for_limiting
    assert "podium.routers.auth.request_login" not in marked
    assert "podium.routers.judging.redeem_judge_code" not in marked
    # Guard against slowapi changing its key format and making the above vacuous.
    assert "podium.routers.projects.validate_project" in marked


def test_request_login_still_requires_turnstile():
    default = inspect.signature(auth.request_login).parameters["_turnstile"].default
    assert default.dependency is turnstile.require_turnstile
