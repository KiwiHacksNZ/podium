<script lang="ts">
  import { onMount } from "svelte";
  import { EventsService } from "$lib/client/sdk.gen";
  import type { EventPrivate, JudgingProgress } from "$lib/client/types.gen";

  let { event }: { event: EventPrivate } = $props();

  let progress = $state<JudgingProgress | null>(null);
  let loadError = $state(false);
  let updatedAt = $state<Date | null>(null);
  let now = $state(Date.now());

  async function load() {
    const { data, error } = await EventsService.getJudgingProgressEventsAdminEventIdJudgingProgressGet({
      path: { event_id: event.id },
      throwOnError: false,
    });
    if (error || !data) {
      loadError = true;
      return;
    }
    loadError = false;
    progress = data;
    updatedAt = new Date();
  }

  // Refresh while judging is open so organisers can watch judges finish
  onMount(() => {
    load();
    const poll = setInterval(() => {
      if (event.judging_open && document.visibilityState === "visible") load();
    }, 15_000);
    const tick = setInterval(() => (now = Date.now()), 30_000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  });

  const total = $derived(progress?.total_projects ?? 0);
  const finished = $derived(progress ? progress.judges.filter((j) => total > 0 && j.scored >= total).length : 0);
  const unjudged = $derived(progress ? progress.projects.filter((p) => p.judges_scored === 0) : []);
  const minCoverage = $derived(progress?.projects.length ? progress.projects[0].judges_scored : 0);

  const relative = new Intl.RelativeTimeFormat("en-NZ", { numeric: "auto" });
  function ago(iso: string | null | undefined): string {
    if (!iso) return "Not started";
    const minutes = Math.round((new Date(iso).getTime() - now) / 60_000);
    if (Math.abs(minutes) < 60) return `Last scored ${relative.format(minutes, "minute")}`;
    return `Last scored ${relative.format(Math.round(minutes / 60), "hour")}`;
  }
</script>

<div class="card bg-base-200">
  <div class="card-body gap-4">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2 class="card-title">Judging progress</h2>
      {#if updatedAt}
        <span class="text-xs text-base-content/50">
          {event.judging_open ? "Updates every 15 seconds" : "Judging is closed"}
        </span>
      {/if}
    </div>

    {#if loadError && !progress}
      <p class="text-sm text-error">Couldn't load judging progress.</p>
    {:else if !progress}
      <span class="loading loading-spinner loading-sm"></span>
    {:else if progress.judges.length === 0}
      <p class="text-sm text-base-content/70">No judges yet. Add judges or hand out judge cards above.</p>
    {:else}
      <p class="text-sm text-base-content/70">
        {finished} of {progress.judges.length} judges finished · {total} projects to score
      </p>

      <ul class="flex flex-col gap-3">
        {#each progress.judges as judge (judge.id)}
          {@const done = total > 0 && judge.scored >= total}
          <li class="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-4">
            <div class="min-w-0 sm:w-56">
              <p class="truncate font-semibold">{judge.name}</p>
              <p class="truncate text-xs text-base-content/60">{judge.email}</p>
            </div>
            <progress
              class="progress grow {done ? 'progress-success' : judge.scored === 0 ? '' : 'progress-info'}"
              value={judge.scored}
              max={Math.max(total, 1)}
            ></progress>
            <div class="flex shrink-0 items-center gap-3 sm:w-56 sm:justify-end">
              <span class="text-sm font-semibold">{judge.scored}/{total}</span>
              {#if done}
                <span class="badge badge-success badge-sm">Done</span>
              {:else}
                <span class="text-xs text-base-content/60">{ago(judge.last_scored_at)}</span>
              {/if}
            </div>
          </li>
        {/each}
      </ul>

      {#if total > 0}
        <div class="rounded-box bg-base-100 p-3 text-sm">
          {#if unjudged.length > 0}
            <p class="font-semibold">
              {unjudged.length}
              {unjudged.length === 1 ? "project hasn't" : "projects haven't"} been scored by anyone yet
            </p>
            <p class="mt-1 text-base-content/70">
              {unjudged.map((p) => (p.team_name ? `${p.name} (${p.team_name})` : p.name)).join(", ")}
            </p>
          {:else}
            <p>
              Every project has been scored by at least {minCoverage}
              {minCoverage === 1 ? "judge" : "judges"}.
            </p>
          {/if}
        </div>
      {/if}
    {/if}
  </div>
</div>
