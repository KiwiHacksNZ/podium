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

  // A ballot is exactly 3 picks (MAX_RANK on the backend)
  const ordinals = ["1st", "2nd", "3rd"];
  function ordinal(index: number) {
    return ordinals[index];
  }

  // Theme tokens so the ballot re-skins with the rest of the app: the top pick
  // is the loudest colour available, then info, then primary.
  const rankStyles = [
    "bg-warning text-warning-content",
    "bg-info text-info-content",
    "bg-primary text-primary-content",
  ];
  function rankStyle(index: number) {
    return rankStyles[index];
  }
  // Ballot order is the rank: 1st choice is worth 3 points, 2nd 2, 3rd 1.
  function points(index: number) {
    return 3 - index;
  }

  function rankLabelFor(projectId: string): string | null {
    const index = selectedProjects.indexOf(projectId);
    return index === -1 ? null : `${ordinal(index)} choice`;
  }

  const picksLeft = $derived(data.toSelect - selectedProjects.length);
  const pickLabel = $derived(
    picksLeft > 0
      ? `Tap to vote ${ordinal(selectedProjects.length)}`
      : `Tap to swap in as ${ordinal(data.toSelect - 1)}`,
  );

  const selectedInOrder = $derived(
    selectedProjects
      .map((id) => data.projects.find((p) => p.id === id))
      .filter((p): p is (typeof data.projects)[number] => p !== undefined),
  );

  function nameOf(projectId: string): string {
    return data.projects.find((p) => p.id === projectId)?.name ?? "that project";
  }

  function toggleProjectSelection(projectId: string) {
    if (selectedProjects.includes(projectId)) {
      selectedProjects = selectedProjects.filter((id) => id !== projectId);
    } else if (selectedProjects.length < data.toSelect) {
      selectedProjects = [...selectedProjects, projectId];
    } else if (data.toSelect > 0) {
      // A full ballot swaps out the last pick rather than refusing the tap
      const last = data.toSelect - 1;
      const dropped = selectedProjects[last];
      selectedProjects = [...selectedProjects.slice(0, last), projectId];
      toast.info(`${nameOf(projectId)} is now your ${ordinal(last)} choice, replacing ${nameOf(dropped)}.`);
    }
  }

  /** Move a pick up (-1) or down (+1) the ballot. */
  function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= selectedProjects.length) return;
    const next = [...selectedProjects];
    [next[index], next[target]] = [next[target], next[index]];
    selectedProjects = next;
  }

  // One ballot per person, so show exactly what's being cast before it goes
  let confirmDialog: HTMLDialogElement | undefined = $state();

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
    confirmDialog?.close();
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
        class="inline-flex items-center rounded-full bg-success-content text-success px-3 py-1 text-sm font-extrabold"
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
        class="inline-flex items-center rounded-full bg-info-content text-info px-3 py-1 text-sm font-extrabold"
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
        worth 3 points, 2nd is 2, 3rd is 1. Reorder or remove picks in your
        ballot below.
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
          {pickLabel}
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
                class="rounded-full bg-black/15 px-3 py-1 text-xs font-extrabold"
              >
                {ordinal(index)}
              </span>
              <span class="font-bold break-words grow">
                {project.name}
                {#if project.team_name}
                  <span class="font-normal opacity-80">· {project.team_name}</span>
                {/if}
              </span>
              <span class="text-sm font-semibold whitespace-nowrap">
                {points(index)}
                {points(index) === 1 ? "pt" : "pts"}
              </span>
              <span class="join">
                <button
                  type="button"
                  class="btn btn-xs btn-ghost join-item"
                  aria-label={`Move ${project.name} up`}
                  disabled={index === 0}
                  onclick={() => move(index, -1)}
                >
                  &uarr;
                </button>
                <button
                  type="button"
                  class="btn btn-xs btn-ghost join-item"
                  aria-label={`Move ${project.name} down`}
                  disabled={index === selectedInOrder.length - 1}
                  onclick={() => move(index, 1)}
                >
                  &darr;
                </button>
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
    <!-- Sticky so the pick count and submit stay in reach while scrolling cards. -->
    <div
      class="sticky bottom-0 z-20 -mx-4 sm:mx-0 bg-base-100/95 backdrop-blur px-4 py-3 border-t border-base-300 flex items-center gap-3"
    >
      <span class="font-bold text-sm grow">
        {#if picksLeft > 0}
          {picksLeft} pick{picksLeft === 1 ? "" : "s"} left
        {:else}
          Ballot ready
        {/if}
      </span>
      <button
        class="btn btn-primary"
        disabled={selectedProjects.length === 0}
        onclick={() => confirmDialog?.showModal()}>Submit vote</button
      >
    </div>
  </div>

  <dialog class="modal modal-bottom sm:modal-middle" bind:this={confirmDialog}>
    <div class="modal-box">
      <h2 class="text-lg font-bold">Cast this ballot?</h2>
      <ol class="mt-4 flex flex-col gap-2">
        {#each selectedInOrder as project, index (project.id)}
          <li class="flex items-baseline gap-3">
            <span class="w-10 shrink-0 text-sm font-extrabold">{ordinal(index)}</span>
            <span class="font-semibold break-words grow">
              {project.name}
              {#if project.team_name}
                <span class="font-normal text-base-content/70">· {project.team_name}</span>
              {/if}
            </span>
            <span class="text-sm text-base-content/70 whitespace-nowrap">
              {points(index)} {points(index) === 1 ? "pt" : "pts"}
            </span>
          </li>
        {/each}
      </ol>
      {#if picksLeft > 0}
        <p class="mt-4 text-sm text-base-content/70">
          You still have {picksLeft} pick{picksLeft === 1 ? "" : "s"} left. You
          can come back and add {picksLeft === 1 ? "it" : "them"} later.
        </p>
      {/if}
      <p class="mt-4 text-sm text-base-content/70">
        Picks can't be changed or reordered once they're cast.
      </p>
      <div class="modal-action">
        <button type="button" class="btn btn-ghost" onclick={() => confirmDialog?.close()}>
          Keep editing
        </button>
        <button type="button" class="btn btn-primary" use:asyncClick={submitVote}>
          Cast ballot
        </button>
      </div>
    </div>
    <form method="dialog" class="modal-backdrop">
      <button>close</button>
    </form>
  </dialog>
{/if}
