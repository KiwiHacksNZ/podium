<script lang="ts">
  import { leaderboardPlaces, placeLabel, withHttpsIfMissing } from "$lib/misc";
  import TeamMembers from "$lib/components/TeamMembers.svelte";
  import ProjectImage from "$lib/components/ProjectImage.svelte";
  import VoteMix from "$lib/components/VoteMix.svelte";
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();

  // Once finalists are locked in, only they were on the ballot. Everyone else
  // gets a calmer "Also submitted" list instead of a column of zeroes.
  const hasFinalists = $derived(data.projects.some((p) => p.is_finalist));
  const ranked = $derived(hasFinalists ? data.projects.filter((p) => p.is_finalist) : data.projects);
  const others = $derived(
    hasFinalists
      ? data.projects.filter((p) => !p.is_finalist).sort((a, b) => a.name.localeCompare(b.name))
      : [],
  );
  const places = $derived(leaderboardPlaces(ranked));
  const podium = $derived(ranked.slice(0, 3));
  const rest = $derived(ranked.slice(3));
  const judgesPicks = $derived(data.projects.filter((p) => p.judges_pick));

  function placeText(i: number): string {
    const { place, tied } = places[i];
    return `${tied ? "=" : ""}${placeLabel(place)}`;
  }

  // Styled by actual place, so a tie for 1st looks like one
  function isFirst(i: number): boolean {
    return places[i].place === 1;
  }
</script>

{#snippet judgesPickBadge()}
  <span class="badge badge-sm badge-outline border-accent/60 text-accent">Judges' pick</span>
{/snippet}

<div class="mx-auto max-w-5xl px-4 pb-10">
  <div class="mb-6 text-center">
    <h1 class="text-3xl font-black tracking-tight">Leaderboard</h1>
    <p class="mt-1 text-sm text-base-content/70">
      Ranked by points: 1st choice = 3, 2nd = 2, 3rd = 1.
    </p>
    <p class="text-sm text-base-content/55">
      Level on points? Most 1st choices goes ahead, then 2nd, then 3rd.
    </p>
  </div>

  {#if data.projects.length === 0}
    <p class="py-12 text-center text-base-content/60">No votes yet.</p>
  {:else}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {#each podium as project, i (project.id)}
        <article
          data-testid="leaderboard-entry"
          class="card overflow-hidden border bg-base-100 shadow-sm {isFirst(i)
            ? 'border-warning/60 ring-2 ring-warning/40'
            : 'border-base-content/20'} {i === 0 ? 'sm:order-2' : i === 1 ? 'sm:order-1 sm:mt-6' : 'sm:order-3 sm:mt-10'}"
        >
          <figure class="relative bg-base-200">
            <ProjectImage {project} alt={project.name} class="aspect-[3/2] w-full" />
            <span class="badge badge-lg absolute left-3 top-3 font-black {isFirst(i) ? 'badge-warning' : 'badge-neutral'}">
              {placeText(i)}
            </span>
          </figure>
          <div class="card-body gap-2 p-4">
            <h2 data-testid="entry-name" class="card-title break-words text-lg leading-tight">{project.name}</h2>
            <TeamMembers {project} class="-mt-1" />
            {#if project.judges_pick}
              <div>{@render judgesPickBadge()}</div>
            {/if}
            <p class="text-2xl font-black">
              <span data-testid="entry-points">{project.points}</span>
              <span class="text-sm font-semibold text-base-content/60">pts</span>
            </p>
            <VoteMix rankCounts={project.rank_counts} />
            {#if places[i].tiebreak}
              <p class="text-xs text-base-content/60">{places[i].tiebreak}</p>
            {/if}
            <div class="card-actions mt-1">
              {#if project.repo}
                <a class="btn btn-secondary btn-xs" href={withHttpsIfMissing(project.repo)} target="_blank" rel="noopener noreferrer">Repo</a>
              {/if}
              {#if project.demo}
                <a class="btn btn-primary btn-xs" href={withHttpsIfMissing(project.demo)} target="_blank" rel="noopener noreferrer">Demo</a>
              {/if}
            </div>
          </div>
        </article>
      {/each}
    </div>

    {#if judgesPicks.length > 0}
      <section class="mx-auto mt-8 max-w-3xl rounded-box border border-accent/30 bg-base-100 p-4">
        <h2 class="text-sm font-semibold text-accent">Judges' pick</h2>
        <p class="text-xs text-base-content/60">The judges' highest-scored {judgesPicks.length === 1 ? "project" : "projects"}, alongside the popular vote.</p>
        <ul class="mt-3 flex flex-col gap-3">
          {#each judgesPicks as project (project.id)}
            <li class="flex items-center gap-3">
              <ProjectImage {project} class="h-12 w-18 shrink-0 rounded-lg" />
              <div class="min-w-0">
                <p class="truncate font-bold">{project.name}</p>
                <TeamMembers {project} />
              </div>
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if rest.length > 0}
      <ol class="mx-auto mt-8 flex max-w-3xl flex-col gap-2">
        {#each rest as project, j (project.id)}
          {@const i = j + 3}
          <li data-testid="leaderboard-entry" class="card flex-row items-center gap-4 bg-base-100 px-4 py-3">
            <span class="w-10 shrink-0 text-center text-lg font-black text-base-content/60">{places[i].tied ? "=" : ""}{places[i].place}</span>
            <ProjectImage {project} class="hidden h-12 w-18 shrink-0 rounded-lg sm:flex" />
            <div class="min-w-0 grow">
              <p class="flex flex-wrap items-center gap-2">
                <span data-testid="entry-name" class="truncate font-bold">{project.name}</span>
                {#if project.judges_pick}
                  {@render judgesPickBadge()}
                {/if}
              </p>
              <TeamMembers {project} />
              <VoteMix rankCounts={project.rank_counts} class="mt-1 max-w-xs" />
              {#if places[i].tiebreak}
                <p class="text-xs text-base-content/60">{places[i].tiebreak}</p>
              {/if}
            </div>
            <span class="shrink-0 text-lg font-black">
              <span data-testid="entry-points">{project.points}</span>
              <span class="text-xs font-semibold text-base-content/60">pts</span>
            </span>
          </li>
        {/each}
      </ol>
    {/if}

    {#if others.length > 0}
      <section class="mx-auto mt-10 max-w-3xl">
        <h2 class="text-lg font-semibold">Also submitted</h2>
        <p class="text-sm text-base-content/60">These projects weren't finalists, so they weren't on the ballot.</p>
        <ul class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {#each others as project (project.id)}
            <li class="flex items-center gap-3 rounded-box bg-base-100/60 px-3 py-2">
              <ProjectImage {project} class="h-10 w-14 shrink-0 rounded-md" />
              <div class="min-w-0">
                <p class="flex flex-wrap items-center gap-2">
                  <span class="truncate font-semibold">{project.name}</span>
                  {#if project.judges_pick}
                    {@render judgesPickBadge()}
                  {/if}
                </p>
                <TeamMembers {project} />
              </div>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</div>
