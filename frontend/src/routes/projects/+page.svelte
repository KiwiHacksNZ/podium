<script lang="ts">
  import type { PageData } from "./$types";
  import ProjectCardWrapper from "$lib/components/ProjectCardWrapper.svelte";

  let { data }: { data: PageData } = $props();
</script>

<div class="mx-auto max-w-7xl space-y-6 px-1 sm:px-0">
  <div class="flex flex-wrap items-end justify-between gap-3">
    <h1 class="text-4xl sm:text-5xl font-black tracking-tight text-base-content">Your Projects</h1>
    <a href="/projects/join" class="btn btn-outline btn-sm">Join a team</a>
  </div>

  {#if data.projects.length > 0}
    <div class="grid grid-cols-1 items-stretch gap-5 md:grid-cols-2 xl:grid-cols-3">
      {#each data.projects as project (project.id)}
        <ProjectCardWrapper {project} events={data.events} />
      {/each}
    </div>
  {:else}
    <div class="py-10 text-center">
      <p class="mb-4 text-base-content/70">
        You haven't submitted any projects yet.
      </p>
      <div class="flex flex-wrap justify-center gap-2">
        <a href="/" class="btn btn-primary">Submit a Project</a>
        <a href="/projects/join" class="btn btn-outline">Join Project</a>
      </div>
    </div>
  {/if}
</div>
