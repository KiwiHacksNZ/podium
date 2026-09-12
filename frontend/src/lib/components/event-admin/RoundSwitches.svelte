<script lang="ts">
  import { untrack } from "svelte";
  import { EventsService } from "$lib/client/sdk.gen";
  import type { EventPrivate } from "$lib/client/types.gen";
  import { handleError } from "$lib/misc";
  import { toast } from "svelte-sonner";

  interface Props {
    event: EventPrivate;
    onUpdate?: (updated: EventPrivate) => void;
  }

  let { event, onUpdate }: Props = $props();

  // Local mirrors so a switch flips immediately even if the parent doesn't
  // reassign the `event` prop.
  let judgingOpen = $state(untrack(() => event.judging_open));
  let votingOpen = $state(untrack(() => event.voting_open));
  $effect(() => {
    judgingOpen = event.judging_open;
    votingOpen = event.voting_open;
  });

  let saving = $state(false);

  async function setRound(round: "judging_open" | "voting_open", open: boolean) {
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
    } else if (data) {
      judgingOpen = data.judging_open;
      votingOpen = data.voting_open;
      onUpdate?.(data);
      toast.success(
        `${round === "judging_open" ? "Judging" : "Attendee voting"} ${open ? "opened" : "closed"}`,
      );
    }
    saving = false;
  }
</script>

<div class="card bg-base-200">
  <div class="card-body">
    <h2 class="card-title">Rounds</h2>
    <p class="text-sm text-base-content/70">
      The two rounds open and close independently of the stage above — run them
      back to back, or at the same time.
    </p>

    <div class="flex flex-col gap-3 mt-2">
      <label class="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          class="toggle toggle-accent"
          disabled={saving}
          checked={judgingOpen}
          onchange={(e) =>
            setRound("judging_open", e.currentTarget.checked)}
        />
        <span>
          <span class="font-medium">Judge scoring</span>
          <span class="block text-sm text-base-content/70">
            Judges can score every project on all four criteria.
          </span>
        </span>
      </label>

      <label class="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          class="toggle toggle-primary"
          disabled={saving}
          checked={votingOpen}
          onchange={(e) => setRound("voting_open", e.currentTarget.checked)}
        />
        <span>
          <span class="font-medium">Attendee voting</span>
          <span class="block text-sm text-base-content/70">
            Attendees can rank {event.finalist_count > 0
              ? `the ${event.finalist_count} finalists`
              : "projects"} 1st / 2nd / 3rd.
          </span>
        </span>
      </label>
    </div>
  </div>
</div>
