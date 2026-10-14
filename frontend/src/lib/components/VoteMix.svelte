<script lang="ts">
  import { voteBreakdown } from "$lib/misc";

  // How a project's votes split across 1st / 2nd / 3rd choices, as one bar.
  // The text breakdown stays alongside for exact numbers and screen readers.
  let {
    rankCounts,
    class: className = "",
  }: { rankCounts: number[] | undefined; class?: string } = $props();

  const counts = $derived((rankCounts ?? []).slice(0, 3));
  const total = $derived(counts.reduce((a, b) => a + b, 0));
  const shades = ["bg-primary", "bg-primary/60", "bg-primary/30"];
</script>

<div class="flex flex-col gap-1 {className}">
  {#if total > 0}
    <div class="flex h-1.5 w-full overflow-hidden rounded-full bg-base-content/10" aria-hidden="true">
      {#each counts as n, i}
        {#if n > 0}
          <div class={shades[i]} style="width: {(n / total) * 100}%"></div>
        {/if}
      {/each}
    </div>
  {/if}
  <p class="text-xs text-base-content/60">{voteBreakdown(rankCounts)}</p>
</div>
