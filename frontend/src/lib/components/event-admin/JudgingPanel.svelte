<script lang="ts">
  import { onMount } from "svelte";
  import { client } from "$lib/client/sdk.gen";
  import type { EventPrivate } from "$lib/client/types.gen";
  import ConfirmationModal from "$lib/components/ConfirmationModal.svelte";
  import { handleError } from "$lib/misc";
  import { toast } from "svelte-sonner";

  // Judging endpoints aren't in the generated SDK yet, so these mirror the API.
  type JudgingResult = {
    project_id: string;
    name: string;
    judge_score: number;
    judge_count: number;
    is_finalist: boolean;
    averages: {
      originality: number;
      technicality: number;
      theme: number;
      usability: number;
    };
  };

  type Finalist = {
    project_id: string;
    name: string;
    judge_score: number;
    judge_count: number;
  };

  interface Props {
    event: EventPrivate;
  }

  let { event }: Props = $props();

  let results = $state<JudgingResult[]>([]);
  let loading = $state(true);
  let locking = $state(false);
  let justLocked = $state<Finalist[] | null>(null);
  let lockConfirmation: ConfirmationModal = $state() as ConfirmationModal;

  const scoredCount = $derived(results.filter((r) => r.judge_count > 0).length);
  const finalists = $derived(results.filter((r) => r.is_finalist));

  async function loadResults() {
    loading = true;
    const { data, error } = await client.get<JudgingResult[], unknown>({
      url: `/judging/${event.id}/results`,
      throwOnError: false,
    });
    if (error) handleError(error);
    else results = data ?? [];
    loading = false;
  }

  async function lockFinalists() {
    locking = true;
    const { data, error } = await client.post<Finalist[], unknown>({
      url: `/events/admin/${event.id}/finalists`,
      throwOnError: false,
    });
    if (error) {
      handleError(error);
    } else {
      justLocked = data ?? [];
      toast.success(`Locked in ${justLocked.length} finalists`);
      await loadResults();
    }
    locking = false;
  }

  function fmt(n: number | null | undefined) {
    return typeof n === "number" ? n.toFixed(1) : "—";
  }

  onMount(loadResults);
</script>

<div class="card bg-base-200">
  <div class="card-body">
    <h2 class="card-title">Judging ({results.length})</h2>


    {#if loading}
      <span class="loading loading-spinner loading-md"></span>
    {:else if results.length === 0}
      <p class="text-base-content/70">No projects to judge yet.</p>
    {:else}
      <p class="text-sm text-base-content/70">
        Mean judge score across Originality, Technicality, Theme and Usability
        (each scored 1-10, so 40 is a perfect score).
        {#if finalists.length > 0}
          Finalists are locked in — attendees rank only those during voting.
        {/if}
      </p>

      {#if justLocked}
        <div class="alert alert-success">
          <span>
            Advanced to voting:
            {justLocked.map((f) => f.name).join(", ") || "no projects"}
          </span>
        </div>
      {/if}

      <div class="overflow-x-auto">
        <table class="table table-zebra w-full">
          <thead>
            <tr>
              <th>#</th>
              <th>Project</th>
              <th>Mean score</th>
              <th>Judges</th>
              <th>Originality</th>
              <th>Technicality</th>
              <th>Theme</th>
              <th>Usability</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each results as result, index (result.project_id)}
              <tr>
                <td>{index + 1}</td>
                <td>
                  <div class="font-medium">{result.name}</div>
                  <div class="text-xs text-base-content/70 font-mono">
                    {result.project_id}
                  </div>
                </td>
                <td class="font-medium">{fmt(result.judge_score)} / 40</td>
                <td>{result.judge_count}</td>
                <td>{fmt(result.averages?.originality)}</td>
                <td>{fmt(result.averages?.technicality)}</td>
                <td>{fmt(result.averages?.theme)}</td>
                <td>{fmt(result.averages?.usability)}</td>
                <td>
                  {#if result.is_finalist}
                    <span class="badge badge-primary badge-sm">Finalist</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="flex flex-wrap items-center gap-3 mt-2">
        <button
          class="btn btn-warning btn-sm"
          disabled={locking || scoredCount === 0}
          onclick={() => lockConfirmation.open()}
        >
          {#if locking}
            Locking…
          {:else if finalists.length > 0}
            Recompute finalists
          {:else}
            Lock in top 5 finalists
          {/if}
        </button>
        <span class="text-sm text-base-content/70">
          {#if scoredCount === 0}
            No judge scores yet.
          {:else if finalists.length > 0}
            {scoredCount} of {results.length} projects scored. Recomputing
            replaces the current finalists — only possible until the first vote
            is cast.
          {:else}
            {scoredCount} of {results.length} projects have been scored.
          {/if}
        </span>
      </div>
    {/if}
  </div>
</div>

<ConfirmationModal
  bind:this={lockConfirmation}
  title="Lock in Finalists"
  message="This makes the top 5 projects by mean judge score the finalists, replacing any current set. Attendees will only be able to rank those projects. You can recompute while judges are still scoring, but not once the first vote is cast."
  confirmText="Lock in finalists"
  cancelText="Cancel"
  confirmClass="btn-error"
  onConfirm={lockFinalists}
  onCancel={() => {}}
/>
