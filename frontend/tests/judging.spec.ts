/**
 * Two-round judging: judges score every project during the JUDGING phase, the
 * organizer locks in the finalists, and attendees then rank those finalists
 * 1st/2nd/3rd (worth 3/2/1 points) during VOTING.
 *
 * Judge accounts, judge scores used as fixtures, and phase changes are set up
 * over the API; every round-specific assertion goes through the UI.
 */

import { test, expect } from './fixtures/auth';
import type { Browser, Page } from '@playwright/test';
import { unique } from './utils/data';
import {
	adminGetVotes,
	adminLockFinalists,
	attendEvent,
	createProject,
	createTestEvent,
	judgeGetProjects,
	judgeScoreProject,
	setEventPhase,
	setRoundOpen,
	voteForProjects
} from './helpers/api';
import {
	authedStorageState,
	createJudgeAndGetToken,
	createUserAndGetToken,
	secondaryUserEmail
} from './helpers/users';

const REPO = 'https://github.com/heycastawhat/kiwihacks-podium';
const IMAGE = 'https://raw.githubusercontent.com/heycastawhat/kiwihacks-podium/main/README.md';

/** Browser context for a user who isn't the worker fixture user. */
async function createAuthenticatedPage(
	browser: Browser,
	token: string,
	baseURL: string
): Promise<Page> {
	const context = await browser.newContext({
		baseURL,
		storageState: authedStorageState(token, baseURL)
	});
	const page = await context.newPage();
	await page.goto('/');
	await page
		.waitForResponse(
			(r) => r.url().includes('/users/current') && r.request().method() === 'GET' && r.ok(),
			{ timeout: 30000 }
		)
		.catch(() => {});
	return page;
}

test.describe('Judging round', () => {
	/**
	 * A judge grades one project on all four criteria and the saved score is
	 * still there after a reload.
	 */
	test('judge scores a project and the score persists on reload', async ({
		browser,
		authedApi
	}, testInfo) => {
		const tag = `${Date.now()}-w${testInfo.workerIndex}`;
		const baseURL = String(testInfo.project.use.baseURL || 'http://127.0.0.1:4174');

		const event = await createTestEvent(authedApi, { name: unique('Judge Score', testInfo) });
		await attendEvent(authedApi, event.id);
		const projectName = unique('Judged Project', testInfo);
		await createProject(authedApi, {
			name: projectName,
			description: 'scored by a judge',
			event_id: event.id,
			repo: REPO,
			image_url: IMAGE
		});
		await setEventPhase(authedApi, event.id, 'judging');
		await setRoundOpen(authedApi, event.id, 'judging_open', true);

		const judge = await createJudgeAndGetToken(
			secondaryUserEmail('admin', `judge-${tag}`),
			'Judge User',
			event.id
		);
		const judgePage = await createAuthenticatedPage(browser, judge.token, baseURL);
		try {
			// Judge page loads server-side, so assert the UI rather than the response
			await judgePage.goto(`/events/${event.slug}/judge`);
			await expect(judgePage.getByRole('heading', { name: 'Your grades' })).toBeVisible({
				timeout: 15000
			});
			await expect(judgePage.getByRole('heading', { name: projectName })).toBeVisible();

			// Distinct value per criterion so the reload check can tell them apart
			const scores: [string, number][] = [
				['Originality', 7],
				['Technicality', 8],
				['Theme', 9],
				['Usability', 10]
			];
			for (const [criterion, value] of scores) {
				await judgePage
					.getByRole('radio', { name: `${value} out of 10 for ${criterion}` })
					.check();
			}

			const saved = judgePage.waitForResponse(
				(r) =>
					r.url().includes(`/judging/${event.id}/scores/`) &&
					r.request().method() === 'PUT' &&
					r.ok(),
				{ timeout: 15000 }
			);
			await judgePage.getByRole('button', { name: 'Save score' }).click();
			await saved;
			await expect(judgePage.getByText(`Saved your grades for ${projectName}`)).toBeVisible({
				timeout: 10000
			});

			await judgePage.reload();
			// Every project is scored now, so the thank-you replaces the grading UI
			await expect(judgePage.getByRole('heading', { name: 'Thanks!' })).toBeVisible({
				timeout: 15000
			});
			await judgePage.getByRole('button', { name: 'Review my grades' }).click();
			for (const [criterion, value] of scores) {
				await expect(
					judgePage.getByRole('radio', { name: `${value} out of 10 for ${criterion}` })
				).toBeChecked({ timeout: 15000 });
			}
			await expect(judgePage.getByText('1 of 1 scored')).toBeVisible();
		} finally {
			await judgePage.context().close();
			await judge.authedApi.dispose();
			await judge.api.dispose();
		}
	});

	/**
	 * Judging is judge-only: an attendee without the flag gets the warning in
	 * the UI and a 403 from the judging API.
	 */
	test('attendee without judge access is refused judging', async ({
		browser,
		authedApi
	}, testInfo) => {
		const tag = `${Date.now()}-w${testInfo.workerIndex}`;
		const baseURL = String(testInfo.project.use.baseURL || 'http://127.0.0.1:4174');

		const event = await createTestEvent(authedApi, { name: unique('Judge Denied', testInfo) });
		await attendEvent(authedApi, event.id);
		await createProject(authedApi, {
			name: unique('Unjudged Project', testInfo),
			description: 'nobody may judge this',
			event_id: event.id,
			repo: REPO,
			image_url: IMAGE
		});
		await setEventPhase(authedApi, event.id, 'judging');
		await setRoundOpen(authedApi, event.id, 'judging_open', true);

		const attendee = await createUserAndGetToken(
			secondaryUserEmail('attendee', `nonjudge-${tag}`),
			'Non Judge'
		);
		const attendeePage = await createAuthenticatedPage(browser, attendee.token, baseURL);
		try {
			await attendEvent(attendee.authedApi, event.id);

			const denied = await judgeGetProjects(attendee.authedApi, event.id);
			expect(denied.status()).toBe(403);

			await attendeePage.goto(`/events/${event.slug}/judge`);
			await expect(attendeePage.getByText(/judging access is required/i)).toBeVisible({
				timeout: 15000
			});
			await expect(attendeePage.getByRole('heading', { name: 'Your grades' })).not.toBeVisible();
		} finally {
			await attendeePage.context().close();
			await attendee.authedApi.dispose();
			await attendee.api.dispose();
		}
	});
});

test.describe('Ranked ballot', () => {
	/**
	 * Organizer locks in finalists from the judging panel, then the attendee
	 * ballot only offers those finalists and records a ranked vote.
	 */
	test('organizer locks finalists and attendee submits a ranked ballot', async ({
		browser,
		authedApi,
		authedPage
	}, testInfo) => {
		const tag = `${Date.now()}-w${testInfo.workerIndex}`;
		const baseURL = String(testInfo.project.use.baseURL || 'http://127.0.0.1:4174');

		const event = await createTestEvent(authedApi, { name: unique('Finalists', testInfo) });
		await attendEvent(authedApi, event.id);

		// Six projects, five of them judged — the unjudged one can never be a
		// finalist, so it proves the ballot is filtered.
		const projects: { id: string; name: string }[] = [];
		for (let i = 1; i <= 6; i++) {
			projects.push(
				await createProject(authedApi, {
					name: unique(`Ballot P${i}`, testInfo),
					description: `ballot project ${i}`,
					event_id: event.id,
					repo: REPO,
					image_url: IMAGE
				})
			);
		}
		await setEventPhase(authedApi, event.id, 'judging');
		await setRoundOpen(authedApi, event.id, 'judging_open', true);

		const judge = await createJudgeAndGetToken(
			secondaryUserEmail('admin', `finalists-${tag}`),
			'Finalist Judge',
			event.id
		);
		try {
			for (const [i, project] of projects.slice(0, 5).entries()) {
				const score = 10 - i;
				const resp = await judgeScoreProject(judge.authedApi, event.id, project.id, {
					originality: score,
					technicality: score,
					theme: score,
					usability: score
				});
				expect(resp.ok()).toBe(true);
			}
		} finally {
			await judge.authedApi.dispose();
			await judge.api.dispose();
		}

		// Organizer locks in the finalists from the admin panel's judging section
		const resultsLoaded = authedPage.waitForResponse(
			(r) => r.url().includes(`/judging/${event.id}/results`) && r.ok(),
			{ timeout: 15000 }
		);
		await authedPage.goto(`/events/${event.slug}`);
		await resultsLoaded;

		const judgingPanel = authedPage.locator('.card').filter({ hasText: 'Judging (' });
		await expect(judgingPanel.getByText('5 of 6 projects have been scored')).toBeVisible({
			timeout: 10000
		});
		await judgingPanel.getByRole('button', { name: 'Lock in top 5 finalists' }).click();

		const locked = authedPage.waitForResponse(
			(r) =>
				r.url().includes(`/events/admin/${event.id}/finalists`) &&
				r.request().method() === 'POST' &&
				r.ok(),
			{ timeout: 15000 }
		);
		await authedPage.locator('.modal-box').getByRole('button', { name: 'Lock in finalists' }).click();
		await locked;

		await expect(authedPage.getByText('Locked in 5 finalists')).toBeVisible({ timeout: 10000 });
		await expect(judgingPanel.locator('.badge').filter({ hasText: 'Finalist' })).toHaveCount(5);

		// Move the event on to voting from the same panel
		const phasePatched = authedPage.waitForResponse(
			(r) =>
				r.url().includes(`/events/admin/${event.id}`) &&
				r.request().method() === 'PATCH' &&
				r.ok(),
			{ timeout: 10000 }
		);
		await authedPage.getByRole('combobox').selectOption('voting');
		await phasePatched;

		const attendee = await createUserAndGetToken(
			secondaryUserEmail('attendee', `ballot-${tag}`),
			'Ballot Attendee'
		);
		const attendeePage = await createAuthenticatedPage(browser, attendee.token, baseURL);
		try {
			await attendEvent(attendee.authedApi, event.id);

			await attendeePage.goto(`/events/${event.slug}/rank`);
			await expect(
				attendeePage.getByRole('heading', { name: 'Rank the 5 finalists' })
			).toBeVisible({ timeout: 15000 });

			// The unjudged project never became a finalist, so it is off the ballot
			await expect(attendeePage.getByText(projects[5].name)).toHaveCount(0);

			// Clicking in order sets the ranking: 1st, 2nd, 3rd choice
			const picks = projects.slice(0, 3);
			for (const project of picks) {
				await attendeePage.getByRole('button', { name: new RegExp(project.name) }).click();
			}

			const ballot = attendeePage.locator('section').filter({ hasText: 'Your ballot' });
			const ballotItems = ballot.locator('li');
			await expect(ballotItems).toHaveCount(3);
			await expect(ballotItems.nth(0)).toContainText('1st');
			await expect(ballotItems.nth(0)).toContainText(picks[0].name);
			await expect(ballotItems.nth(0)).toContainText('3 pts');
			await expect(ballotItems.nth(1)).toContainText('2nd');
			await expect(ballotItems.nth(1)).toContainText(picks[1].name);
			await expect(ballotItems.nth(1)).toContainText('2 pts');
			await expect(ballotItems.nth(2)).toContainText('3rd');
			await expect(ballotItems.nth(2)).toContainText(picks[2].name);
			await expect(ballotItems.nth(2)).toContainText('1 pt');

			const voted = attendeePage.waitForResponse(
				(r) => r.url().includes('/events/vote') && r.request().method() === 'POST' && r.ok(),
				{ timeout: 15000 }
			);
			await attendeePage.getByRole('button', { name: 'Submit vote' }).click();
			await voted;
			await expect(attendeePage.getByText('Vote submitted successfully')).toBeVisible({
				timeout: 10000
			});

			// The whole ballot was recorded, one vote per rank
			const votesResp = await adminGetVotes(authedApi, event.id);
			expect(votesResp.ok()).toBe(true);
			const votes = await votesResp.json();
			const votedProjectIds = votes.map((v: { project_id: string }) => v.project_id);
			expect(votedProjectIds).toHaveLength(3);
			for (const project of picks) {
				expect(votedProjectIds).toContain(project.id);
			}
		} finally {
			await attendeePage.context().close();
			await attendee.authedApi.dispose();
			await attendee.api.dispose();
		}
	});

	/**
	 * The closed-phase leaderboard is ordered by weighted points (3/2/1), not by
	 * how many people voted for a project: a project with a single 1st-choice
	 * vote outranks one with two 3rd-choice votes.
	 */
	test('leaderboard orders projects by weighted ballot points', async ({
		authedApi,
		authedPage
	}, testInfo) => {
		const tag = `${Date.now()}-w${testInfo.workerIndex}`;

		const event = await createTestEvent(authedApi, { name: unique('Weighted', testInfo) });
		await attendEvent(authedApi, event.id);

		const projects: { id: string; name: string }[] = [];
		for (let i = 1; i <= 6; i++) {
			projects.push(
				await createProject(authedApi, {
					name: unique(`Weighted P${i}`, testInfo),
					description: `weighted project ${i}`,
					event_id: event.id,
					repo: REPO,
					image_url: IMAGE
				})
			);
		}

		// Judging + finalist lock-in is what puts three ranks on the ballot
		await setEventPhase(authedApi, event.id, 'judging');
		await setRoundOpen(authedApi, event.id, 'judging_open', true);
		const judge = await createJudgeAndGetToken(
			secondaryUserEmail('admin', `weighted-${tag}`),
			'Weighted Judge',
			event.id
		);
		try {
			for (const [i, project] of projects.slice(0, 5).entries()) {
				const score = 10 - i;
				const resp = await judgeScoreProject(judge.authedApi, event.id, project.id, {
					originality: score,
					technicality: score,
					theme: score,
					usability: score
				});
				expect(resp.ok()).toBe(true);
			}
		} finally {
			await judge.authedApi.dispose();
			await judge.api.dispose();
		}
		const lockResp = await adminLockFinalists(authedApi, event.id);
		expect(lockResp.ok()).toBe(true);
		await setEventPhase(authedApi, event.id, 'voting');
		await setRoundOpen(authedApi, event.id, 'voting_open', true);

		// Ballot order is the ranking. Second choice is worth 2, third 1, so:
		//   projects[2] = 2 + 2 = 4 points from 2 votes
		//   projects[0] = 3 points from 1 vote
		//   projects[3] = 3 points from 1 vote
		//   projects[1] = 1 + 1 = 2 points from 2 votes
		const ballots: [string, string[]][] = [
			[`w1-${tag}`, [projects[0].id, projects[2].id, projects[1].id]],
			[`w2-${tag}`, [projects[3].id, projects[2].id, projects[1].id]]
		];
		for (const [voterTag, ranking] of ballots) {
			const voter = await createUserAndGetToken(
				secondaryUserEmail('attendee', voterTag),
				'Weighted Voter'
		);
			try {
				await attendEvent(voter.authedApi, event.id);
				const resp = await voteForProjects(voter.authedApi, event.id, ranking);
				expect(resp.ok()).toBe(true);
			} finally {
				await voter.authedApi.dispose();
				await voter.api.dispose();
			}
		}

		await setEventPhase(authedApi, event.id, 'closed');

		await authedPage.goto(`/events/${event.slug}/leaderboard`);
		await expect(authedPage.getByRole('heading', { name: 'Leaderboard' })).toBeVisible({
			timeout: 15000
		});

		const cardFor = (name: string) => authedPage.locator('.grid > div').filter({ hasText: name });
		await expect(cardFor(projects[2].name).getByText('Points: 4')).toBeVisible();
		await expect(cardFor(projects[0].name).getByText('Points: 3')).toBeVisible();
		await expect(cardFor(projects[3].name).getByText('Points: 3')).toBeVisible();
		await expect(cardFor(projects[1].name).getByText('Points: 2')).toBeVisible();

		const order = (await authedPage.locator('.grid .card-title').allTextContents()).map((t) =>
			t.trim()
		);
		expect(order[0]).toBe(projects[2].name);
		// Two 3rd-choice votes are worth less than a single 1st-choice vote
		expect(order.indexOf(projects[1].name)).toBeGreaterThan(order.indexOf(projects[0].name));
		expect(order.indexOf(projects[1].name)).toBeGreaterThan(order.indexOf(projects[3].name));
	});
});
