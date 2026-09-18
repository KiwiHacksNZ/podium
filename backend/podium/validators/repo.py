"""
Repository URL validator.

Instant check: regex on the URL shape (mirrored frontend-side in validation.ts).
Background check: asks the host whether the repo actually exists — the one
failure worth catching before judging starts, since a private or deleted repo
is something a judge can't open and the submitter can't fix once they've left.

Hosts with a public, unauthenticated repo API get that existence check. Any
other URL is accepted without comment: teams use self-hosted Gitea, Replit,
Colab and plenty else, and a warning badge on a working submission costs more
than the check is worth.

Rate limits, all per server IP when unauthenticated: GitHub 60/hr (5000 with
PODIUM_GITHUB_TOKEN — set it for events over ~30 projects), Bitbucket 60/hr,
GitLab ~500/min, Codeberg generous. Results are cached per repo so repeated
edits to one submission cost a single call, and any non-404 error is a soft
warning rather than a hard fail.
"""

from dataclasses import asdict, dataclass
from typing import Callable
from urllib.parse import quote, urlparse

import httpx

from podium.cache import cache_get, cache_set
from podium.config import settings
from podium.validators.base import ValidationResult

# Long enough that a submission being edited repeatedly costs one API call, short
# enough that a repo made public mid-event revalidates without organiser action.
REPO_CACHE_TTL = 600


@dataclass(frozen=True)
class _Host:
    label: str
    # Maps the repo's URL path to an API endpoint, or None if the path is too
    # short to name a repository.
    api_url: Callable[[str], str | None]


def _two_segment_api(template: str) -> Callable[[str], str | None]:
    """Build an api_url for hosts whose repos are always exactly owner/name."""

    def api_url(path: str) -> str | None:
        parts = path.split("/")
        if len(parts) < 2 or not all(parts[:2]):
            return None
        return template.format(owner=parts[0], repo=parts[1])

    return api_url


def _gitlab_api_url(path: str) -> str | None:
    # GitLab namespaces nest arbitrarily deep (group/subgroup/project), so the
    # whole path is the project identifier rather than the first two segments.
    if "/" not in path.strip("/"):
        return None
    return f"https://gitlab.com/api/v4/projects/{quote(path, safe='')}"


CHECKED_HOSTS: dict[str, _Host] = {
    "github.com": _Host(
        "GitHub", _two_segment_api("https://api.github.com/repos/{owner}/{repo}")
    ),
    "gitlab.com": _Host("GitLab", _gitlab_api_url),
    "codeberg.org": _Host(
        "Codeberg", _two_segment_api("https://codeberg.org/api/v1/repos/{owner}/{repo}")
    ),
    "bitbucket.org": _Host(
        "Bitbucket",
        _two_segment_api("https://api.bitbucket.org/2.0/repositories/{owner}/{repo}"),
    ),
}

def _parse_url(url: str):
    value = (url or "").strip()
    if not value:
        return urlparse("")
    if "://" not in value:
        value = f"https://{value}"
    return urlparse(value)


def _host_of(parsed) -> str:
    return (parsed.hostname or "").lower().removeprefix("www.")


def _repo_path(parsed) -> str:
    """Reduce a browsable repo URL to its bare owner/name path.

    GitLab separates the repo path from page routes with `/-/`; GitHub and
    Bitbucket append them directly, but those hosts only ever use the first two
    segments so the extra ones fall away on their own.
    """
    path = parsed.path.split("/-/", 1)[0].strip("/")
    return path.removesuffix(".git")


def is_git_url(url: str) -> bool:
    """Return True for a URL that plausibly names a repository."""
    parsed = _parse_url(url)
    host = _host_of(parsed)
    if not host:
        return False
    segments = [part for part in _repo_path(parsed).split("/") if part]
    return (host in CHECKED_HOSTS or "git" in host) and len(segments) >= 2


async def validate_git_url(repo_url: str) -> ValidationResult:
    """Shape-only check: does this look like a repo on a known or git-named host?

    Used by the `git` strategy, which never makes a network call.
    """
    if is_git_url(repo_url):
        return ValidationResult(valid=True, message="")
    return ValidationResult(
        valid=False,
        message="Repository URL must point at a repo (e.g. github.com/owner/repo, gitlab.com/owner/repo, or another git host).",
    )


async def _repo_exists(host: _Host, api_url: str, timeout: float) -> ValidationResult | None:
    """Return a verdict, or None when the host could not give a usable answer."""
    headers = {"Accept": "application/json"}
    if host.label == "GitHub":
        headers |= {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token := settings.get("github_token", ""):
            headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        response = await client.get(api_url)

    if response.status_code == 200:
        return ValidationResult(valid=True, message="")
    if response.status_code in (401, 403):
        # Private repos answer 404 on these APIs, so a 401/403 means we were
        # throttled or blocked — that says nothing about the repo.
        return None
    if response.status_code == 404:
        return ValidationResult(
            valid=False,
            message=f"{host.label} says this repository doesn't exist or isn't public. Check the link, and make the repo public so judges can open it.",
        )
    return None


async def validate(repo_url: str, timeout: float = 10.0) -> ValidationResult:
    """Check that a repo URL resolves to something a judge can actually open.

    Recognised hosts get an existence check; anything else that parses as a URL
    with an owner/name path is accepted as-is.
    """
    parsed = _parse_url(repo_url)
    host_name = _host_of(parsed)
    path = _repo_path(parsed)

    if not host_name or not path:
        return ValidationResult(
            valid=False,
            message="Enter a link to your project's code (e.g. github.com/owner/repo).",
        )

    host = CHECKED_HOSTS.get(host_name)
    if host is None:
        # Self-hosted Gitea, Replit, a personal domain — nothing to check
        # against, and warning here would flag a perfectly good submission.
        return ValidationResult(valid=True, message="")

    api_url = host.api_url(path)
    if api_url is None:
        return ValidationResult(
            valid=False,
            message=f"That {host.label} link doesn't point at a repository. Use the repo's main page, e.g. {host_name}/owner/repo.",
        )

    # Keyed on the API URL, not the submitted one: it is the repo's canonical
    # identity, so a browse link and a bare repo link share one cached answer.
    cache_key = f"repo-exists:{api_url}"
    if (cached := await cache_get(cache_key)) is not None:
        return ValidationResult(**cached)

    try:
        result = await _repo_exists(host, api_url, timeout)
    except Exception:
        result = None

    if result is None:
        # Soft warning, and deliberately not cached: it describes the lookup,
        # not the repo, so caching would outlive the outage that caused it.
        return ValidationResult(
            valid=False,
            message=f"Could not reach {host.label} to check this repository. It may still be fine.",
        )

    await cache_set(cache_key, asdict(result), ttl=REPO_CACHE_TTL)
    return result
