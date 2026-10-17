<script lang="ts">
  import { untrack } from "svelte";
  import { EventsService } from "$lib/client/sdk.gen";
  import type { EventPrivate } from "$lib/client/types.gen";
  import { handleError } from "$lib/misc";
  import { asyncClick } from "$lib/actions/asyncClick";
  import { toast } from "svelte-sonner";

  let { event }: { event: EventPrivate } = $props();

  let theme = $state(untrack(() => event.theme ?? ""));

  async function save() {
    const { data, error } =
      await EventsService.updateEventAdminEventsAdminEventIdPatch({
        path: { event_id: event.id },
        body: { theme: theme.trim() },
        throwOnError: false,
      });
    if (error || !data) {
      handleError(error);
      return;
    }
    event.theme = theme = data.theme ?? "";
    toast.success("Theme saved");
  }
</script>

<div class="card bg-base-200">
  <div class="card-body">
    <h2 class="card-title">Theme</h2>
    <p class="text-sm text-base-content/70">
      Shown on the event page and to judges when they score how well a project fits the theme.
    </p>
    <textarea
      class="textarea textarea-bordered w-full mt-2"
      placeholder="e.g. Build something that helps your community"
      bind:value={theme}
    ></textarea>
    <div class="card-actions justify-end">
      <button
        class="btn btn-primary btn-sm"
        disabled={theme.trim() === (event.theme ?? "")}
        use:asyncClick={save}
      >
        Save theme
      </button>
    </div>
  </div>
</div>
