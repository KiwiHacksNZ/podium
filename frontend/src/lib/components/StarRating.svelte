<svelte:options runes />

<script lang="ts">
  interface Props {
    value: number | null;
    onchange: (v: number) => void;
    label: string;
    disabled?: boolean;
  }

  let { value, onchange, label, disabled = false }: Props = $props();

  const uid = $props.id();
  const name = `star-rating-${uid}`;
  const stars = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
</script>

<div class="flex flex-wrap items-center gap-3">
  <div class="rating rating-md" role="radiogroup" aria-label={label}>
    <!-- Lets the row render empty: DaisyUI dims every star that follows the checked input -->
    <input
      type="radio"
      {name}
      {disabled}
      class="rating-hidden"
      aria-label="No rating yet"
      checked={value === null}
    />
    {#each stars as star}
      <input
        type="radio"
        {name}
        {disabled}
        class="mask mask-star-2 bg-current"
        aria-label={`${star} out of 10 for ${label}`}
        checked={value === star}
        onchange={() => onchange(star)}
      />
    {/each}
  </div>
  <span class="text-sm font-bold tabular-nums" aria-live="polite">
    {value ?? "—"}/10
  </span>
</div>
