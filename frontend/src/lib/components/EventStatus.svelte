<script lang="ts">
  import { eventStatus } from "$lib/misc";

  // The event's state as a quiet label with a dot: it describes, it isn't a button.
  let {
    event,
  }: { event: { phase: string; voting_open?: boolean; judging_open?: boolean } } = $props();

  const status = $derived(eventStatus(event));
  // badge-* class -> matching text colour for the dot
  const dot = $derived(
    {
      "badge-info": "bg-info",
      "badge-warning": "bg-warning",
      "badge-accent": "bg-accent",
      "badge-success": "bg-success",
    }[status.badge] ?? "bg-base-content/40",
  );
</script>

<span class="inline-flex items-center gap-2 text-sm text-base-content/75">
  <span class="size-2 rounded-full {dot}" aria-hidden="true"></span>
  {status.label}
</span>
