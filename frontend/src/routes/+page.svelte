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
  <div class="max-w-5xl mx-auto space-y-12">
    <section class="flex flex-col items-center gap-4 pt-4 text-center">
      <img
        src="/assets/kiwihacks/kiwi-logo.png"
        alt=""
        class="w-28 md:w-32 object-contain select-none"
      />
      <img
        src="/assets/kiwihacks/kiwi-text.png"
        alt="KiwiHacks"
        class="w-60 md:w-72 object-contain select-none"
      />
      <h1 class="max-w-xl text-2xl md:text-3xl">
        Where KiwiHacks projects get shown off, judged and voted on.
      </h1>
      <p class="max-w-lg text-base-content/70">
        Submit your team's project, judges score it, and everyone at the event picks their
        favourites.
      </p>
      <div class="mt-2 flex flex-wrap justify-center gap-3">
        <a href="/login" class="btn btn-primary">Sign in</a>
        <a href="/past-events" class="btn btn-outline">See past results</a>
      </div>
    </section>

    <section class="space-y-4">
      <h2 class="text-xl">Events</h2>
      <OfficialEventsDisplay events={officialEvents} {loading} />
    </section>
  </div>
{:else}
  <!-- Authenticated dashboard -->
  <div class="max-w-6xl mx-auto space-y-8" id="home">
    <div id="welcome-back">
      <h1 class="text-3xl font-bold text-base-content mb-2">
        Welcome back, {getAuthenticatedUser().user.first_name}!
      </h1>
    </div>

    <div class="sm:min-h-[60vh] flex items-start sm:items-center justify-center">
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
