<script lang="ts">
  import { untrack } from "svelte";
  import { EventsService } from "$lib/client/sdk.gen";
  import type { EventPrivate } from "$lib/client/types.gen";
  import { AI_CODE_LIMIT_PERCENT, handleError } from "$lib/misc";
  import { toast } from "svelte-sonner";

  interface Props {
    event: EventPrivate;
    onUpdate?: (updated: EventPrivate) => void;
  }

  let { event, onUpdate }: Props = $props();

  // Local mirrors so a switch flips immediately even if the parent doesn't
  // reassign the `event` prop.
  let isPast = $state(untrack(() => event.is_past));
  let requireAi = $state(untrack(() => event.require_ai_declaration));
  $effect(() => {
    isPast = event.is_past;
    requireAi = event.require_ai_declaration;
  });

  const toastLabels = {
    is_past: (on: boolean) =>
      on ? "Moved to past events" : "Removed from past events",
    require_ai_declaration: (on: boolean) =>
      on ? "AI declarations now required" : "AI declarations no longer required",
  };

  let saving = $state(false);

  async function setRound(
    round: "is_past" | "require_ai_declaration",
    toggle: HTMLInputElement,
  ) {
    const open = toggle.checked;
    if (saving) return;
    saving = true;
    const { data, error } =
      await EventsService.updateEventAdminEventsAdminEventIdPatch({
        path: { event_id: event.id },
        body: { [round]: open },
        throwOnError: false,
      });
    if (error) {
      handleError(error);
      // Snap the toggle back: the browser already flipped it on tap, and the
      // state didn't change so Svelte won't re-render it.
      toggle.checked = !open;
    } else if (data) {
      isPast = data.is_past;
      requireAi = data.require_ai_declaration;
      onUpdate?.(data);
      toast.success(toastLabels[round](open));
    }
    saving = false;
  }
</script>

<div class="card bg-base-200">
  <div class="card-body">
    <h2 class="card-title">Settings</h2>

    <div class="flex flex-col gap-3 mt-2">
      <label class="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          class="toggle toggle-info shrink-0"
          disabled={saving}
          checked={requireAi}
          onchange={(e) => setRound("require_ai_declaration", e.currentTarget)}
        />
        <span>
          <span class="font-medium">Require AI declaration</span>
          <span class="block text-sm text-base-content/70">
            Teams must say how they used AI and whether it wrote less than
            {AI_CODE_LIMIT_PERCENT}% of their code. Judges see every declaration.
          </span>
        </span>
      </label>

      <label class="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          class="toggle toggle-secondary shrink-0"
          disabled={saving}
          checked={isPast}
          onchange={(e) => setRound("is_past", e.currentTarget)}
        />
        <span>
          <span class="font-medium">Past event</span>
          <span class="block text-sm text-base-content/70">
            Takes the event off the main event list and shows its results on
            <a href="/past-events" class="link">/past-events</a>.
          </span>
        </span>
      </label>
    </div>
  </div>
</div>
