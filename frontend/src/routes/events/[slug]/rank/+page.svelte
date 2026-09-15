<svelte:options runes />

<script lang="ts">
  import { toast } from "svelte-sonner";
  import { EventsService } from "$lib/client/sdk.gen";
  import ProjectCard from "$lib/components/ProjectCard.svelte";
  import { customInvalidateAll, handleError } from "$lib/misc";
  import { asyncClick } from "$lib/actions/asyncClick";
  import { goto } from "$app/navigation";

  const { data } = $props();
  let selectedProjects: string[] = $state([]);

  const ordinals = ["1st", "2nd", "3rd"];
  function ordinal(index: number) {
    return ordinals[index] ?? `${index + 1}th`;
  }

  // Theme tokens so the ballot re-skins with the rest of the app: the top pick
  // is the loudest colour available, then info, then primary.
  const rankStyles = [
    "bg-warning text-warning-content",
    "bg-info text-info-content",
    "bg-primary text-primary-content",
  ];
  function rankStyle(index: number) {
    return rankStyles[index] ?? "bg-base-300 text-base-content";
  }
  // Ballot order is the rank: 1st choice is worth 3 points, 2nd 2, 3rd 1.
  function points(index: number) {
    return Math.max(1, 3 - index);
  }

  function rankLabelFor(projectId: string): string | null {
    const index = selectedProjects.indexOf(projectId);
    return index === -1 ? null : `${ordinal(index)} choice`;
  }

  const selectedInOrder = $derived(
    selectedProjects
      .map((id) => data.projects.find((p) => p.id === id))
      .filter((p): p is (typeof data.projects)[number] => p !== undefined),
  );

  function toggleProjectSelection(projectId: string) {
    if (selectedProjects.includes(projectId)) {
      // Deselecting is also how you reorder: drop a pick and re-add it later to
      // move it down the ballot.
      selectedProjects = selectedProjects.filter((id) => id !== projectId);
    } else {
      if (selectedProjects.length < data.toSelect) {
        selectedProjects = [...selectedProjects, projectId];
      }
    }
  }

  async function submitVote() {
    const { error: err } = await EventsService.voteEventsVotePost({
      body: {
        event: data.event.id,
        projects: selectedProjects,
      },
      throwOnError: false,
    });
    if (err) {
      handleError(err);
      return;
    }
    toast.success("Vote submitted successfully");
    selectedProjects = [];
    await customInvalidateAll();
    // Navigate back to the event page
    await goto(`/events/${data.event.slug}`);
  }
</script>

<!-- Basic information about voting -->
{#if data.alreadyVoted}
  <div class="container mx-auto max-w-3xl p-4 sm:p-6">
    <section class="rounded-box bg-success text-success-content p-8 text-center">
      <span
        class="inline-flex items-center rounded-full bg-success-content text-success px-3 py-1 text-sm font-extrabold uppercase tracking-wide"
      >
        Vote counted
      </span>
      <h1 class="mt-4 text-3xl sm:text-4xl font-extrabold">Thanks!</h1>
      <p class="mt-3 opacity-90">
        Your ballot is in. Everyone gets one vote, so that is you done.
      </p>
    </section>
  </div>
{:else}
  <div class="container mx-auto max-w-5xl p-4 sm:p-6 flex flex-col gap-6">
    <section class="rounded-box bg-info text-info-content p-5 sm:p-6">
      <span
        class="inline-flex items-center rounded-full bg-info-content text-info px-3 py-1 text-sm font-extrabold uppercase tracking-wide"
      >
        How to vote
      </span>
      <h1 class="mt-4 text-2xl sm:text-3xl font-extrabold">
        {#if data.finalistCount > 0}
          Rank the {data.finalistCount} finalists
        {:else}
          Rank your favourites
        {/if}
      </h1>
      <p class="mt-2 opacity-90 text-sm">
        Tap projects in the order you like them, favourite first. 1st choice is
        worth 3 points, 2nd is 2, 3rd is 1. Tap a pick again to remove it and
        reorder.
      </p>
      <p class="mt-3 font-bold">
        {data.toSelect - selectedProjects.length} pick{data.toSelect -
          selectedProjects.length ===
        1
          ? ""
          : "s"} left
      </p>
    </section>
    <div
      class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6"
    >
      {#each data.projects as project}
        <ProjectCard
          {project}
          isSelected={selectedProjects.includes(project.id)}
          toggle={() => toggleProjectSelection(project.id)}
          selectable={true}
          rankLabel={rankLabelFor(project.id)}
        />
      {/each}
    </div>

    <section class="rounded-box bg-base-200 p-5 sm:p-6">
      <h2 class="text-xl font-extrabold">Your ballot</h2>
      {#if selectedProjects.length === 0}
        <p class="mt-2 text-base-content/70 text-sm">
          Nothing picked yet. Tap a project to make it your 1st choice.
        </p>
      {:else}
        <ul class="mt-4 flex flex-col gap-3">
          {#each selectedInOrder as project, index (project.id)}
            <li
              class="rounded-box px-4 py-3 flex items-center gap-3 {rankStyle(
                index,
              )}"
            >
              <span
                class="rounded-full bg-black/15 px-3 py-1 text-xs font-extrabold uppercase tracking-wide"
              >
                {ordinal(index)}
              </span>
              <span class="font-bold break-words grow">{project.name}</span>
              <span class="text-sm font-semibold whitespace-nowrap">
                {points(index)}
                {points(index) === 1 ? "pt" : "pts"}
              </span>
              <button
                type="button"
                class="btn btn-xs btn-ghost"
                aria-label={`Remove ${project.name} from your ballot`}
                onclick={() => toggleProjectSelection(project.id)}
              >
                Remove
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <!-- Not disabling if user has already voted since this is hidden then anyway. Also not disabling if projects is under toSelect since people can come back. -->
    <button class="btn-block btn btn-primary" use:asyncClick={submitVote}
      >Submit vote</button
    >
  </div>
{/if}
