<svelte:options runes />

<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/state";
  import { client } from "$lib/client/sdk.gen";
  import { handleError } from "$lib/misc";
  import { asyncClick } from "$lib/actions/asyncClick";

  type Card = {
    code: string;
    redeemed_at?: string | null;
    redeemed_by?: string | null;
    issued_for?: string | null;
  };

  const { data } = $props();

  const owned = $derived(Boolean(data.event.owned));
  // Printed cards are handed out away from a screen, so spell the URL in full.
  const joinUrl = $derived(`${page.url.origin}/judge`);

  let cards = $state<Card[]>([]);
  let loading = $state(true);
  let count = $state(8);

  // Only unused cards are worth printing; spent ones stay listed below so an
  // organiser can see which card became which judge.
  const unused = $derived(cards.filter((c) => !c.redeemed_at));
  const spent = $derived(cards.filter((c) => c.redeemed_at));

  async function load() {
    const { data: list, error } = await client.get<Card[], unknown>({
      url: `/events/admin/${data.event.id}/judge-cards`,
      throwOnError: false,
    });
    if (error) handleError(error);
    else cards = list ?? [];
    loading = false;
  }

  async function mint() {
    const { error } = await client.post<Card[], unknown>({
      url: `/events/admin/${data.event.id}/judge-cards`,
      body: { count },
      throwOnError: false,
    });
    if (error) {
      handleError(error);
      return;
    }
    await load();
  }

  onMount(load);
</script>

{#if !owned}
  <div role="alert" class="alert alert-warning max-w-2xl mx-auto mt-6">
    <span>Only the event organiser can print judge codes.</span>
  </div>
{:else}
  <div class="container mx-auto max-w-4xl p-4 sm:p-6 flex flex-col gap-6">
    <!-- Controls are screen-only; the sheet below is what reaches paper. -->
    <section class="no-print flex flex-wrap items-end gap-4">
      <div>
        <h1 class="text-2xl font-extrabold">Judge code cards</h1>
        <p class="text-sm opacity-70">
          Each card has its own code, used up by the first judge who enters it.
        </p>
      </div>
      <label class="form-control">
        <span class="label-text">Make more</span>
        <input
          class="input input-bordered w-24"
          type="number"
          min="1"
          max="100"
          bind:value={count}
        />
      </label>
      <button class="btn btn-outline" use:asyncClick={mint}>Generate</button>
      <button
        class="btn btn-primary"
        disabled={unused.length === 0}
        onclick={() => window.print()}
      >
        Print {unused.length || ""}
      </button>
    </section>

    {#if loading}
      <span class="loading loading-spinner loading-md no-print"></span>
    {:else if unused.length === 0}
      <div role="alert" class="alert alert-info no-print">
        <span>
          No unused cards. Choose how many you need and hit Generate.
        </span>
      </div>
    {/if}

    <div class="sheet grid grid-cols-1 sm:grid-cols-2 gap-4">
      {#each unused as card (card.code)}
        <article class="card-cut">
          <p class="card-line">Go to {joinUrl} and enter the code</p>
          <p class="card-code">{card.code}</p>
          <p class="card-line">
            To judge {data.event.name}{card.issued_for
              ? ` — for ${card.issued_for}`
              : ""}
          </p>
        </article>
      {/each}
    </div>

    {#if spent.length > 0}
      <section class="no-print">
        <h2 class="font-bold">Used cards</h2>
        <ul class="text-sm opacity-70 mt-2 flex flex-col gap-1">
          {#each spent as card (card.code)}
            <li>
              <span class="font-mono">{card.code}</span>
              — {card.redeemed_by ?? "a judge"}{card.issued_for
                ? ` (reissued for ${card.issued_for})`
                : ""}
            </li>
          {/each}
        </ul>
      </section>
    {/if}
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
