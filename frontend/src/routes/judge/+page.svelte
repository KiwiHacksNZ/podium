<svelte:options runes />

<script lang="ts">
  import { goto } from "$app/navigation";
  import { client } from "$lib/client/sdk.gen";
  import { validateToken } from "$lib/user.svelte";
  import { handleError } from "$lib/misc";
  import { asyncClick } from "$lib/actions/asyncClick";
  import { toast } from "svelte-sonner";

  type Redeemed = {
    access_token: string;
    token_type: string;
    event_id: string;
    event_name: string;
    event_slug: string;
  };

  let code = $state("");
  let name = $state("");
  let email = $state("");
  const emailLooksValid = $derived(/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim()));
  const valid = $derived(
    /^\d{6}$/.test(code.trim()) && name.trim().length > 0 && emailLooksValid,
  );

  async function redeem() {
    if (!/^\d{6}$/.test(code.trim())) {
      toast.error("Judge codes are 6 digits");
      return;
    }
    if (!name.trim()) {
      toast.error("Enter your name");
      return;
    }
    if (!emailLooksValid) {
      toast.error("Enter a valid email address");
      return;
    }
    const { data, error } = await client.post<Redeemed, unknown>({
      url: "/judging/redeem",
      body: { code: code.trim(), name: name.trim(), email: email.trim() },
      throwOnError: false,
    });
    if (error) {
      handleError(error);
      return;
    }
    if (!data) return;
    // The code redemption logs the judge in; validate the returned token so
    // the judging page sees judge_event_ids before it guards on them.
    await validateToken(data.access_token);
    toast.success(`You're a judge for ${data.event_name}`);
    await goto(`/events/${data.event_slug}/judge`);
  }
</script>

<div class="max-w-md mx-auto mt-10 space-y-4">
  <div class="card bg-base-200">
    <div class="card-body">
      <h1 class="card-title">Become a judge</h1>
      <p class="text-sm text-base-content/70">
        Enter your name, email and the 6-digit judge code your event organizer
        gave you. No account needed — the email just lets organisers reach you.
      </p>

      <input
        class="input input-bordered w-full"
        autocomplete="name"
        placeholder="Your name"
        aria-label="Your name"
        bind:value={name}
      />
      <input
        class="input input-bordered w-full"
        type="email"
        autocomplete="email"
        placeholder="you@example.com"
        aria-label="Your email"
        bind:value={email}
      />
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
    </div>
  </div>
</div>
