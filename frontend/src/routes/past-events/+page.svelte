<script lang="ts">
  import { onMount } from "svelte";
  import { EventsService } from "$lib/client/sdk.gen";
  import type { PastEvent, ProjectPublic } from "$lib/client";

  type PastResult = { event: PastEvent; podium: ProjectPublic[] };

  let pastEvents = $state<PastResult[]>([]);
  let loading = $state(true);
  let loadError = $state(false);

  const places = ["1st", "2nd", "3rd"];

  // The API returns events already sorted by series; group consecutive runs
  const bySeries = $derived(
    pastEvents.reduce<{ series: string; name: string; events: PastResult[] }[]>((groups, r) => {
      const last = groups.at(-1);
      if (last && last.series === r.event.series) last.events.push(r);
      else groups.push({ series: r.event.series, name: r.event.series_name, events: [r] });
      return groups;
    }, []),
  );

  onMount(async () => {
    const res = await EventsService.listPastEventsEventsPastGet({
      throwOnError: false,
    });
    if (res.error || !res.data) {
      loadError = true;
      loading = false;
      return;
    }
    // The leaderboard is only public once an event is closed
    pastEvents = await Promise.all(
      res.data.map(async (event) => {
        if (event.phase !== "closed") return { event, podium: [] };
        const lb = await EventsService.getEventProjectsEventsEventIdProjectsGet({
          path: { event_id: event.id },
          query: { leaderboard: true },
          throwOnError: false,
        });
        return { event, podium: (lb.data ?? []).slice(0, 3) };
      }),
    );
    loading = false;
  });
</script>

<div class="max-w-4xl mx-auto space-y-6 px-4">
  <div class="text-center py-4">
    <h1 class="text-3xl font-bold text-base-content mb-2">Past Events</h1>
    <p class="text-base-content/70">Results from events that have wrapped up.</p>
  </div>

  {#if loading}
    <div class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else if loadError}
    <div class="alert alert-error">
      <span>Failed to load past events. Please refresh the page.</span>
    </div>
  {:else}
    {#each bySeries as group (group.series)}
      <h2 class="divider text-base-content/60 font-semibold">
        {group.name || "Other events"}
      </h2>
      {#each group.events as { event, podium } (event.id)}
        <div class="card bg-base-100 border border-base-300 shadow-sm">
          <div class="card-body gap-3">
            <div class="flex items-start justify-between gap-2">
              <h2 class="card-title">
                <a href={`/events/${event.slug}`} class="link link-hover">{event.name}</a>
              </h2>
              {#if event.phase === "closed"}
                <a
                  href={`/events/${event.slug}/leaderboard`}
                  class="btn btn-primary btn-sm shrink-0"
                >
                  Full leaderboard →
                </a>
              {/if}
            </div>
            {#if event.description}
              <p class="text-base-content/60 text-sm">{event.description}</p>
            {/if}
            {#if podium.length > 0}
              <ol class="space-y-1">
                {#each podium as project, i (project.id)}
                  <li class="flex items-center gap-2">
                    <span class="badge badge-sm w-10 shrink-0 {i === 0 ? 'badge-warning' : 'badge-ghost'}">{places[i]}</span>
                    <span class="font-medium">{project.name}</span>
                    {#if project.team_name}
                      <span class="text-sm text-base-content/60">· {project.team_name}</span>
                    {/if}
                    <span class="text-sm text-base-content/60">{project.points} pts</span>
                  </li>
                {/each}
              </ol>
            {:else}
              <p class="text-sm text-base-content/50">Results aren't published yet.</p>
            {/if}
          </div>
        </div>
      {/each}
    {:else}
      <p class="text-center text-base-content/50 py-8">No past events yet.</p>
    {/each}
  {/if}
</div>
