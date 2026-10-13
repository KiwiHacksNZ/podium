<script lang="ts">
  import { AI_CODE_LIMIT_PERCENT } from "$lib/misc";

  // Read-only view of a project's AI declaration. `compact` shows just the badge.
  let {
    declaration = "",
    underLimit = null,
    compact = false,
  }: {
    declaration?: string | null;
    underLimit?: boolean | null;
    compact?: boolean;
  } = $props();

  const declared = $derived(Boolean(declaration?.trim()) || underLimit !== null);
  const noAi = $derived(/^\s*(none|no|n\/a|nothing)\.?\s*$/i.test(declaration ?? ""));
</script>

{#snippet badge()}
  {#if underLimit === false}
    <span class="badge badge-error badge-sm shrink-0">Over {AI_CODE_LIMIT_PERCENT}% AI</span>
  {:else if noAi}
    <span class="badge badge-ghost badge-sm shrink-0">No AI used</span>
  {:else if underLimit === true}
    <span class="badge badge-info badge-sm shrink-0">Under {AI_CODE_LIMIT_PERCENT}% AI</span>
  {/if}
{/snippet}

{#if declared}
  <!-- Nothing written beyond "None": the badge says it all -->
  {#if compact || noAi || !declaration?.trim()}
    {@render badge()}
  {:else}
    <div
      class="rounded-box p-3 text-sm flex flex-col gap-1 {underLimit === false
        ? 'bg-error/15 border border-error/40'
        : 'bg-base-300/60'}"
    >
      <div class="flex items-center justify-between gap-2">
        <span class="font-semibold">AI declaration</span>
        {@render badge()}
      </div>
      <p class="whitespace-pre-line break-words opacity-90">{declaration}</p>
    </div>
  {/if}
{/if}
