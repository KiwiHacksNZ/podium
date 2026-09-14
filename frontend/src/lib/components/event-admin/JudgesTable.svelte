<script lang="ts">
  import { onMount } from "svelte";
  import { client } from "$lib/client/sdk.gen";
  import type { EventPrivate, UserAttendee } from "$lib/client/types.gen";
  import ConfirmationModal from "$lib/components/ConfirmationModal.svelte";
  import { handleError } from "$lib/misc";
  import { toast } from "svelte-sonner";

  interface Props {
    event: EventPrivate;
  }

  let { event }: Props = $props();

  type JudgeCode = { judge_code: string };

  let judges = $state<UserAttendee[]>([]);
  let loading = $state(true);
  let email = $state("");
  let adding = $state(false);
  let rotating = $state(false);
  // Set only after rotating; otherwise the event prop is the source of truth.
  let rotatedCode = $state<string | null>(null);
  const judgeCode = $derived(rotatedCode ?? event.judge_code ?? null);

  // Code shown inline after reissuing, so an organiser can read it straight out
  // to the judge standing in front of them.
  let reissued = $state<Record<string, string>>({});
  let reissuing = $state<string | null>(null);

  async function reissueCard(judge: UserAttendee) {
    reissuing = judge.id;
    const { data, error } = await client.post<{ code: string }, unknown>({
      url: `/events/admin/${event.id}/judges/${judge.id}/card`,
      throwOnError: false,
    });
    reissuing = null;
    if (error) {
      handleError(error);
      return;
    }
    if (data) reissued = { ...reissued, [judge.id]: data.code };
  }

  let removeConfirmation: ConfirmationModal = $state() as ConfirmationModal;
  let judgeToRemove = $state<UserAttendee | null>(null);

  async function loadJudges() {
    loading = true;
    const { data, error } = await client.get<UserAttendee[], unknown>({
      url: `/events/admin/${event.id}/judges`,
      throwOnError: false,
    });
    if (error) handleError(error);
    else judges = data ?? [];
    loading = false;
  }

  async function addJudge() {
    const trimmed = email.trim();
    if (!trimmed) return;
    adding = true;
    const { error } = await client.post<UserAttendee, unknown>({
      url: `/events/admin/${event.id}/add-judge`,
      body: { email: trimmed },
      throwOnError: false,
    });
    if (error) {
      handleError(error);
    } else {
      email = "";
      toast.success(`${trimmed} can now judge this event`);
      await loadJudges();
    }
    adding = false;
  }

  async function removeJudge() {
    if (!judgeToRemove) return;
    const { error } = await client.post<unknown, unknown>({
      url: `/events/admin/${event.id}/remove-judge`,
      body: { user_id: judgeToRemove.id },
      throwOnError: false,
    });
    if (error) handleError(error);
    else {
      toast.success("Judge removed");
      await loadJudges();
    }
    judgeToRemove = null;
  }

  async function rotateJudgeCode() {
    rotating = true;
    const { data, error } = await client.post<JudgeCode, unknown>({
      url: `/events/admin/${event.id}/judge-code`,
      throwOnError: false,
    });
    if (error) handleError(error);
    else if (data) {
      rotatedCode = data.judge_code;
      toast.success("New judge code generated");
    }
    rotating = false;
  }

  onMount(loadJudges);
</script>

<div class="card bg-base-200">
  <div class="card-body">
    <h2 class="card-title">Judges ({judges.length})</h2>
    <p class="text-sm text-base-content/70">
      Judging is scoped to this event — these people can score its projects and
      nothing else.
    </p>

    <div class="flex flex-wrap items-end gap-3 mt-2">
      <div>
        <div class="text-xs text-base-content/70">Judge code</div>
        <div class="font-mono text-2xl tracking-widest">
          {judgeCode ?? "——————"}
        </div>
      </div>
      <button
        class="btn btn-outline btn-sm"
        disabled={rotating}
        onclick={rotateJudgeCode}
      >
        {rotating ? "Generating…" : judgeCode ? "New code" : "Generate code"}
      </button>
      <a
        class="btn btn-outline btn-sm"
        href="/events/{event.slug}/judge-codes"
        target="_blank"
        rel="noopener">Print cards</a
      >
      <span class="text-sm text-base-content/70 flex-1 min-w-60">
        Judges claim access by entering this at <span class="font-mono"
          >/judge</span
        >. A new code invalidates the old one but doesn't remove anyone below.
      </span>
    </div>

    <div class="divider my-1"></div>

    <form
      class="flex flex-wrap gap-2"
      onsubmit={(e) => {
        e.preventDefault();
        addJudge();
      }}
    >
      <input
        class="input input-bordered input-sm flex-1 min-w-60"
        type="email"
        placeholder="judge@example.com"
        aria-label="Judge email"
        bind:value={email}
      />
      <button class="btn btn-primary btn-sm" disabled={adding || !email.trim()}>
        {adding ? "Adding…" : "Add judge"}
      </button>
    </form>

    {#if loading}
      <span class="loading loading-spinner loading-md"></span>
    {:else if judges.length === 0}
      <p class="text-base-content/70">
        No judges yet. Add one by email, or share the code above.
      </p>
    {:else}
      <div class="overflow-x-auto">
        <table class="table table-zebra table-sm w-full">
          <thead>
            <tr><th>Name</th><th>Email</th><th>New card</th><th></th></tr>
          </thead>
          <tbody>
            {#each judges as judge (judge.id)}
              <tr>
                <td>{judge.display_name || "—"}</td>
                <td class="font-mono text-xs">{judge.judge_email ?? judge.email}</td>
                <td>
                  {#if reissued[judge.id]}
                    <span class="font-mono text-lg tracking-widest"
                      >{reissued[judge.id]}</span
                    >
                  {:else}
                    <button
                      class="btn btn-outline btn-xs"
                      disabled={reissuing === judge.id}
                      onclick={() => reissueCard(judge)}
                    >
                      {reissuing === judge.id ? "…" : "New card"}
                    </button>
                  {/if}
                </td>
                <td>
                  <button
                    class="btn btn-ghost btn-xs"
                    onclick={() => {
                      judgeToRemove = judge;
                      removeConfirmation.open();
                    }}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</div>

<ConfirmationModal
  bind:this={removeConfirmation}
  title="Remove Judge"
  message={`Remove ${judgeToRemove?.email ?? "this judge"} from this event? Scores they already gave are kept.`}
  confirmText="Remove judge"
  onConfirm={removeJudge}
  onCancel={() => (judgeToRemove = null)}
/>
