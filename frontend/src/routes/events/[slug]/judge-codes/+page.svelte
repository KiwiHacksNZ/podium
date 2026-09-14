<svelte:options runes />

<script lang="ts">
  import { page } from "$app/state";

  const { data } = $props();

  const judgeCode = $derived(
    (data.event as { judge_code?: string | null }).judge_code ?? null,
  );
  const owned = $derived(Boolean(data.event.owned));
  // Printed cards are handed out away from a screen, so spell the URL in full.
  const joinUrl = $derived(`${page.url.origin}/judge`);

  let count = $state(8);
  const cards = $derived(Array.from({ length: count }, (_, i) => i));
</script>

{#if !owned}
  <div role="alert" class="alert alert-warning max-w-2xl mx-auto mt-6">
    <span>Only the event organiser can print judge codes.</span>
  </div>
{:else if !judgeCode}
  <div role="alert" class="alert alert-info max-w-2xl mx-auto mt-6">
    <span>
      This event has no judge code yet. Generate one from the admin panel on the
      event page, then come back.
    </span>
  </div>
{:else}
  <div class="container mx-auto max-w-4xl p-4 sm:p-6 flex flex-col gap-6">
    <!-- Controls are screen-only; the sheet below is what reaches paper. -->
    <section class="no-print flex flex-wrap items-end gap-4">
      <div>
        <h1 class="text-2xl font-extrabold">Judge code cards</h1>
        <p class="text-sm opacity-70">
          Every card carries the same code — cut them up and hand one to each
          judge.
        </p>
      </div>
      <label class="form-control">
        <span class="label-text">Cards</span>
        <input
          class="input input-bordered w-24"
          type="number"
          min="1"
          max="60"
          bind:value={count}
        />
      </label>
      <button class="btn btn-primary" onclick={() => window.print()}>
        Print
      </button>
    </section>

    <div class="sheet grid grid-cols-1 sm:grid-cols-2 gap-4">
      {#each cards as i (i)}
        <article class="card-cut">
          <p class="card-line">Go to {joinUrl} and enter the code</p>
          <p class="card-code">{judgeCode}</p>
          <p class="card-line">To judge {data.event.name}</p>
        </article>
      {/each}
    </div>
  </div>
{/if}

<style>
  /* Deliberately plain black on white — these get photocopied and cut up. */
  .card-cut {
    border: 3px solid #000;
    border-radius: 1rem;
    background: #fff;
    color: #000;
    padding: 1.25rem 1rem;
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 0.75rem;
    min-height: 12rem;
    break-inside: avoid;
  }

  .card-line {
    font-size: 0.95rem;
    font-weight: 600;
    line-height: 1.3;
    overflow-wrap: anywhere;
  }

  .card-code {
    font-size: 3rem;
    font-weight: 800;
    letter-spacing: 0.35rem;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }

  @media print {
    /* Hide the app shell without unmounting it: visibility keeps the layout
       intact, and pulling the sheet to the top-left stops the hidden chrome
       from pushing a blank first page. */
    :global(body *) {
      visibility: hidden !important;
    }
    .sheet,
    .sheet * {
      visibility: visible !important;
    }
    .sheet {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      margin: 0;
      padding: 0;
      grid-template-columns: 1fr 1fr;
      gap: 0.5rem;
    }
    .no-print {
      display: none !important;
    }
  }

  @page {
    margin: 1cm;
  }
</style>
