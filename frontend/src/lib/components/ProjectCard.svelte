<script lang="ts">
  import type { ProjectPrivate, ProjectPublic } from "$lib/client/types.gen";
  import TeamMembers from "./TeamMembers.svelte";
  import AiDeclaration from "./AiDeclaration.svelte";
  import ProjectImage from "./ProjectImage.svelte";
  interface Props {
    project: ProjectPrivate | ProjectPublic;
    isSelected: boolean;
    toggle: () => void;
    selectable?: boolean;
    rankLabel?: string | null;
    /** Call to action shown on selectable cards that aren't picked yet. */
    pickLabel?: string;
  }
  let loadingImage = $state(true);
  let imageFailed = $state(false);

  let {
    project,
    isSelected,
    toggle,
    selectable = false,
    rankLabel = null,
    pickLabel = "Tap to vote",
  }: Props = $props();

  // $inspect(project);
</script>

<button
  type="button"
  onclick={() => {
    if (selectable) {
      console.debug("card clicked");
      toggle();
    }
  }}
  onkeydown={selectable ? (e) => e.key === "Enter" && toggle() : null}
  aria-pressed={isSelected}
  disabled={!selectable}
  class="block h-full w-full text-left {selectable ? 'cursor-pointer group' : ''}"
>
  <!-- Selection is a ring, not a size change, so the grid never shifts -->
  <div
    class="card card-sm h-full overflow-hidden bg-base-100 transition-shadow duration-150 {isSelected
      ? 'ring-4 ring-info'
      : selectable
        ? 'group-hover:ring-2 group-hover:ring-info/60'
        : ''}"
  >
    <figure class="w-full relative bg-base-200">
      {#if project.image_url && !imageFailed}
        <img
          src={project.image_url}
          alt="Project"
          class="aspect-[3/2] w-full object-cover"
          loading="lazy"
          onload={() => (loadingImage = false)}
          onerror={() => {
            loadingImage = false;
            imageFailed = true;
          }}
          style="opacity: {loadingImage ? 0 : 1}; transition: opacity 0.2s;"
        />
        {#if loadingImage}
          <div class="skeleton absolute inset-0"></div>
        {/if}
      {:else}
        <ProjectImage {project} class="aspect-[3/2] w-full" />
      {/if}
      {#if rankLabel}
        <div class="badge badge-info badge-lg absolute top-2 left-2 z-10">
          {rankLabel}
        </div>
      {/if}
    </figure>
    <div class="card-body grow">
      <h2 class="card-title break-words overflow-x-auto">
        {project.name}
      </h2>
      <TeamMembers {project} class="-mt-1" />
      <div>
        <AiDeclaration
          declaration={project.ai_declaration}
          underLimit={project.ai_under_limit}
          compact
        />
      </div>
      <div class="divider my-0"></div>
      <p class="break-words text-sm">{project.description}</p>
      <div class="card-actions justify-center mt-2">
        <!-- stopPropagation: opening a link must not also toggle the vote -->
        <a
          href={project.repo}
          target="_blank"
          rel="noopener"
          class="btn btn-secondary btn-sm"
          onclick={(e) => e.stopPropagation()}
        >
          Repo
        </a>
        {#if project.demo}
          <a
            href={project.demo}
            target="_blank"
            rel="noopener"
            class="btn btn-primary btn-sm"
            onclick={(e) => e.stopPropagation()}
          >
            Demo
          </a>
        {/if}
      </div>
    </div>
    {#if selectable}
      <div
        class="border-t border-base-content/10 px-4 py-3 text-center font-extrabold text-sm {isSelected
          ? 'bg-info text-info-content'
          : 'bg-base-200 group-hover:bg-info group-hover:text-info-content'}"
      >
        {isSelected ? `✓ ${rankLabel ?? "Picked"} · tap to remove` : pickLabel}
      </div>
    {/if}
  </div>
</button>
