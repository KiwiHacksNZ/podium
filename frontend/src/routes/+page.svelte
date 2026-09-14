<script lang="ts">
  import { onMount } from "svelte";
  import { EventsService, ProjectsService } from "$lib/client/sdk.gen";
  import type { ProjectPrivate, EventPublic } from "$lib/client";
  import { getAuthenticatedUser, isAuthenticated } from "$lib/user.svelte";
  import EventSelector from "$lib/components/EventSelector.svelte";
  import ProjectSubmissionWizard from "$lib/components/ProjectSubmissionWizard.svelte";
  import OfficialEventsDisplay from "$lib/components/OfficialEventsDisplay.svelte";
  import { setHasProject } from "$lib/project-state.svelte";

  let officialEvents = $state<EventPublic[]>([]);
  let projects = $state<ProjectPrivate[]>([]);
  let attendingEvents = $state<EventPublic[]>([]);
  let loading = $state(true);

  // Only consider events the user is enrolled in AND are currently official
  const activeAttendingEvents = $derived(() => {
    const officialIds = new Set(officialEvents.map((e) => e.id));
    return attendingEvents.filter((e) => officialIds.has(e.id));
  });

  const currentEvent = $derived(() => activeAttendingEvents()[0]);

  // Keep global project state in sync
  $effect(() => {
    setHasProject(projects.length > 0);
  });

  onMount(async () => {
    // Always load official events — the home page is the event browser
    const officialRes = await EventsService.listOfficialEventsEventsOfficialGet({
      throwOnError: false,
    });
    if (!officialRes.error && officialRes.data) {
      officialEvents = officialRes.data as EventPublic[];
    }

    if (isAuthenticated()) {
      try {
        const [attendingRes, projectsRes] = await Promise.all([
          EventsService.getAttendingEventsEventsGet({ throwOnError: false }),
          ProjectsService.getProjectsProjectsMineGet({ throwOnError: false }),
        ]);

        if (!attendingRes.error && attendingRes.data) {
          attendingEvents = (attendingRes.data.attending_events ??
            []) as EventPublic[];
        }

        if (!projectsRes.error && projectsRes.data) {
          projects = projectsRes.data;
        }
      } catch (err) {
        console.error("Failed to load user data:", err);
      }
    }

    loading = false;
  });

  function handleEventJoined() {
    window.location.reload();
  }
</script>

{#if !isAuthenticated()}
  <!-- Unauthenticated: event-first landing — no login wall -->
  <div class="max-w-6xl mx-auto space-y-8">
    <!-- Hero -->
    <div class="card bg-base-100 shadow-lg">
      <div class="card-body flex flex-col items-center text-center gap-5 py-8">
        <img
          src="/assets/kiwihacks/kiwi-logo.png"
          alt="KiwiHacks mascot"
          class="w-40 md:w-48 object-contain select-none"
        />
        <img
          src="/assets/kiwihacks/kiwi-text.png"
          alt="Kiwihacks"
          class="w-72 md:w-[28rem] object-contain select-none"
        />
        <p class="mono text-lg text-base-content/80">
          {officialEvents[0]?.description ||
            "KiwiHacks Podium"}
        </p>

        <div class="w-full max-w-4xl grid grid-cols-1 md:grid-cols-3 gap-3 p-4 bg-primary/30 rounded-2xl border border-base-300">
          <div class="font-medium">Project submissions</div>
          <div class="font-medium">Peer voting</div>
          <div class="font-medium">Live leaderboard</div>
        </div>

        <a href="/login" class="btn btn-primary btn-lg mt-1">Sign in to participate</a>
      </div>
    </div>

    <OfficialEventsDisplay events={officialEvents} {loading} />
  </div>
{:else}
  <!-- Authenticated dashboard -->
  <div class="max-w-6xl mx-auto space-y-8" id="home">
    <div id="welcome-back">
      <h1 class="text-3xl font-bold text-base-content mb-2">
        Welcome back, {getAuthenticatedUser().user.first_name}!
      </h1>
    </div>

    <div class="min-h-[60vh] flex items-center justify-center">
      {#if loading}
        <div class="flex flex-col items-center gap-4">
          <span class="loading loading-spinner loading-lg text-primary"></span>
          <p class="text-base-content/70">Loading...</p>
        </div>
      {:else if !currentEvent()}
        <!-- Attending no event yet — pick one -->
        <div class="max-w-md w-full mx-auto">
          <div class="card bg-base-100 shadow-lg">
            <div class="card-body">
              <EventSelector onEventJoined={handleEventJoined} />
            </div>
          </div>
        </div>
      {:else}
        <!-- Attending an event — submit/manage project -->
        <ProjectSubmissionWizard
          flagshipEvents={activeAttendingEvents() as any}
          {projects}
        />
      {/if}
    </div>
  </div>
{/if}
