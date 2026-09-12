<script lang="ts">
  import { onMount } from "svelte";
  import { EventsService } from "$lib/client/sdk.gen";
  import type {
    UserAttendee,
    ProjectPrivate,
    EventPublic,
    EventPrivate,
    VoteResponse,
    ReferralResponse,
    VoteAuditResponse,
    VoteSuspicionResponse,
  } from "$lib/client/types.gen";
  import LoadingSpinner from "$lib/components/LoadingSpinner.svelte";
  import AttendeesTable from "./AttendeesTable.svelte";
  import AdminLeaderboard from "./AdminLeaderboard.svelte";
  import StageTimeline from "./StageTimeline.svelte";
  import RoundSwitches from "./RoundSwitches.svelte";
  import JudgesTable from "./JudgesTable.svelte";
  import JudgingPanel from "./JudgingPanel.svelte";
  import VotesTable from "./VotesTable.svelte";
  import VoteAuditTable from "./VoteAuditTable.svelte";
  import VoteSuspicionTable from "./VoteSuspicionTable.svelte";
  import ReferralsTable from "./ReferralsTable.svelte";
  import { handleError, returnLoadingText } from "$lib/misc";
  import { getAuthenticatedUser } from "$lib/user.svelte";
  import { toast } from "svelte-sonner";

  interface Props {
    event: EventPrivate & { owned: boolean; partOfEvent: boolean };
  }

  let { event }: Props = $props();

  // Admin state
  let attendees = $state<UserAttendee[]>([]);
  let adminLeaderboard = $state<ProjectPrivate[]>([]);
  let votes = $state<VoteResponse[]>([]);
  let voteAudit = $state<VoteAuditResponse[]>([]);
  let voteSuspicion = $state<VoteSuspicionResponse[]>([]);
  let referrals = $state<ReferralResponse[]>([]);
  let loading = $state(false);

  // Lookup maps for efficient data access
  let userLookup = $state<Map<string, string>>(new Map());
  let projectLookup = $state<Map<string, string>>(new Map());

  // Load admin data after component mounts
  onMount(async () => {
    if (event.owned) {
      await loadAdminData();
    }
  });

  async function loadAdminData() {
    loading = true;
    try {
      const [
        attendeesResult,
        leaderboardResult,
        votesResult,
        voteAuditResult,
        voteSuspicionResult,
        referralsResult,
      ] =
        await Promise.all([
          EventsService.getEventAttendeesEventsAdminEventIdAttendeesGet({
            path: { event_id: event.id },
            throwOnError: false,
          }),
          EventsService.getEventLeaderboardEventsAdminEventIdLeaderboardGet({
            path: { event_id: event.id },
            throwOnError: false,
          }),
          EventsService.getEventVotesEventsAdminEventIdVotesGet({
            path: { event_id: event.id },
            throwOnError: false,
          }),
          EventsService.getEventVoteAuditEventsAdminEventIdVoteAuditGet({
            path: { event_id: event.id },
            throwOnError: false,
          }),
          EventsService.getEventVoteSuspicionEventsAdminEventIdVoteSuspicionGet({
            path: { event_id: event.id },
            throwOnError: false,
          }),
          EventsService.getEventReferralsEventsAdminEventIdReferralsGet({
            path: { event_id: event.id },
            throwOnError: false,
          }),
        ]);

      if (attendeesResult.error) handleError(attendeesResult.error);
      else attendees = attendeesResult.data || [];

      if (leaderboardResult.error) handleError(leaderboardResult.error);
      else adminLeaderboard = leaderboardResult.data || [];

      if (votesResult.error) handleError(votesResult.error);
      else votes = votesResult.data || [];

      if (voteAuditResult.error) handleError(voteAuditResult.error);
      else voteAudit = voteAuditResult.data || [];

      if (voteSuspicionResult.error) handleError(voteSuspicionResult.error);
      else voteSuspicion = voteSuspicionResult.data || [];

      if (referralsResult.error) handleError(referralsResult.error);
      else referrals = referralsResult.data || [];

      // Build lookup maps from existing data
      buildLookupMaps();
    } catch (err) {
      handleError(err);
    } finally {
      loading = false;
    }
  }

  function buildLookupMaps() {
    // Build user lookup from attendees (for votes and referrals)
    userLookup.clear();
    attendees.forEach((attendee) => {
      userLookup.set(
        attendee.id,
        `${attendee.first_name} ${attendee.last_name || ""}`.trim(),
      );
    });

    // Build project lookup from admin leaderboard
    projectLookup.clear();
    adminLeaderboard.forEach((project) => {
      projectLookup.set(project.id, project.name);
    });
  }

  function isEventOwner(userId: string): boolean {
    const currentUser = getAuthenticatedUser();
    return currentUser.user.id === userId;
  }

  async function removeAttendee(userId: string) {
    // Prevent event owner from removing themselves
    // if (isEventOwner(userId)) {
      // toast.error("You cannot remove yourself from your own event");
      // return;
    // }

    try {
      const { error } =
        await EventsService.removeAttendeeEventsAdminEventIdRemoveAttendeePost({
          path: { event_id: event.id },
          body: { user_id: userId },
          throwOnError: false,
        });

      if (error) {
        handleError(error);
      } else {
        toast.success("Attendee removed");
        await loadAdminData();
      }
    } catch (err) {
      handleError(err);
    }
  }
</script>

{#if event.owned}
  <div class="divider">Admin Panel</div>

  {#if loading}
    <div class="flex justify-center py-8">
      <LoadingSpinner loadingText={returnLoadingText()} />
    </div>
  {:else}
    <div class="space-y-6">
      <!-- Event Status Timeline -->
      <StageTimeline
        {event}
        onUpdate={(updated) => {
          // Reflect the new phase locally so gating UI updates without a reload
          event.phase = updated.phase;
        }}
      />

      <!-- Judging / voting round switches -->
      <RoundSwitches
        {event}
        onUpdate={(updated) => {
          event.judging_open = updated.judging_open;
          event.voting_open = updated.voting_open;
        }}
      />

      <!-- Attendees Table -->
      <AttendeesTable {attendees} onRemoveAttendee={removeAttendee} {event} />

      <!-- Judges for this event + judge code -->
      <JudgesTable {event} />

      <!-- Judging Results + finalist lock-in -->
      <JudgingPanel {event} />

      <!-- Admin Leaderboard -->
      <AdminLeaderboard projects={adminLeaderboard} {event} />

      <!-- Votes Table -->
      <VotesTable {votes} {userLookup} {projectLookup} />

      <VoteSuspicionTable findings={voteSuspicion} {userLookup} />

      <VoteAuditTable logs={voteAudit} {userLookup} {projectLookup} />

      <!-- Referrals Table -->
      <ReferralsTable {referrals} {userLookup} />
    </div>
  {/if}
{/if}
