/**
 * API Endpoint Coverage
 *
 * Every backend HTTP endpoint is exercised in this file at least once — success
 * path when practical, plus common error paths where they inform route correctness
 * (e.g. 404 on unknown IDs, 403 on wrong actor). These tests run at the API layer
 * so they're fast and stable; UI-level verification lives in the other specs.
 *
 * When a new endpoint is added to backend/podium/routers/*.py, add a case here.
 */

import { request as apiRequest } from '@playwright/test';
import { test, expect } from './fixtures/auth';
import { unique } from './utils/data';
import {
	adminGetAttendees,
	adminGetEvent,
	adminGetLeaderboard,
	adminGetReferrals,
	adminGetVotes,
	adminLockFinalists,
	adminAddJudge,
	adminGetJudgeCards,
	adminGetJudges,
	adminMintJudgeCards,
	adminPatchEvent,
	adminRemoveJudge,
	adminRotateJudgeCode,
	adminRemoveAttendee,
	attendEvent,
	createProject,
	createTestEvent,
	deleteProject,
	getAttendingEvents,
	getCurrentUser,
	getEvent,
	getEventIdBySlug,
	getEventProjects,
	getJudgingResults,
	getMyProjects,
	getOfficialEvents,
	getProject,
	getUserPublic,
	joinProject,
	judgeGetProjects,
	judgeScoreProject,
	redeemJudgeCode,
	requestLogin,
	setRoundOpen,
	updateCurrentUser,
	updateProject,
	userExists,
	validateProject,
	voteForProjects
} from './helpers/api';
import {
	createJudgeAndGetToken,
	createUserAndGetToken,
	secondaryUserEmail
} from './helpers/users';

const BAD_UUID = '00000000-0000-0000-0000-000000000000';

test.describe('API coverage — AUTH router', () => {
	test('POST /request-login succeeds for an existing user', async ({
		authedApi,
		userEmail
	}) => {
		const resp = await requestLogin(authedApi, userEmail);
		// No LOOPS key in dev => endpoint returns 200 with no body
		expect(resp.ok()).toBe(true);
	});

	test('POST /request-login gives a generic response for an unknown user', async ({ authedApi }, testInfo) => {
		// @example.com is the reserved documentation TLD — EmailStr accepts it.
		const unknown = `nobody+${Date.now()}-w${testInfo.workerIndex}@example.com`;
		const resp = await requestLogin(authedApi, unknown);
		expect(resp.status()).toBe(200);
	});

	// GET /verify is exercised in the `token` fixture for every worker, so it is
	// implicitly covered before any test runs.
});

test.describe('API coverage — USERS router', () => {
	test('GET /users/exists reports existing + missing users', async ({
		authedApi,
		userEmail
	}, testInfo) => {
		const present = await userExists(authedApi, userEmail);
		expect(present.exists).toBe(true);

		// /users/exists validates with EmailStr, which rejects .local as a reserved
		// TLD. Use @example.com (reserved documentation TLD) instead.
		const missingEmail = `nobody+${Date.now()}-w${testInfo.workerIndex}@example.com`;
		const missing = await userExists(authedApi, missingEmail);
		expect(missing.exists).toBe(false);
	});

	test('GET /users/current returns the authenticated user', async ({
		authedApi,
		userEmail
	}) => {
		const me = await getCurrentUser(authedApi);
		expect(me.email).toBe(userEmail);
		expect(typeof me.id).toBe('string');
	});

	test('PUT /users/current updates mutable profile fields', async ({
		authedApi
	}, testInfo) => {
		const newDisplayName = unique('Renamed', testInfo);
		const updated = await updateCurrentUser(authedApi, { display_name: newDisplayName });
		expect(updated.display_name).toBe(newDisplayName);

		const again = await getCurrentUser(authedApi);
		expect(again.display_name).toBe(newDisplayName);
	});

	test('GET /users/{user_id} returns a public profile', async ({ api, authedApi }) => {
		const me = await getCurrentUser(authedApi);
		const pub = await getUserPublic(api, me.id);
		expect(pub.id).toBe(me.id);
		expect(pub).toHaveProperty('display_name');
		// Public schema must not leak PII
		expect(pub).not.toHaveProperty('email');
		expect(pub).not.toHaveProperty('phone');
	});

	test('POST /users/ rejects duplicate signups', async ({ api, userEmail }) => {
		const resp = await api.post('/users/', {
			headers: { 'Content-Type': 'application/json' },
			data: {
				email: userEmail,
				first_name: 'Dup',
				last_name: 'User'
			}
		});
		expect(resp.status()).toBe(400);
	});
});

test.describe('API coverage — EVENTS router', () => {
	test('GET /events/official lists events in the active series', async ({
		authedApi
	}, testInfo) => {
		const name = unique('Official List', testInfo);
		const event = await createTestEvent(authedApi, { name });

		const events = await getOfficialEvents(authedApi);
		expect(Array.isArray(events)).toBe(true);
		expect(events.some((e: { id: string }) => e.id === event.id)).toBe(true);
	});

	test('GET /events/{event_id} returns the event and 404s on unknown IDs', async ({
		authedApi
	}, testInfo) => {
		const name = unique('GetById', testInfo);
		const event = await createTestEvent(authedApi, { name });

		const fetched = await getEvent(authedApi, event.id);
		expect(fetched.id).toBe(event.id);
		expect(fetched.name).toBe(name);

		const missing = await authedApi.get(`/events/${BAD_UUID}`);
		expect(missing.status()).toBe(404);
	});

	test('GET /events/ returns events the user attends', async ({ authedApi }, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('Attending', testInfo) });
		await attendEvent(authedApi, event.id);

		const mine = await getAttendingEvents(authedApi);
		expect(mine.attending_events.some((e: { id: string }) => e.id === event.id)).toBe(true);
	});

	test('GET /events/id/{slug} maps slug to ID', async ({ authedApi }, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('SlugLookup', testInfo) });
		const idResp = await authedApi.get(`/events/id/${event.slug}`);
		expect(idResp.ok()).toBe(true);
		const body = await idResp.text();
		// endpoint returns a bare JSON-encoded string
		expect(body.replace(/"/g, '')).toBe(event.id);

		// Also via helper
		const viaHelper = await getEventIdBySlug(authedApi, event.slug);
		expect(viaHelper).toBe(event.id);
	});

	test('GET /events/{event_id}/projects returns project list (shuffled)', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('Projects', testInfo) });
		await attendEvent(authedApi, event.id);
		const created = await createProject(authedApi, {
			name: unique('Covered Project', testInfo),
			description: 'api-coverage test',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});

		const listResp = await getEventProjects(authedApi, event.id, false);
		expect(listResp.ok()).toBe(true);
		const projects = await listResp.json();
		expect(projects.some((p: { id: string }) => p.id === created.id)).toBe(true);

		// leaderboard=true with a VOTING-phase event → 403
		const lbResp = await getEventProjects(authedApi, event.id, true);
		expect(lbResp.status()).toBe(403);
	});

	test('POST /events/{event_id}/attend is idempotent', async ({ authedApi }, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('Attend', testInfo) });
		const first = await attendEvent(authedApi, event.id);
		expect(first.event_id).toBe(event.id);
		const second = await attendEvent(authedApi, event.id);
		expect(second.event_id).toBe(event.id);
	});

	test('POST /events/vote rejects self-votes and records valid votes', async ({
		authedApi
	}, testInfo) => {
		// Organizer (authedApi user) creates event + attends + creates a project
		const event = await createTestEvent(authedApi, { name: unique('Vote', testInfo) });
		await attendEvent(authedApi, event.id);
		const ownProject = await createProject(authedApi, {
			name: unique('Own Project', testInfo),
			description: 'cannot vote for this',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});

		// Attempt to self-vote → 403
		const selfVote = await voteForProjects(authedApi, event.id, [ownProject.id]);
		expect(selfVote.status()).toBe(403);

		// Attendee (separate user) votes for the organizer's project
		const tag = `vote-${Date.now()}-w${testInfo.workerIndex}`;
		const { authedApi: attendeeApi, api: attendeeBase } = await createUserAndGetToken(
			secondaryUserEmail('attendee', tag),
			'Attendee User'
		);
		try {
			await attendEvent(attendeeApi, event.id);
			const ok = await voteForProjects(attendeeApi, event.id, [ownProject.id]);
			expect(ok.ok()).toBe(true);
		} finally {
			await attendeeApi.dispose();
			await attendeeBase.dispose();
		}
	});
});

test.describe('API coverage — PROJECTS router', () => {
	test('GET /projects/mine returns owned + collaborating projects', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('Mine', testInfo) });
		await attendEvent(authedApi, event.id);
		const project = await createProject(authedApi, {
			name: unique('Mine Project', testInfo),
			description: '',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});

		const mine = await getMyProjects(authedApi);
		expect(mine.some((p: { id: string }) => p.id === project.id)).toBe(true);
	});

	test('GET /projects/{project_id} returns a public project and 404s on unknown IDs', async ({
		api,
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('GetProj', testInfo) });
		await attendEvent(authedApi, event.id);
		const project = await createProject(authedApi, {
			name: unique('GetProj P', testInfo),
			description: '',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});

		// Public endpoint — anonymous client works
		const resp = await getProject(api, project.id);
		expect(resp.ok()).toBe(true);

		const missing = await getProject(api, BAD_UUID);
		expect(missing.status()).toBe(404);
	});

	test('PUT + DELETE /projects/{id} enforce ownership', async ({ authedApi }, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('Mutate', testInfo) });
		await attendEvent(authedApi, event.id);
		const project = await createProject(authedApi, {
			name: unique('Mutate P', testInfo),
			description: 'orig',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});

		// Update
		const updateResp = await updateProject(authedApi, project.id, {
			description: 'updated by test'
		});
		expect(updateResp.ok()).toBe(true);
		const updated = await updateResp.json();
		expect(updated.description).toBe('updated by test');

		// Non-owner cannot update → 403
		const tag = `owner-${Date.now()}-w${testInfo.workerIndex}`;
		const { authedApi: otherApi, api: otherBase } = await createUserAndGetToken(
			secondaryUserEmail('attendee', tag),
			'Other User'
		);
		try {
			const forbid = await updateProject(otherApi, project.id, { name: 'nope' });
			expect(forbid.status()).toBe(403);

			const forbidDel = await deleteProject(otherApi, project.id);
			expect(forbidDel.status()).toBe(403);
		} finally {
			await otherApi.dispose();
			await otherBase.dispose();
		}

		// Owner can delete
		const delResp = await deleteProject(authedApi, project.id);
		expect(delResp.ok()).toBe(true);
	});

	test('POST /projects/join adds a collaborator via join_code', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('Join', testInfo) });
		await attendEvent(authedApi, event.id);
		const project = await createProject(authedApi, {
			name: unique('Join P', testInfo),
			description: '',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});

		const tag = `join-${Date.now()}-w${testInfo.workerIndex}`;
		const { authedApi: collabApi, api: collabBase } = await createUserAndGetToken(
			secondaryUserEmail('attendee', tag),
			'Collab User'
		);
		try {
			await attendEvent(collabApi, event.id);
			const ok = await joinProject(collabApi, project.join_code);
			expect(ok.ok()).toBe(true);

			// Joining twice should be rejected
			const dup = await joinProject(collabApi, project.join_code);
			expect(dup.status()).toBe(400);

			// Unknown code → 404
			const bogus = await joinProject(collabApi, 'NOT-A-REAL-CODE');
			expect(bogus.status()).toBe(404);
		} finally {
			await collabApi.dispose();
			await collabBase.dispose();
		}
	});

	test('POST /projects/validate queues background re-validation', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('Validate', testInfo) });
		await attendEvent(authedApi, event.id);

		const project = await createProject(authedApi, {
			name: unique('ToValidate', testInfo),
			description: '',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});

		// Validate queues background work and returns a 200 with valid=true
		const resp = await validateProject(authedApi, project.id);
		expect(resp.ok()).toBe(true);
		const body = await resp.json();
		expect(body).toHaveProperty('valid');
		expect(body).toHaveProperty('message');

		// Non-owner cannot trigger re-validation
		const tag = `valout-${Date.now()}-w${testInfo.workerIndex}`;
		const { authedApi: outsiderApi, api: outsiderBase } = await createUserAndGetToken(
			secondaryUserEmail('attendee', tag),
			'Outsider'
		);
		try {
			const denied = await validateProject(outsiderApi, project.id);
			expect(denied.status()).toBe(403);
		} finally {
			await outsiderApi.dispose();
			await outsiderBase.dispose();
		}
	});
});

test.describe('API coverage — ADMIN router', () => {
	test('GET /events/admin/{id} returns EventPrivate for the owner', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('AdminGet', testInfo) });
		const resp = await adminGetEvent(authedApi, event.id);
		expect(resp.ok()).toBe(true);
		const body = await resp.json();
		expect(body.id).toBe(event.id);
		expect(body).toHaveProperty('owner_id');
	});

	test('GET /events/admin/{id} returns 403 for non-owners', async ({ authedApi }, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('AdminDeny', testInfo) });
		const tag = `outsider-${Date.now()}-w${testInfo.workerIndex}`;
		const { authedApi: outsiderApi, api: outsiderBase } = await createUserAndGetToken(
			secondaryUserEmail('attendee', tag),
			'Outsider User'
		);
		try {
			const resp = await adminGetEvent(outsiderApi, event.id);
			expect(resp.status()).toBe(403);
		} finally {
			await outsiderApi.dispose();
			await outsiderBase.dispose();
		}
	});

	test('PATCH /events/admin/{id} updates mutable fields', async ({ authedApi }, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('AdminPatch', testInfo) });
		const resp = await adminPatchEvent(authedApi, event.id, {
			description: 'patched by test',
			repo_validation: 'none'
		});
		expect(resp.ok()).toBe(true);
		const body = await resp.json();
		expect(body.description).toBe('patched by test');
		expect(body.repo_validation).toBe('none');
	});

	test('GET /events/admin/{id}/attendees lists attendees', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('AdminAttendees', testInfo) });
		await attendEvent(authedApi, event.id);
		const resp = await adminGetAttendees(authedApi, event.id);
		expect(resp.ok()).toBe(true);
		const attendees = await resp.json();
		expect(Array.isArray(attendees)).toBe(true);
		expect(attendees.length).toBeGreaterThanOrEqual(1);
		expect(attendees[0]).toHaveProperty('email');
	});

	test('POST /events/admin/{id}/remove-attendee drops a user from the event', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('RemoveAtt', testInfo) });
		const tag = `toremove-${Date.now()}-w${testInfo.workerIndex}`;
		const { authedApi: attendeeApi, api: attendeeBase } = await createUserAndGetToken(
			secondaryUserEmail('attendee', tag),
			'To Remove'
		);
		try {
			await attendEvent(attendeeApi, event.id);
			const me = await getCurrentUser(attendeeApi);

			const removeResp = await adminRemoveAttendee(authedApi, event.id, me.id);
			expect(removeResp.ok()).toBe(true);

			const after = await adminGetAttendees(authedApi, event.id);
			const list = await after.json();
			expect(list.some((a: { id: string }) => a.id === me.id)).toBe(false);
		} finally {
			await attendeeApi.dispose();
			await attendeeBase.dispose();
		}
	});

	test('GET /events/admin/{id}/leaderboard returns ranked projects', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('AdminLB', testInfo) });
		await attendEvent(authedApi, event.id);
		await createProject(authedApi, {
			name: unique('LB P', testInfo),
			description: '',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});
		const resp = await adminGetLeaderboard(authedApi, event.id);
		expect(resp.ok()).toBe(true);
		const projects = await resp.json();
		expect(Array.isArray(projects)).toBe(true);
		expect(projects.length).toBeGreaterThanOrEqual(1);
	});

	test('GET /events/admin/{id}/votes lists votes cast on the event', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('AdminVotes', testInfo) });
		await attendEvent(authedApi, event.id);
		const ownerProject = await createProject(authedApi, {
			name: unique('Vote Target', testInfo),
			description: '',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});

		const tag = `voter-${Date.now()}-w${testInfo.workerIndex}`;
		const { authedApi: voterApi, api: voterBase } = await createUserAndGetToken(
			secondaryUserEmail('attendee', tag),
			'Voter User'
		);
		try {
			await attendEvent(voterApi, event.id);
			const voteResp = await voteForProjects(voterApi, event.id, [ownerProject.id]);
			expect(voteResp.ok()).toBe(true);

			const resp = await adminGetVotes(authedApi, event.id);
			expect(resp.ok()).toBe(true);
			const votes = await resp.json();
			expect(votes.length).toBeGreaterThanOrEqual(1);
			expect(votes[0]).toHaveProperty('voter_id');
			expect(votes[0]).toHaveProperty('project_id');
		} finally {
			await voterApi.dispose();
			await voterBase.dispose();
		}
	});

	test('GET /events/admin/{id}/referrals returns the (possibly empty) referral list', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('AdminRef', testInfo) });
		const resp = await adminGetReferrals(authedApi, event.id);
		expect(resp.ok()).toBe(true);
		const referrals = await resp.json();
		expect(Array.isArray(referrals)).toBe(true);
	});

	test('POST /events/admin/{id}/finalists locks the top judge-scored projects', async ({
		authedApi
	}, testInfo) => {
		const tag = `finalists-${Date.now()}-w${testInfo.workerIndex}`;
		const event = await createTestEvent(authedApi, { name: unique('Finalists', testInfo) });
		await attendEvent(authedApi, event.id);
		const project = await createProject(authedApi, {
			name: unique('Finalist P', testInfo),
			description: '',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});

		// Nothing judged yet → 400
		const tooEarly = await adminLockFinalists(authedApi, event.id);
		expect(tooEarly.status()).toBe(400);

		await setRoundOpen(authedApi, event.id, 'judging_open', true);
		const judge = await createJudgeAndGetToken(
			secondaryUserEmail('admin', tag),
			'Finalist Judge',
			event.id
		);
		try {
			const scored = await judgeScoreProject(judge.authedApi, event.id, project.id, {
				originality: 9,
				technicality: 9,
				theme: 9,
				usability: 9
			});
			expect(scored.ok()).toBe(true);
		} finally {
			await judge.authedApi.dispose();
			await judge.api.dispose();
		}

		const resp = await adminLockFinalists(authedApi, event.id);
		expect(resp.ok()).toBe(true);
		const finalists = await resp.json();
		expect(finalists.some((f: { project_id: string }) => f.project_id === project.id)).toBe(true);

		// finalist_count is exposed on the event so the ballot can size itself
		const updated = await getEvent(authedApi, event.id);
		expect(updated.finalist_count).toBe(1);
	});
});

test.describe('API coverage — JUDGING router', () => {
	test('GET /judging/{id}/projects is judge-only and gated on the judging round', async ({
		authedApi
	}, testInfo) => {
		const tag = `judgelist-${Date.now()}-w${testInfo.workerIndex}`;
		const event = await createTestEvent(authedApi, { name: unique('JudgeList', testInfo) });
		await attendEvent(authedApi, event.id);
		const project = await createProject(authedApi, {
			name: unique('JudgeList P', testInfo),
			description: '',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});

		// Event owner is not a judge → 403
		const notAJudge = await judgeGetProjects(authedApi, event.id);
		expect(notAJudge.status()).toBe(403);

		const judge = await createJudgeAndGetToken(
			secondaryUserEmail('admin', tag),
			'List Judge',
			event.id
		);
		try {
			// Judging round hasn't been opened yet
			const roundClosed = await judgeGetProjects(judge.authedApi, event.id);
			expect(roundClosed.status()).toBe(403);

			await setRoundOpen(authedApi, event.id, 'judging_open', true);
			const resp = await judgeGetProjects(judge.authedApi, event.id);
			expect(resp.ok()).toBe(true);
			const body = await resp.json();
			const listed = body.projects.find((p: { id: string }) => p.id === project.id);
			expect(listed).toBeDefined();
			expect(listed.my_score).toBeNull();
			expect(listed).toHaveProperty('owner_display_name');
		} finally {
			await judge.authedApi.dispose();
			await judge.api.dispose();
		}
	});

	test('PUT /judging/{id}/scores/{project_id} upserts a score and blocks self-scoring', async ({
		authedApi
	}, testInfo) => {
		const tag = `judgescore-${Date.now()}-w${testInfo.workerIndex}`;
		const event = await createTestEvent(authedApi, { name: unique('JudgeScore', testInfo) });
		await attendEvent(authedApi, event.id);
		const project = await createProject(authedApi, {
			name: unique('JudgeScore P', testInfo),
			description: '',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});
		await setRoundOpen(authedApi, event.id, 'judging_open', true);

		const judge = await createJudgeAndGetToken(
			secondaryUserEmail('admin', tag),
			'Scoring Judge',
			event.id
		);
		try {
			const created = await judgeScoreProject(judge.authedApi, event.id, project.id, {
				originality: 5,
				technicality: 6,
				theme: 7,
				usability: 8
			});
			expect(created.ok()).toBe(true);
			expect((await created.json()).total).toBe(26);

			// Re-scoring replaces the judge's previous score
			const updated = await judgeScoreProject(judge.authedApi, event.id, project.id, {
				originality: 10,
				technicality: 10,
				theme: 10,
				usability: 10
			});
			expect(updated.ok()).toBe(true);
			expect((await updated.json()).total).toBe(40);

			// Criteria are ints 1-10
			const outOfRange = await judgeScoreProject(judge.authedApi, event.id, project.id, {
				originality: 11,
				technicality: 1,
				theme: 1,
				usability: 1
			});
			expect(outOfRange.status()).toBe(422);

			// A judge cannot score a project they own
			await attendEvent(judge.authedApi, event.id);
			const ownProject = await createProject(judge.authedApi, {
				name: unique('Judge Own P', testInfo),
				description: '',
				event_id: event.id,
				repo: 'https://github.com/heycastawhat/kiwihacks-podium',
				image_url:
					'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
			});
			const selfScore = await judgeScoreProject(judge.authedApi, event.id, ownProject.id, {
				originality: 10,
				technicality: 10,
				theme: 10,
				usability: 10
			});
			expect(selfScore.status()).toBe(403);
		} finally {
			await judge.authedApi.dispose();
			await judge.api.dispose();
		}
	});

	test('GET /judging/{id}/results ranks projects for judges and the owner', async ({
		authedApi
	}, testInfo) => {
		const tag = `judgeresults-${Date.now()}-w${testInfo.workerIndex}`;
		const event = await createTestEvent(authedApi, { name: unique('JudgeResults', testInfo) });
		await attendEvent(authedApi, event.id);
		const low = await createProject(authedApi, {
			name: unique('Low P', testInfo),
			description: '',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});
		const high = await createProject(authedApi, {
			name: unique('High P', testInfo),
			description: '',
			event_id: event.id,
			repo: 'https://github.com/heycastawhat/kiwihacks-podium',
			image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
		});
		await setRoundOpen(authedApi, event.id, 'judging_open', true);

		const judge = await createJudgeAndGetToken(
			secondaryUserEmail('admin', tag),
			'Results Judge',
			event.id
		);
		try {
			await judgeScoreProject(judge.authedApi, event.id, low.id, {
				originality: 2,
				technicality: 2,
				theme: 2,
				usability: 2
			});
			await judgeScoreProject(judge.authedApi, event.id, high.id, {
				originality: 9,
				technicality: 9,
				theme: 9,
				usability: 9
			});

			// Judges can read the standings too
			const judgeView = await getJudgingResults(judge.authedApi, event.id);
			expect(judgeView.ok()).toBe(true);
		} finally {
			await judge.authedApi.dispose();
			await judge.api.dispose();
		}

		const resp = await getJudgingResults(authedApi, event.id);
		expect(resp.ok()).toBe(true);
		const results = await resp.json();
		expect(results[0].project_id).toBe(high.id);
		expect(results[0].judge_count).toBe(1);
		expect(results[0].judge_score).toBe(36);
		expect(results[0].averages.originality).toBe(9);
		expect(results[0].is_finalist).toBe(false);

		// Neither a judge nor the owner → 403
		const outsiderTag = `resultsout-${Date.now()}-w${testInfo.workerIndex}`;
		const { authedApi: outsiderApi, api: outsiderBase } = await createUserAndGetToken(
			secondaryUserEmail('attendee', outsiderTag),
			'Results Outsider'
		);
		try {
			const denied = await getJudgingResults(outsiderApi, event.id);
			expect(denied.status()).toBe(403);
		} finally {
			await outsiderApi.dispose();
			await outsiderBase.dispose();
		}
	});

	test('judging access is scoped to one event', async ({ authedApi }, testInfo) => {
		const tag = `judgescope-${Date.now()}-w${testInfo.workerIndex}`;
		const event = await createTestEvent(authedApi, { name: unique('ScopeA', testInfo) });
		const other = await createTestEvent(authedApi, { name: unique('ScopeB', testInfo) });
		await setRoundOpen(authedApi, event.id, 'judging_open', true);
		await setRoundOpen(authedApi, other.id, 'judging_open', true);

		const judge = await createJudgeAndGetToken(
			secondaryUserEmail('admin', tag),
			'Scoped Judge',
			event.id
		);
		try {
			expect((await judgeGetProjects(judge.authedApi, event.id)).ok()).toBe(true);
			// Judging one event grants nothing on another
			expect((await judgeGetProjects(judge.authedApi, other.id)).status()).toBe(403);
			expect((await getJudgingResults(judge.authedApi, other.id)).status()).toBe(403);
		} finally {
			await judge.authedApi.dispose();
			await judge.api.dispose();
		}
	});

	test('GET/POST /events/admin/{id}/judges manages judges by email', async ({
		authedApi
	}, testInfo) => {
		const tag = `judgecrud-${Date.now()}-w${testInfo.workerIndex}`;
		const event = await createTestEvent(authedApi, { name: unique('JudgeCrud', testInfo) });
		await setRoundOpen(authedApi, event.id, 'judging_open', true);

		expect(await (await adminGetJudges(authedApi, event.id)).json()).toEqual([]);

		const email = secondaryUserEmail('attendee', tag);
		// No account with that email yet
		expect((await adminAddJudge(authedApi, event.id, email)).status()).toBe(404);

		const { authedApi: judgeApi, api: judgeBase } = await createUserAndGetToken(
			email,
			'Crud Judge'
		);
		try {
			const added = await adminAddJudge(authedApi, event.id, email);
			expect(added.ok()).toBe(true);
			expect((await added.json()).email).toBe(email);

			// Adding twice is a no-op, not an error
			expect((await adminAddJudge(authedApi, event.id, email)).ok()).toBe(true);
			const listed = await (await adminGetJudges(authedApi, event.id)).json();
			expect(listed).toHaveLength(1);
			expect((await judgeGetProjects(judgeApi, event.id)).ok()).toBe(true);

			// The owner already sees everything a judge does
			const me = await getCurrentUser(authedApi);
			expect((await adminAddJudge(authedApi, event.id, me.email)).status()).toBe(400);

			expect((await adminRemoveJudge(authedApi, event.id, listed[0].id)).ok()).toBe(true);
			expect(await (await adminGetJudges(authedApi, event.id)).json()).toEqual([]);
			expect((await judgeGetProjects(judgeApi, event.id)).status()).toBe(403);
		} finally {
			await judgeApi.dispose();
			await judgeBase.dispose();
		}
	});

	test('POST /events/admin/{id}/judge-code + POST /judging/redeem make a judge', async ({
		authedApi
	}, testInfo) => {
		const tag = `judgecode-${Date.now()}-w${testInfo.workerIndex}`;
		const event = await createTestEvent(authedApi, { name: unique('JudgeCode', testInfo) });
		await setRoundOpen(authedApi, event.id, 'judging_open', true);

		const first = await adminRotateJudgeCode(authedApi, event.id);
		expect(first.ok()).toBe(true);
		const { judge_code: code } = await first.json();
		expect(code).toMatch(/^\d{6}$/);

		const { authedApi: userApi, api: userBase } = await createUserAndGetToken(
			secondaryUserEmail('attendee', tag),
			'Code Redeemer'
		);
		try {
			// Not a judge yet
			expect((await judgeGetProjects(userApi, event.id)).status()).toBe(403);

			expect((await redeemJudgeCode(userApi, '000')).status()).toBe(400);
			expect((await redeemJudgeCode(userApi, '999999')).status()).toBe(404);

			const redeemed = await redeemJudgeCode(userApi, code);
			expect(redeemed.ok()).toBe(true);
			const { access_token, event_slug } = await redeemed.json();
			expect(event_slug).toBe(event.slug);

			// Redeeming provisions a separate code-only judge identity rather than
			// granting judge access to whoever made the call.
			expect((await getCurrentUser(userApi)).judge_event_ids).not.toContain(event.id);
			const judgeApi = await apiRequest.newContext({
				extraHTTPHeaders: { Authorization: `Bearer ${access_token}` }
			});
			try {
				expect((await judgeGetProjects(judgeApi, event.id)).ok()).toBe(true);
			} finally {
				await judgeApi.dispose();
			}

			// The address the judge typed is kept for the organiser, while their
			// login identity stays in the unroutable placeholder namespace.
			const judgeList = await (await adminGetJudges(authedApi, event.id)).json();
			const codeJudge = judgeList.find(
				(j: { judge_email?: string }) => j.judge_email === 'code.judge@example.com'
			);
			expect(codeJudge).toBeDefined();
			expect(codeJudge.email).toMatch(/@judge\.invalid$/);

			// Rotating invalidates the old code
			const second = await adminRotateJudgeCode(authedApi, event.id);
			expect(second.ok()).toBe(true);
			expect((await second.json()).judge_code).not.toBe(code);
			expect((await redeemJudgeCode(userApi, code)).status()).toBe(404);
		} finally {
			await userApi.dispose();
			await userBase.dispose();
		}
	});

	test('POST /events/admin/{id}/judge-cards mints single-use codes that burn on redeem', async ({
		authedApi
	}, testInfo) => {
		const tag = `cards-${Date.now()}-w${testInfo.workerIndex}`;
		const event = await createTestEvent(authedApi, { name: unique('JudgeCards', testInfo) });

		const minted = await (await adminMintJudgeCards(authedApi, event.id, 2)).json();
		expect(minted).toHaveLength(2);
		const [first, second] = minted.map((c: { code: string }) => c.code);
		expect(first).toMatch(/^\d{6}$/);
		expect(first).not.toBe(second);

		const anon = await apiRequest.newContext();
		try {
			// First judge burns the card
			const claimed = await redeemJudgeCode(anon, first, 'Card Judge', `card+${tag}@example.com`);
			expect(claimed.ok()).toBe(true);

			// A different person cannot reuse it
			const reused = await redeemJudgeCode(anon, first, 'Someone Else', `other+${tag}@example.com`);
			expect(reused.status()).toBe(409);

			// Nor can the original judge — the card is spent, not personal
			const again = await redeemJudgeCode(anon, first, 'Card Judge', `card+${tag}@example.com`);
			expect(again.status()).toBe(409);

			// The spare card still works
			expect((await redeemJudgeCode(anon, second, 'Spare Judge', `spare+${tag}@example.com`)).ok()).toBe(true);
		} finally {
			await anon.dispose();
		}

		const listed = await (await adminGetJudgeCards(authedApi, event.id)).json();
		expect(listed).toHaveLength(2);
		expect(listed.every((c: { redeemed_at: string | null }) => c.redeemed_at)).toBe(true);
		expect(listed.find((c: { code: string }) => c.code === first).redeemed_by).toBe('Card Judge');
	});
});

test.describe('API coverage — EVENT PHASE lifecycle', () => {
	// The phase gates the public leaderboard (CLOSED only); the voting round is a
	// separate switch (voting_open). This walks both and checks each gate.
	test('phase gates the leaderboard, voting_open gates the ballot', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, { name: unique('Lifecycle', testInfo) });
		await attendEvent(authedApi, event.id);

		// Second user will do the voting so we don't hit the self-vote rule.
		const tag = `life-${Date.now()}-w${testInfo.workerIndex}`;
		const { authedApi: voterApi, api: voterBase } = await createUserAndGetToken(
			secondaryUserEmail('attendee', tag),
			'Lifecycle Voter'
		);
		try {
			await attendEvent(voterApi, event.id);
			const project = await createProject(authedApi, {
				name: unique('Lifecycle P', testInfo),
				description: '',
				event_id: event.id,
				repo: 'https://github.com/heycastawhat/kiwihacks-podium',
				image_url: 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md'
			});
			// Closing the voting round blocks the ballot, whatever the phase says.
			await setRoundOpen(authedApi, event.id, 'voting_open', false);
			const submissionResp = await adminPatchEvent(authedApi, event.id, { phase: 'submission' });
			expect(submissionResp.ok()).toBe(true);
			const noVote = await voteForProjects(voterApi, event.id, [project.id]);
			expect(noVote.status()).toBe(403);

			// Reopening it lets the ballot through while the phase is still SUBMISSION.
			await setRoundOpen(authedApi, event.id, 'voting_open', true);
			const okVote = await voteForProjects(voterApi, event.id, [project.id]);
			expect(okVote.ok()).toBe(true);

			// Public leaderboard is gated on CLOSED phase.
			const hiddenLB = await getEventProjects(voterApi, event.id, true);
			expect(hiddenLB.status()).toBe(403);

			const closedResp = await adminPatchEvent(authedApi, event.id, { phase: 'closed' });
			expect(closedResp.ok()).toBe(true);
			const visibleLB = await getEventProjects(voterApi, event.id, true);
			expect(visibleLB.ok()).toBe(true);
			const lb = await visibleLB.json();
			expect(Array.isArray(lb)).toBe(true);
		} finally {
			await voterApi.dispose();
			await voterBase.dispose();
		}
	});
});

test.describe('API coverage — TEST endpoints', () => {
	test('POST /events/test/create accepts description and sets VOTING phase', async ({
		authedApi
	}, testInfo) => {
		const event = await createTestEvent(authedApi, {
			name: unique('TestCreate', testInfo),
			description: 'with description'
		});
		expect(event.phase).toBe('voting');
		expect(event.description).toBe('with description');
	});

	// POST /events/test/cleanup is intentionally NOT invoked here — it reaps
	// data for every worker and would break parallel tests. It is covered by
	// running it manually out of band or as a post-suite cleanup hook.
});
