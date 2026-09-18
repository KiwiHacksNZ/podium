"""Tests for the multi-host repository validator.

The behaviour these pin down is that a submission on a host we can't check is
*accepted*, not warned about. Teams use GitLab, Codeberg, self-hosted Gitea and
Replit; an earlier GitHub-only version flagged every one of them as invalid.
"""

import httpx
import pytest

from podium import cache
from podium.validators import repo


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeClient:
    """Records every URL fetched so tests can assert calls were/weren't made."""

    calls: list[str] = []
    status_by_url: dict[str, int] = {}
    default_status = 200

    def __init__(self, **kwargs) -> None:
        self.headers = kwargs.get("headers", {})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def get(self, url: str) -> FakeResponse:
        type(self).calls.append(url)
        type(self).last_headers = self.headers
        return FakeResponse(type(self).status_by_url.get(url, type(self).default_status))


@pytest.fixture
def fake_http(monkeypatch):
    FakeClient.calls = []
    FakeClient.status_by_url = {}
    FakeClient.default_status = 200
    FakeClient.last_headers = {}
    monkeypatch.setattr(repo.httpx, "AsyncClient", FakeClient)
    # Keep each test isolated from the shared repo-exists cache.
    monkeypatch.setattr(cache, "_redis", None)
    return FakeClient


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/a/b", "a/b"),
        ("github.com/a/b", "a/b"),
        ("https://www.github.com/a/b", "a/b"),
        ("https://github.com/a/b.git", "a/b"),
        ("https://github.com/a/b/tree/main/src", "a/b/tree/main/src"),
        ("https://gitlab.com/g/sub/p/-/tree/main", "g/sub/p"),
        ("https://gitlab.com/g/p/", "g/p"),
    ],
)
def test_repo_path_normalisation(url, expected):
    assert repo._repo_path(repo._parse_url(url)) == expected


@pytest.mark.parametrize(
    "url,api_url",
    [
        ("https://github.com/a/b", "https://api.github.com/repos/a/b"),
        # Only the first two segments matter, so browse URLs resolve correctly.
        ("https://github.com/a/b/tree/main", "https://api.github.com/repos/a/b"),
        ("https://codeberg.org/a/b", "https://codeberg.org/api/v1/repos/a/b"),
        ("https://bitbucket.org/a/b", "https://api.bitbucket.org/2.0/repositories/a/b"),
        # GitLab namespaces nest, so the whole path is the identifier.
        ("https://gitlab.com/a/b", "https://gitlab.com/api/v4/projects/a%2Fb"),
        (
            "https://gitlab.com/g/sub/p",
            "https://gitlab.com/api/v4/projects/g%2Fsub%2Fp",
        ),
    ],
)
@pytest.mark.asyncio
async def test_each_host_is_checked_at_its_own_api(fake_http, url, api_url):
    result = await repo.validate(url)
    assert result.valid
    assert fake_http.calls == [api_url]


@pytest.mark.parametrize(
    "url",
    [
        "https://replit.com/@someone/my-game",
        "https://scratch.mit.edu/projects/123456",
        "https://git.mycompany.nz/team/thing",
        "https://example.com/some/thing",
    ],
)
@pytest.mark.asyncio
async def test_unrecognised_hosts_are_accepted_without_a_lookup(fake_http, url):
    """The regression this guards: a GitHub-only validator warned on all of these."""
    result = await repo.validate(url)
    assert result.valid
    assert result.message == ""
    assert fake_http.calls == []


@pytest.mark.asyncio
async def test_missing_repo_warns_and_names_the_host(fake_http):
    fake_http.default_status = 404
    result = await repo.validate("https://codeberg.org/a/b")
    assert not result.valid
    assert "Codeberg" in result.message


@pytest.mark.asyncio
async def test_throttled_lookup_is_a_soft_warning(fake_http):
    """403 means we were blocked, not that the repo is missing — the message
    must not tell the user their repo doesn't exist."""
    fake_http.default_status = 403
    result = await repo.validate("https://github.com/a/b")
    assert not result.valid
    assert "Could not reach" in result.message
    assert "doesn't exist" not in result.message


@pytest.mark.asyncio
async def test_unreachable_host_is_a_soft_warning(fake_http, monkeypatch):
    async def boom(self, url):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(FakeClient, "get", boom)
    result = await repo.validate("https://github.com/a/b")
    assert not result.valid
    assert "Could not reach" in result.message


@pytest.mark.asyncio
async def test_github_token_is_sent_when_configured(fake_http, monkeypatch):
    monkeypatch.setattr(
        repo.settings, "get", lambda name, default="": "tok" if name == "github_token" else default
    )
    await repo.validate("https://github.com/a/b")
    assert fake_http.last_headers["Authorization"] == "Bearer tok"


@pytest.mark.asyncio
async def test_non_github_hosts_get_no_github_token(fake_http, monkeypatch):
    monkeypatch.setattr(
        repo.settings, "get", lambda name, default="": "tok" if name == "github_token" else default
    )
    await repo.validate("https://gitlab.com/a/b")
    assert "Authorization" not in fake_http.last_headers


@pytest.mark.parametrize(
    "url,message_fragment",
    [
        ("https://github.com/torvalds", "doesn't point at a repository"),
        ("", "Enter a link"),
        ("   ", "Enter a link"),
    ],
)
@pytest.mark.asyncio
async def test_unusable_urls_are_rejected_without_a_lookup(fake_http, url, message_fragment):
    result = await repo.validate(url)
    assert not result.valid
    assert message_fragment in result.message
    assert fake_http.calls == []


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://github.com/a/b", True),
        ("https://gitlab.com/a/b", True),
        ("https://codeberg.org/a/b", True),
        ("https://bitbucket.org/a/b", True),
        ("https://git.mycompany.nz/a/b", True),
        ("https://example.com/a/b", False),
        ("https://github.com/a", False),
    ],
)
def test_git_shape_check_covers_known_hosts(url, ok):
    """The `git` strategy makes no network call, so it must recognise Codeberg
    and Bitbucket by name — neither has "git" in its domain."""
    assert repo.is_git_url(url) is ok


@pytest.mark.asyncio
async def test_repeated_edits_to_one_repo_cost_a_single_lookup(fake_http, monkeypatch):
    """Caching is what keeps a 100-project event inside GitHub's hourly cap."""

    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value, ex=None):
            self.store[key] = value

    monkeypatch.setattr(cache, "_redis", FakeRedis())

    first = await repo.validate("https://github.com/a/b")
    second = await repo.validate("https://github.com/a/b/tree/main")

    assert first.valid and second.valid
    assert fake_http.calls == ["https://api.github.com/repos/a/b"]


@pytest.mark.asyncio
async def test_transient_failures_are_not_cached(fake_http, monkeypatch):
    """A cached outage would outlive the outage itself."""

    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value, ex=None):
            self.store[key] = value

    redis = FakeRedis()
    monkeypatch.setattr(cache, "_redis", redis)

    fake_http.default_status = 403
    await repo.validate("https://github.com/a/b")
    assert redis.store == {}
