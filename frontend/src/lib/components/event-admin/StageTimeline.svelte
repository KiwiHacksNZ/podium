<script lang="ts">
  import { untrack } from "svelte";
  import { EventsService } from "$lib/client/sdk.gen";
  import type { EventPrivate, EventUpdate } from "$lib/client/types.gen";
  import { handleError } from "$lib/misc";
  import { toast } from "svelte-sonner";

  interface Props {
    event: EventPrivate;
    onUpdate?: (updated: EventPrivate) => void;
  }

  let { event, onUpdate }: Props = $props();

  // Local mirrors so the card updates immediately even if the parent doesn't
  // reassign the `event` prop.
  let phase = $state(untrack(() => event.phase));
  let judgingOpen = $state(untrack(() => event.judging_open));
  let votingOpen = $state(untrack(() => event.voting_open));
  $effect(() => {
    phase = event.phase;
    judgingOpen = event.judging_open;
    votingOpen = event.voting_open;
  });

  // Keep in sync with backend EventPhase enum (backend/podium/constants.py).
  // The stage sets visibility and the leaderboard; the judging and voting
  // rounds open and close on their own, right here beside it, so the two can
  // never quietly disagree without the organiser seeing it.
  const stages = [
    {
      id: "hidden",
      label: "Hidden",
      description: "Kept off the public event list. Direct links still work.",
    },
    { id: "draft", label: "Draft", description: "Not yet accepting submissions" },
    { id: "submission", label: "Submission", description: "Open for project submissions" },
    {
      id: "judging",
      label: "Judging",
      description:
        "Submissions closed. Open judge scoring, then lock in the top 5 finalists.",
    },
    {
      id: "voting",
      label: "Voting",
      description: "Finalists picked. Open attendee voting when you're ready.",
    },
    { id: "closed", label: "Closed", description: "Voting closed, leaderboard visible" },
  ] as const;

  let saving = $state(false);

  const currentIndex = $derived(
    Math.max(0, stages.findIndex((s) => s.id === phase)),
  );

  async function patch(body: EventUpdate, message: string) {
    if (saving) return;
    saving = true;
    const { data, error } =
      await EventsService.updateEventAdminEventsAdminEventIdPatch({
        path: { event_id: event.id },
        body,
        throwOnError: false,
      });
    if (error) {
      handleError(error);
    } else if (data) {
      phase = data.phase;
      judgingOpen = data.judging_open;
      votingOpen = data.voting_open;
      onUpdate?.(data);
      toast.success(message);
    }
    saving = false;
  }

  function setPhase(next: string) {
    if (next === phase) return;
    patch({ phase: next }, `Event set to ${next}`);
  }

  function setRound(round: "judging_open" | "voting_open", open: boolean) {
    const name = round === "judging_open" ? "Judge scoring" : "Attendee voting";
    patch({ [round]: open }, `${name} ${open ? "opened" : "closed"}`);
  }

  const rounds = $derived([
    {
      key: "judging_open" as const,
      name: "Judge scoring",
      open: judgingOpen,
      // The round this stage is about, so it reads as the next step
      current: phase === "judging",
      blurb: "Judges score every project on all four criteria.",
    },
    {
      key: "voting_open" as const,
      name: "Attendee voting",
      open: votingOpen,
      current: phase === "voting",
      blurb:
        event.finalist_count > 0
          ? `Attendees rank the ${event.finalist_count} finalists 1st / 2nd / 3rd.`
          : "Attendees rank projects 1st / 2nd / 3rd.",
    },
  ]);

  // States that are allowed but almost certainly a mistake
  const warnings = $derived(
    [
      phase === "closed" && votingOpen
        ? {
            text: "Results are public, but attendee voting is still open. New ballots will change the leaderboard.",
            fix: "Close voting",
            round: "voting_open" as const,
          }
        : null,
      phase === "closed" && judgingOpen
        ? {
            text: "The event is closed, but judge scoring is still open.",
            fix: "Close scoring",
            round: "judging_open" as const,
          }
        : null,
    ].filter((w) => w !== null),
  );
</script>

<div class="card bg-base-200">
  <div class="card-body gap-4">
    <h3 class="card-title text-base">Event status</h3>

    <!-- DaisyUI `steps` renders the dot-and-connector timeline. Each <li> is
         the click target so the dot AND the label are both hit areas. -->
    <ul class="steps steps-vertical sm:steps-horizontal w-full">
      {#each stages as stage, i}
        <li
          class="step {i <= currentIndex ? 'step-primary' : ''}"
          data-content={i < currentIndex ? "✓" : i + 1}
        >
          <button
            type="button"
            class="link link-hover font-medium disabled:opacity-60 disabled:no-underline"
            disabled={saving}
            onclick={() => setPhase(stage.id)}
          >
            {stage.label}
          </button>
        </li>
      {/each}
    </ul>

    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-sm text-base-content/70">
        {stages[currentIndex].description}
      </p>
      <!-- Explicit select as a second, unambiguous control. Useful on mobile
           and for users who don't realize the timeline is clickable. -->
      <label class="flex items-center gap-2 text-sm">
        <span class="text-base-content/70">Set stage:</span>
        <select
          class="select select-sm select-bordered"
          disabled={saving}
          value={phase}
          onchange={(e) => setPhase((e.currentTarget as HTMLSelectElement).value)}
        >
          {#each stages as stage}
            <option value={stage.id}>{stage.label}</option>
          {/each}
        </select>
      </label>
    </div>

    {#each warnings as warning (warning.round)}
      <div role="alert" class="alert alert-warning">
        <span>{warning.text}</span>
        <button
          type="button"
          class="btn btn-sm"
          disabled={saving}
          onclick={() => setRound(warning.round, false)}
        >
          {warning.fix}
        </button>
      </div>
    {/each}

    <div class="flex flex-col gap-2">
      {#each rounds as round (round.key)}
        <div
          class="flex flex-wrap items-center gap-3 rounded-box bg-base-100 px-4 py-3 {round.current
            ? 'ring-1 ring-primary/40'
            : ''}"
        >
          <span
            class="size-2.5 shrink-0 rounded-full {round.open ? 'bg-success' : 'bg-base-content/25'}"
            aria-hidden="true"
          ></span>
          <span class="min-w-0 grow">
            <span class="font-medium">{round.name}:</span>
            <span class={round.open ? "text-success" : "text-base-content/60"}>
              {round.open ? "open" : "closed"}
            </span>
            <span class="block text-sm text-base-content/60">{round.blurb}</span>
          </span>
          <button
            type="button"
            class="btn btn-sm {round.open ? 'btn-ghost' : round.current ? 'btn-primary' : ''}"
            disabled={saving}
            onclick={() => setRound(round.key, !round.open)}
          >
            {round.open ? "Close" : "Open"}
            {round.key === "judging_open" ? "scoring" : "voting"}
          </button>
        </div>
      {/each}
      <p class="text-xs text-base-content/55">
        Rounds open and close independently of the stage, so you can run them
        back to back or at the same time. Closing the event closes voting.
      </p>
    </div>
  </div>
</div>
