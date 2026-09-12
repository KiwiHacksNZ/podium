# Review Checklist

Flows to verify after major changes. **Most core flows are covered by e2e tests** (see `frontend/tests/journey.spec.ts`).

## Core Flow (✅ E2E tested)
- [ ] Register for a new account
- [ ] Login using magic link
- [ ] Select an official event from the list ✅
- [ ] Create a project via the wizard ✅
- [ ] View project validation result ✅
- [ ] Edit project if validation fails ✅

## Judging
- [ ] Generate an event judge code, redeem it at `/judge`, land on the judging page
- [ ] Rotating the code invalidates the old one
- [ ] Add a judge by email from the admin panel's Judges card, and remove them
- [ ] A judge for one event gets no access to another event
- [ ] Open the judging round with the admin panel's Rounds switch
- [ ] Score a project on all four criteria; reload and confirm it persisted
- [ ] Non-judge is refused the judging page
- [ ] Organizer sees judge standings and locks in the top 5 finalists

## Voting (✅ E2E tested)
- [ ] Judging and attendee voting can be open at the same time, and either alone
- [ ] Navigate to event ranking page ✅
- [ ] Only finalists appear on the ballot
- [ ] Picks show 1st / 2nd / 3rd choice labels in order
- [ ] Vote for projects ✅
- [ ] View leaderboard — order reflects weighted 3/2/1 points ✅

## Project Management (✅ E2E tested)
- [ ] Update own project ✅
- [ ] Delete own project ✅

## Collaboration
- [ ] Join existing project via join code
- [ ] Verify collaborator appears on project

## Organizer Admin (✅ E2E tested)
- [ ] View admin panel for event ✅
- [ ] Set event phase (draft → submission → judging → voting → closed) ✅
- [ ] View attendees list ✅
- [ ] Remove attendee ✅
