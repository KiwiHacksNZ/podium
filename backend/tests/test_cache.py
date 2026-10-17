"""Tests for the Redis cache helpers and the payloads that go through them.

The leaderboard cache silently did nothing for its entire life: the endpoint
cached a plain model_dump(), json.dumps refused the UUIDs inside it, and
cache_set caught the TypeError and logged a warning nobody read. Every
leaderboard request paid the full query-and-serialise cost.
"""

import json
from uuid import uuid4

import pytest

from podium import cache
from podium.db.postgres import Project
from podium.routers.events import serialize_projects


class FakeRedis:
    """Stores what a real Redis would: JSON strings."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def get(self, key: str):
        return self.store.get(key)


def _leaderboard_payload() -> list[dict]:
    """Built by the same function the leaderboard endpoint uses, so a regression
    at that call site fails these tests rather than sliding past them."""
    projects = [
        Project(name=f"P{i}", join_code=f"c{i}", event_id=uuid4(), owner_id=uuid4())
        for i in range(3)
    ]
    return serialize_projects(projects)


def test_leaderboard_payload_is_json_serializable() -> None:
    """A plain model_dump() leaves UUIDs as objects and json.dumps rejects them."""
    json.dumps(_leaderboard_payload())


@pytest.mark.asyncio
async def test_leaderboard_payload_actually_reaches_redis(monkeypatch) -> None:
    """cache_set swallows serialisation errors, so the only honest check is
    whether the value can be read back out again."""
    fake = FakeRedis()
    monkeypatch.setattr(cache, "_redis", fake)
    payload = _leaderboard_payload()

    await cache.cache_set("leaderboard:abc", payload, ttl=30)

    assert fake.store, "cache_set wrote nothing — the payload was not serialisable"
    assert await cache.cache_get("leaderboard:abc") == payload


@pytest.mark.asyncio
async def test_cache_set_survives_an_unserialisable_value(monkeypatch) -> None:
    """A cache is best-effort: a bad value must not 500 the request it came from."""
    fake = FakeRedis()
    monkeypatch.setattr(cache, "_redis", fake)

    await cache.cache_set("k", {"bad": object()}, ttl=30)

    assert fake.store == {}


@pytest.mark.asyncio
async def test_cache_is_a_noop_without_redis(monkeypatch) -> None:
    monkeypatch.setattr(cache, "_redis", None)
    await cache.cache_set("k", {"a": 1}, ttl=30)
    assert await cache.cache_get("k") is None
