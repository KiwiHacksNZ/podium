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
  <div class="p-4 bg-success text-center rounded-xl max-w-2xl mx-auto">
    <p class="text-success-content">
      You have already voted for this event. You can only vote once.
    </p>
  </div>
{:else}
  <div class="p-4 bg-warning text-center rounded-xl max-w-2xl mx-auto">
    <p class="text-warning-content text-sm">
      {#if data.finalistCount > 0}
        These are the {data.finalistCount} finalists chosen by the judges. Rank
        them in order: click projects in the order you like them, from favorite
        first. Your 1st choice is worth 3 points, 2nd choice 2 points and 3rd
        choice 1 point.
      {:else}
        Rank projects in order: click projects in the order you like them, from
        favorite first. Your 1st choice is worth 3 points, 2nd choice 2 points
        and 3rd choice 1 point.
      {/if}
      You can pick {data.toSelect - selectedProjects.length} more. Click a
      selected project again to remove it and reorder your ballot.
    </p>
  </div>
  <div class="container mx-auto p-6">
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

    <div class="card bg-base-200 mt-6">
      <div class="card-body">
        <h2 class="card-title text-base">Your ballot</h2>
        {#if selectedProjects.length === 0}
          <p class="text-base-content/70 text-sm">
            Nothing picked yet. Click a project to make it your 1st choice.
          </p>
        {:else}
          <ol class="list-decimal list-inside space-y-1">
            {#each selectedInOrder as project, index (project.id)}
              <li class="text-sm">
                <span class="badge badge-info badge-sm mr-2"
                  >{ordinal(index)} choice</span
                >
                <span class="font-medium">{project.name}</span>
                <span class="text-base-content/70">
                  — {points(index)}
                  {points(index) === 1 ? "point" : "points"}</span
                >
                <button
                  type="button"
                  class="btn btn-ghost btn-xs ml-2"
                  onclick={() => toggleProjectSelection(project.id)}
                >
                  Remove
                </button>
              </li>
            {/each}
          </ol>
        {/if}
      </div>
    </div>

    <!-- Not disabling if user has already voted since this is hidden then anyway. Also not disabling if projects is under toSelect since people can come back. -->
    <button class="btn-block btn btn-warning mt-4" use:asyncClick={submitVote}
      >Submit Vote</button
    >
  </div>
{/if}
