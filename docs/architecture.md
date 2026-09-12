# Architecture

Podium is a judging platform for Kiwihacks hackathons. Attendees select an official event and submit projects; judges score every project, and attendees rank the finalists.

## Stack

- **Frontend:** SvelteKit (Svelte 5), Tailwind, DaisyUI
- **Backend:** FastAPI, SQLModel (async PostgreSQL)
- **Auth:** Magic link email via Loops API
- **Cache:** Redis (optional — leaderboards cached 30s; app works without it)
- **CAPTCHA:** Cloudflare Turnstile on unauthenticated endpoints
- **Monitoring:** Sentry

## Data Model

Core entities:

- **User** — email, display_name, first_name, is_superadmin, is_admin
- **Event** — name, slug, phase, judging_open, voting_open, judge_code, feature_flags_csv, repo_validation, demo_validation, require_address
- **Project** — name, repo, image_url, demo, owner_id, event_id, points, is_finalist, validation_status, validation_message
- **Vote** — voter_id, project_id, event_id, rank (unique on voter+project, and on voter+event+rank)
- **JudgeScore** — judge_id, project_id, event_id, originality/technicality/theme/usability (unique on judge+project)

M2M relationships via junction tables:
- `event_attendees` — User ↔ Event
- `event_judges` — User ↔ Event (judging access, per event)
- `project_collaborators` — User ↔ Project

## Event Lifecycle

Events move through phases in order: `draft` → `submission` → `judging` → `voting` → `closed`.

| Phase | What's allowed |
|---|---|
| `draft` | Not yet visible to users |
| `submission` | Users can join and submit projects |
| `judging` | Submissions closed; judges are scoring |
| `voting` | Finalists picked; attendees are ranking |
| `closed` | Leaderboard visible |

The phase controls visibility and the leaderboard, and tells everyone where the event is up to. It does **not** gate the two rounds — those are separate booleans on the event, `judging_open` and `voting_open`, flipped independently from the admin panel's Rounds switches (`PATCH /events/admin/{id}`). Judges can still be scoring while attendees vote, or either round can run on its own.

The phase is changed by the event owner via the admin panel UI or `PATCH /events/admin/{id}`.

## Event Series

Events are grouped into a **series** — a flagship event plus its satellites (e.g., "Scrapyard 2025"). Only one series is active at a time, controlled by `ACTIVE_EVENT_SERIES` in backend config. Events with matching `feature_flags_csv` appear in the event selector.

Key rules:
- **One event per user per series** — backend enforces; selecting a new event auto-switches
- **Events are admin-created** — users select from a list, never create events
- **All official events are equal** — no UI distinction between flagship and satellites
- **Past series are read-only** — users can view but not edit old projects

## Validation System

Validation has two independent layers:

**1. Frontend (instant, non-blocking warnings)** — `frontend/src/lib/validation.ts`
Shows a warning as the user types. Only implemented for `github` and `itch`; setting either field to `none` or `custom` shows no frontend warning at all. There is no frontend equivalent for custom validators.

**2. Backend (background, async)** — `backend/podium/validators/`
Runs after every project create/update; never blocks submission. Results appear as badges (`pending → valid | warning`).

Validation strategy is configured per-event via `repo_validation` and `demo_validation`:

| Setting | Frontend warning | Backend check |
|---|---|---|
| `github` | Regex check for valid GitHub URL | GitHub public API — repo must exist |
| `git` | URL host must contain `git`, path must look like a repo | Shape check only; accepts GitHub, GitLab, and self-hosted git domains |
| `itch` | Regex check for valid itch.io URL | Scrapes itch.io for `.game_frame` (browser-playable) |
| `custom` | None | Calls the named module from `validators/custom/REGISTRY` |
| `none` | None | Skipped |

**Adding a custom backend validator:**
1. Create `backend/podium/validators/custom/<name>.py` implementing `validate_repo(url)` and/or `validate_demo(url)`, each returning `ValidationResult`.
2. Register it in `validators/custom/__init__.py`: `REGISTRY["<name>"] = <module>`.
3. Set the event's `custom_validator` field to `"<name>"` and set `repo_validation` and/or `demo_validation` to `"custom"`.

Events can also set `require_address: true` to enforce that users have a shipping address on file before submitting — this is a hard block at the API level.

## User Flow

```
Sign in → Select event → (Address check) → Submit project → Validation → Vote
```

1. User signs in via magic link
2. Selects from available official events (`GET /events/official`)
3. If `require_address` is set, must provide shipping address first
4. Creates or joins a project (join codes allow collaborators)
5. Background validation runs; badge appears on project card
6. Can vote on other projects

## Judging and Voting

Results come out of two rounds.

**Judges.** Judging access is scoped to one event, held in the `event_judges` link table — judging one event grants nothing on another. Two ways in: the organizer adds someone by email from the admin panel's Judges card (`POST /events/admin/{id}/add-judge`), or they hand out the event's rotatable 6-digit code (`POST /events/admin/{id}/judge-code`) which the judge redeems at `/judge` (`POST /judging/redeem`). Superadmins bypass the check, as everywhere else. A user's judged events come back on `/users/current` as `judge_event_ids`.

**Round 1 — judges.** While `judging_open` is on, that event's judges score every project 1-10 on four criteria: originality, technicality, theme, and usability (max 40). One score row per judge per project; re-scoring replaces it. Judges can't score a project they own or collaborate on. Standings are the mean judge total, ranked at `GET /judging/{event_id}/results`.

**Locking finalists.** The organizer calls `POST /events/admin/{event_id}/finalists`, which marks the top `FINALIST_COUNT` (5) projects by mean judge score as finalists, ties broken by how many judges scored them. Re-running it recomputes the whole set, but it is refused once the first vote is cast — otherwise votes could be left on projects that are no longer finalists.

**Round 2 — attendees.** While `voting_open` is on, attendees rank the finalists: the ballot is an ordered list, so `projects[0]` is their first choice. A first choice is worth 3 points, a second 2, a third 1 (`RANK_POINTS`). Attendees get `min(3, finalist_count)` picks once finalists exist; before that, ballot size still scales with project count (1 under 4 projects, 2 under 20, else 3). Users can't vote for their own or collaborated projects, and non-finalists are rejected.

A project's `points` is the weighted sum of the ballots it appears on — judge scores decide who reaches the ballot, not the final order.

## Key Directories

Backend (`backend/podium/`):
- `main.py` — FastAPI app, lifespan (Redis init/close)
- `config.py` — Dynaconf settings (all env vars with `PODIUM_` prefix)
- `constants.py` — Shared types: `EventPhase`, `RepoValidation`, `DemoValidation`, `BAD_AUTH`, etc.
- `limiter.py` — slowapi rate limiter (user-email based)
- `db/postgres/` — SQLModel models and database session helpers
- `routers/` — API endpoints (`auth`, `users`, `events`, `projects`, `admin`, `superadmin`)
- `validators/` — Project URL validation: `github.py`, `itch.py`, `custom/` (event-specific); input validation: `email.py`, `turnstile.py`
- `cache/` — Redis helpers (`cache_get`, `cache_set`, `cache_delete`) with graceful no-op fallback

Frontend (`frontend/src/`):
- `hooks.client.ts` — Client init, auth validation
- `lib/client/` — Generated OpenAPI client (run `bun run openapi-ts` to regenerate)
- `lib/forms/` — Reusable form components (Button, Input, Label, Textarea, FileDropZone)
- `lib/logos/` — Event logo components (CampfireFlagship, CampfireSat)
- `lib/user.svelte.ts` — User state
- `lib/validation.ts` — Project validation
- `routes/` — SvelteKit pages

## Admin Tools

- `backend/scripts/manage.py` — TUI: create events, manage attendees, toggle superadmin, delete users/events
- `/superadmin` — Web UI (requires `is_superadmin`): list/create/delete events, edit owner and validation settings, list users
- `PATCH /events/admin/{id}` — API: update any event field (owners and superadmins)
- NocoDB — spreadsheet UI for the database (see nocodb.md)

Superadmin status (`is_superadmin`) is toggled via the TUI Users tab — there is no API for it.
