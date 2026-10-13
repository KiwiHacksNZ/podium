<script lang="ts">
  import type { PageData } from "./$types";
  import AdminPanel from "$lib/components/event-admin/AdminPanel.svelte";
  import type { EventPrivate } from "$lib/client/types.gen";
  import { getAuthenticatedUser, isAuthenticated } from "$lib/user.svelte";
  import { toast } from "svelte-sonner";
  import { handleError } from "$lib/misc";
  import { client } from "$lib/client/sdk.gen";
  import { goto } from "$app/navigation";

  let { data }: { data: PageData } = $props();

  let joining = $state(false);

  // Type assertion: owned events are always PrivateEvent
  function getPrivateEvent(
    event: any,
  ): EventPrivate & { owned: boolean; partOfEvent: boolean } {
    return event as EventPrivate & { owned: boolean; partOfEvent: boolean };
  }

  async function joinEvent() {
    joining = true;
    try {
      const response = await client.post<{ message: string; event_id: string }>(
        { url: `/events/${data.event.id}/attend` },
      );
      if (response.error) {
        handleError(response.error);
        return;
      }
      toast.success("Joined event!");
      // Go to home so the user can submit their project
      await goto("/");
    } catch (err) {
      handleError(err);
    } finally {
      joining = false;
    }
  }

  const isAuthed = $derived(isAuthenticated());
  const isJudge = $derived(
    !!getAuthenticatedUser().user.judge_event_ids?.includes(data.event.id),
  );
  const finalistCount = $derived(data.event.finalist_count ?? 0);

  const accents = {
    primary: { border: "hover:border-primary/60", text: "text-primary" },
    secondary: { border: "hover:border-secondary/60", text: "text-secondary" },
    accent: { border: "hover:border-accent/60", text: "text-accent" },
    info: { border: "hover:border-info/60", text: "text-info" },
  };
</script>

<!-- Full class names so Tailwind can see them -->
{#snippet action(href: string, title: string, blurb: string, enabled: boolean, accent: keyof typeof accents)}
  {#if enabled}
    <a {href} class="card border border-base-content/10 bg-base-100 shadow-sm transition-colors {accents[accent].border}">
      <div class="card-body gap-1 p-5">
        <span class="flex items-center justify-between gap-2">
          <span class="text-lg font-bold">{title}</span>
          <span class={accents[accent].text} aria-hidden="true">&rarr;</span>
        </span>
        <span class="text-sm text-base-content/70">{blurb}</span>
      </div>
    </a>
  {:else}
    <div class="card border border-dashed border-base-content/15 bg-base-100/40" aria-disabled="true">
      <div class="card-body gap-1 p-5">
        <span class="text-lg font-bold text-base-content/50">{title}</span>
        <span class="text-sm text-base-content/50">{blurb}</span>
      </div>
    </div>
  {/if}
{/snippet}

<div class="mx-auto mt-2 grid max-w-3xl grid-cols-1 gap-4 px-4 sm:grid-cols-2">
  {#if data.event.judging_open && isJudge}
    {@render action(
      `/events/${data.event.slug}/judge`,
      "Judge projects",
      "Score every project on all four criteria.",
      true,
      "accent",
    )}
  {/if}
  {#if data.event.partOfEvent}
    {@render action(
      `/events/${data.event.slug}/rank`,
      finalistCount > 0 ? "Rank the finalists" : "Vote",
      data.event.voting_open
        ? finalistCount > 0
          ? `Pick your top 3 of the ${finalistCount} finalists.`
          : "Pick your top 3 projects."
        : "Voting isn't open yet. Your organisers will open it.",
      data.event.voting_open,
      "primary",
    )}
  {/if}
  {@render action(
    `/events/${data.event.slug}/showcase`,
    "Showcase",
    "Browse every project built at this event.",
    true,
    "secondary",
  )}
  {#if !data.event.owned}
    {@render action(
      `/events/${data.event.slug}/leaderboard`,
      "Leaderboard",
      data.event.phase === "closed"
        ? "See the final results."
        : "Results appear here once voting closes.",
      data.event.phase === "closed",
      "info",
    )}
  {/if}

  {#if !data.event.partOfEvent && !data.event.owned}
    <div class="card bg-base-200 text-center sm:col-span-2">
      <div class="card-body items-center gap-2 py-5">
        {#if isAuthed}
          <p class="text-base-content/70 text-sm">You're not attending this event yet.</p>
          <button class="btn btn-primary btn-sm" onclick={joinEvent} disabled={joining}>
            {#if joining}
              <span class="loading loading-spinner loading-xs"></span>
            {/if}
            Join this event
          </button>
        {:else}
          <p class="text-base-content/70 text-sm">Want to submit a project or vote?</p>
          <a href="/login?redirect=/events/{data.event.slug}" class="btn btn-primary btn-sm">
            Sign in to participate
          </a>
        {/if}
      </div>
    </div>
  {/if}
</div>

{#if data.event.owned}
  <AdminPanel event={getPrivateEvent(data.event)} />
{/if}
