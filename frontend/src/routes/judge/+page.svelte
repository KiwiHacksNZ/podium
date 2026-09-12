<svelte:options runes />

<script lang="ts">
  import { goto } from "$app/navigation";
  import { client } from "$lib/client/sdk.gen";
  import { getAuthenticatedUser, validateToken } from "$lib/user.svelte";
  import { handleError } from "$lib/misc";
  import { asyncClick } from "$lib/actions/asyncClick";
  import { toast } from "svelte-sonner";

  type Redeemed = { event_id: string; event_name: string; event_slug: string };

  let code = $state("");
  const isAuthenticated = $derived(!!getAuthenticatedUser().access_token);
  const valid = $derived(/^\d{6}$/.test(code.trim()));

  async function redeem() {
    if (!valid) {
      toast.error("Judge codes are 6 digits");
      return;
    }
    const { data, error } = await client.post<Redeemed, unknown>({
      url: "/judging/redeem",
      body: { code: code.trim() },
      throwOnError: false,
    });
    if (error) {
      handleError(error);
      return;
    }
    if (!data) return;
    // Refresh the user so the new event shows in judge_event_ids before the
    // judging page guards on it.
    await validateToken(getAuthenticatedUser().access_token);
    toast.success(`You're a judge for ${data.event_name}`);
    await goto(`/events/${data.event_slug}/judge`);
  }
</script>

<div class="max-w-md mx-auto mt-10 space-y-4">
  <div class="card bg-base-200">
    <div class="card-body">
      <h1 class="card-title">Become a judge</h1>
      <p class="text-sm text-base-content/70">
        Enter the 6-digit judge code your event organizer gave you.
      </p>

      {#if !isAuthenticated}
        <div role="alert" class="alert alert-warning">
          <span>Sign in first, then come back and enter your code.</span>
        </div>
      {:else}
        <input
          class="input input-bordered w-full font-mono text-2xl tracking-widest text-center"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          placeholder="000000"
          aria-label="Judge code"
          bind:value={code}
          oninput={() => (code = code.replace(/\D/g, ""))}
        />
        <button
          class="btn btn-primary btn-block"
          disabled={!valid}
          use:asyncClick={redeem}
        >
          Claim judge access
        </button>
      {/if}
    </div>
  </div>
</div>
