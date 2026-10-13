<script lang="ts">
  import { teamLabel, voteBreakdown, withHttpsIfMissing } from "$lib/misc";
  import type { PageData } from "./$types";

  let { data }: { data: PageData } = $props();
  const podium = $derived(data.projects.slice(0, 3));
  const rest = $derived(data.projects.slice(3));

  const places = ["1st", "2nd", "3rd"];
  // 1st stands out; 2nd and 3rd stay calmer
  const placeStyles = [
    "border-warning/60 ring-2 ring-warning/40",
    "border-base-content/20",
    "border-base-content/20",
  ];
  const placeBadges = ["badge-warning", "badge-neutral", "badge-neutral"];
</script>

<div class="mx-auto max-w-5xl px-4 pb-10">
  <div class="mb-6 text-center">
    <h1 class="text-3xl font-black tracking-tight">Leaderboard</h1>
    <p class="mt-1 text-sm text-base-content/70">
      Ranked by points: 1st choice = 3, 2nd = 2, 3rd = 1.
    </p>
  </div>

  {#if data.projects.length === 0}
    <p class="py-12 text-center text-base-content/60">No votes yet.</p>
  {:else}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {#each podium as project, i (project.id)}
        <article data-testid="leaderboard-entry" class="card overflow-hidden border bg-base-100 shadow-sm {placeStyles[i]} {i === 0 ? 'sm:order-2' : i === 1 ? 'sm:order-1 sm:mt-6' : 'sm:order-3 sm:mt-10'}">
          <figure class="relative bg-base-200">
            {#if project.image_url}
              <img src={project.image_url} alt={project.name} class="aspect-[3/2] w-full object-cover" loading="lazy" />
            {:else}
              <div class="flex aspect-[3/2] w-full items-center justify-center text-sm text-base-content/45">No image</div>
            {/if}
            <span class="badge badge-lg absolute left-3 top-3 font-black {placeBadges[i]}">{places[i]}</span>
          </figure>
          <div class="card-body gap-2 p-4">
            <h2 data-testid="entry-name" class="card-title break-words text-lg leading-tight">{project.name}</h2>
            {#if project.team_name}
              <p class="-mt-1 text-sm font-semibold text-base-content/70">{teamLabel(project.team_name)}</p>
            {/if}
            <p class="text-2xl font-black"><span data-testid="entry-points">{project.points}</span> <span class="text-sm font-semibold text-base-content/60">pts</span></p>
            <p class="text-xs text-base-content/60">{voteBreakdown(project.rank_counts)}</p>
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

    {#if rest.length > 0}
      <ol class="mt-8 flex flex-col gap-2">
        {#each rest as project, i (project.id)}
          <li data-testid="leaderboard-entry" class="card flex-row items-center gap-4 bg-base-100 px-4 py-3">
            <span class="w-8 shrink-0 text-center text-lg font-black text-base-content/60">{i + 4}</span>
            {#if project.image_url}
              <img src={project.image_url} alt="" class="hidden h-12 w-18 shrink-0 rounded-lg object-cover sm:block" loading="lazy" />
            {/if}
            <div class="min-w-0 grow">
              <p data-testid="entry-name" class="truncate font-bold">{project.name}</p>
              <p class="truncate text-xs text-base-content/60">
                {[project.team_name ? teamLabel(project.team_name) : "", voteBreakdown(project.rank_counts)]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            <span class="shrink-0 text-lg font-black"><span data-testid="entry-points">{project.points}</span> <span class="text-xs font-semibold text-base-content/60">pts</span></span>
          </li>
        {/each}
      </ol>
    {/if}
  {/if}
</div>
