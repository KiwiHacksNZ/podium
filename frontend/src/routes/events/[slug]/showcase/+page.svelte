<script lang="ts">
  import type { PageData } from "./$types";
  import { teamLabel } from "$lib/misc";
  import AiDeclaration from "$lib/components/AiDeclaration.svelte";

  let { data }: { data: PageData } = $props();
  let projects = $derived(data.projects);
</script>

<div class="mx-auto max-w-6xl px-4 py-6">
  <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 class="text-3xl font-black tracking-tight text-base-content">Project Showcase</h1>
      <p class="text-sm text-base-content/65">{projects.length} projects</p>
    </div>
  </div>

  {#if projects.length === 0}
    <div class="py-12 text-center text-base-content/60">No projects yet.</div>
  {:else}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each projects as project, index}
        <article class="card bg-base-100 shadow-sm border border-base-content/10">
          <figure class="bg-base-200">
            {#if project.image_url}
              <img
                src={project.image_url}
                alt={project.name}
                class="aspect-[3/2] w-full object-cover"
                loading="lazy"
              />
            {:else}
              <div class="flex aspect-[3/2] w-full items-center justify-center text-base-content/45">
                No image
              </div>
            {/if}
          </figure>
          <div class="card-body gap-3">
            <div class="flex items-start justify-between gap-3">
              <h2 class="card-title min-w-0 break-words text-lg">{project.name}</h2>
              {#if project.points > 0}
                <span class="badge badge-info shrink-0">#{index + 1}</span>
              {/if}
            </div>
            {#if project.team_name}
              <p class="-mt-2 text-sm font-semibold text-base-content/70">{teamLabel(project.team_name)}</p>
            {/if}
            <div>
              <AiDeclaration
                declaration={project.ai_declaration}
                underLimit={project.ai_under_limit}
              />
            </div>
            <p class="line-clamp-3 text-sm text-base-content/75">
              {project.description || "No description yet."}
            </p>
            <p class="text-xs text-base-content/60">
              {[project.owner_display_name, ...(project.collaborator_display_names ?? [])].filter(Boolean).join(", ")}
            </p>
            <div class="card-actions mt-1">
              {#if project.repo}
                <a class="btn btn-sm btn-info" href={project.repo} target="_blank" rel="noopener noreferrer">Repo</a>
              {/if}
              {#if project.demo}
                <a class="btn btn-sm btn-success" href={project.demo} target="_blank" rel="noopener noreferrer">Demo</a>
              {/if}
              {#if project.points > 0}
                <span class="badge badge-outline self-center">{project.points} pts</span>
              {/if}
            </div>
          </div>
        </article>
      {/each}
    </div>
  {/if}
</div>
