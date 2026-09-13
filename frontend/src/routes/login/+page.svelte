<script lang="ts">
  import { defaultUser, getAuthenticatedUser } from "$lib/user.svelte";
  import { toast, Toaster } from "svelte-sonner";
  import { onMount } from "svelte";
  import { validateToken } from "$lib/user.svelte";
  import { AuthService, UsersService } from "$lib/client/sdk.gen";
  import { goto } from "$app/navigation";
  import type { HTTPValidationError } from "$lib/client/types.gen";
  import { handleError } from "$lib/misc";
  import type { UserSignup } from "$lib/client/types.gen";
  import { countries } from "countries-list";
  import { asyncClick } from "$lib/actions/asyncClick";
  import { Turnstile } from "svelte-turnstile";
  import { env } from "$env/dynamic/public";
  // rest is the extra props passed to the component
  let { ...rest } = $props();

  // Turnstile token — refreshed each time the user solves the challenge
  let turnstileToken = $state("");
  let resetTurnstile: (() => void) | undefined = $state();

  let isVerifying = $state(false);
  let showSignupFields = $state(false);
  let showEmailLogin = $state(false);
  let expandedDueTo = "";
  const configuredTurnstileSiteKey = env.PUBLIC_TURNSTILE_SITE_KEY;
  const turnstileSiteKey =
    configuredTurnstileSiteKey === "disabled"
      ? ""
      : configuredTurnstileSiteKey || "0x4AAAAAAEx_FfidvS2NGCvu";
  const hackClubSsoEnabled = $derived(
    Boolean(env.PUBLIC_SSO_CLIENT_ID || env.PUBLIC_HACKCLUB_CLIENT_ID),
  );
  let userInfo: UserSignup = $state({
    ...defaultUser,
  });
  $inspect(userInfo);
  $inspect(showSignupFields);
  let redirectUrl: string;

  // Convert countries to a list of objects with name and code
  const countryList = Object.entries(countries)
    .map(([code, data]) => ({
      code,
      name: data.name,
    }))
    .sort((a, b) => a.name.localeCompare(b.name));

  async function eitherLoginOrSignUp() {
    // console.debug("eitherLoginOrSignUp", showSignupFields);
    // If showSignupFields is true, the user is signing up and signupAndLogin should be called. Otherwise, the user is logging in and login should be called.
    if (!showSignupFields) {
      await login();
    } else {
      await signupAndLogin();
    }
  }

  /** Build headers including the Turnstile token when one is available. */
  function turnstileHeaders(): Record<string, string> {
    return turnstileToken ? { "X-Turnstile-Token": turnstileToken } : {};
  }

  function refreshTurnstile() {
    turnstileToken = "";
    resetTurnstile?.();
  }

  // Function to handle login
  async function login() {
    if (!userInfo.email || userInfo.email.trim() === "") {
      toast.error("Please enter your email address.");
      document.getElementById("email")?.focus();
      return;
    }
    // Even though error handling is done in the API, the try-finally block is used to ensure the loading state is reset
    const { data, error: err } = await AuthService.requestLoginRequestLoginPost({
      body: { email: userInfo.email },
      query: { redirect: redirectUrl ?? "" },
      headers: turnstileHeaders(),
      throwOnError: false,
    }).finally(refreshTurnstile);
    if (err || !data) {
      handleError(err);
      return;
    }
    if (data.account_exists) {
      toast.success(`Magic link sent to ${userInfo.email}. Check your spam folder if you don't see it!`);
      // Clear field
      userInfo.email = "";
    } else {
      toast.error("You don't exist (yet)! Let's change that.");
      expandedDueTo = userInfo.email;
      showSignupFields = true;
    }
  }

  // Function to handle signup and login
  async function signupAndLogin() {
    if (!userInfo.email || userInfo.email.trim() === "") {
      toast.error("Please enter your email address.");
      document.getElementById("email")?.focus();
      return;
    }
    const signupEmail = userInfo.email;
    const { error: signupErr } = await UsersService.createUserUsersPost({
      body: userInfo,
      query: { send_login_link: true, redirect: redirectUrl ?? "" },
      headers: turnstileHeaders(),
      throwOnError: false,
    }).finally(refreshTurnstile);
    if (signupErr) {
      handleError(signupErr);
      return;
    }

    showSignupFields = false;
    expandedDueTo = "";
    toast.success(`Magic link sent to ${signupEmail}. Check your spam folder if you don't see it!`);
    // Reset values for the next signup attempt
    userInfo = {
      ...defaultUser,
    };
  }

  // Function to handle verification link
  async function verifyMagicLink(token: string) {
    isVerifying = true;
    try {
      const { data, error: err } = await AuthService.verifyTokenVerifyGet({
        query: { token },
        throwOnError: false,
      });
      if (err || !data) {
        handleError(err);
        return;
      }
      await validateToken(data.access_token);
      toast("Login successful");

      const target = redirectUrl && redirectUrl.trim() !== "" ? redirectUrl : "/";
      await goto(target);
    } finally {
      isVerifying = false;
    }
  }

  // Read auth material from the URL fragment, which browsers never send to servers.
  onMount(() => {
    const urlParams = new URLSearchParams(window.location.hash.slice(1));
    const token = urlParams.get("token");
    redirectUrl = urlParams.get("redirect") ?? "";
    if (token) {
      window.history.replaceState({}, "", window.location.pathname);
      verifyMagicLink(token);
    }
  });

  // Prevent default form submission (not needed it seems)
  // https://svelte.dev/docs/svelte/svelte-legacy#preventDefault
  // https://svelte.dev/docs/svelte/v5-migration-guide#Breaking-changes-in-runes-mode-Touch-and-wheel-events-are-passive
  // function preventDefault(fn) {
  //     return function (event) {
  //         event.preventDefault();
  //         fn.call(this, event);
  //     };
  // }
</script>

<div class="p-4 max-w-md mx-auto" {...rest}>
  {#if getAuthenticatedUser().access_token}
    <div class="text-center">
      <h2 class="text-2xl font-bold mb-2">
        You are logged in as {getAuthenticatedUser().user.email}
      </h2>
      <button
        class="mt-4 px-4 py-2 btn btn-primary"
        onclick={() => history.back()}
      >
        Go back to previous page
      </button>
    </div>
  {:else if isVerifying}
    <div class="text-center">
      <span class="loading loading-spinner loading-lg"></span>
      <p class="mt-2">Verifying your magic link...</p>
    </div>
  {:else}
    {#if hackClubSsoEnabled}
      <a
        href="{env.PUBLIC_API_URL}/auth/sso"
        class="btn btn-lg w-full mb-2 gap-2"
        style="background-color: #132f1e; color: #eae6e2; border-color: #132f1e;"
      >
        <img src="/kiwihacks-logo.png" alt="KiwiHacks" class="w-6 h-6" />
        Sign in with KiwiHacks
      </a>
      <p class="text-center text-sm text-base-content/60 mb-1">
        One account for everything KiwiHacks.
      </p>
      {#if !showEmailLogin}
        <button
          type="button"
          class="btn btn-link btn-xs w-full text-base-content/50"
          onclick={() => (showEmailLogin = true)}
        >
          or continue with email
        </button>
      {:else}
        <div class="divider my-2">or use email</div>
      {/if}
    {/if}

    {#if showEmailLogin || !hackClubSsoEnabled}
    <fieldset
      class="fieldset bg-base-200 border-base-300 rounded-box border p-4"
    >
      <label class="label flex justify-between" for="email">
        <span>Email</span>
      </label>
      <input
        id="email"
        type="email"
        class="input input-bordered w-full"
        bind:value={userInfo.email}
        placeholder="example@example.com"
        onblur={() => {
          if (
            expandedDueTo != userInfo.email &&
            userInfo.email &&
            showSignupFields
          ) {
            showSignupFields = false;
          }
        }}
      />
      <label class="label flex justify-between" for="email">
        <span>We'll send you an email</span>
      </label>

      {#if showSignupFields}
        <label class="label" for="first_name">First Name</label>
        <input
          id="first_name"
          type="text"
          class="input input-bordered w-full"
          placeholder="Abc"
          bind:value={userInfo.first_name}
        />

        <label class="label" for="last_name">Last Name</label>
        <input
          id="last_name"
          type="text"
          class="input input-bordered w-full"
          placeholder="Xyz"
          bind:value={userInfo.last_name}
        />

        <p class="text-sm text-base-content/60">
          Your display name will default to First Name + Last Initial (e.g. Alex B.) and can be changed later in your profile.
        </p>

        <label class="label flex justify-between" for="phone">
          <span>Phone</span>
          <span>Optional, but recommended</span>
        </label>
        <input
          id="phone"
          type="tel"
          class="input input-bordered w-full"
          placeholder="+15555555555"
          bind:value={userInfo.phone}
        />
        <label class="label flex justify-between" for="phone">
          <span>International format without spaces or special characters</span>
        </label>

        <label class="label" for="street_1">Address line 1</label>
        <input
          id="street_1"
          type="text"
          class="input input-bordered w-full"
          placeholder="123 Main St"
          bind:value={userInfo.street_1}
        />

        <label class="label flex justify-between" for="street_2">
          <span>Address line 2</span>
          <span>Optional</span>
        </label>
        <input
          id="street_2"
          type="text"
          class="input input-bordered w-full"
          placeholder="Apt 4B"
          bind:value={userInfo.street_2}
        />

        <label class="label" for="city">City</label>
        <input
          id="city"
          type="text"
          class="input input-bordered w-full"
          placeholder="New York"
          bind:value={userInfo.city}
        />

        <label class="label" for="state">State/Province</label>
        <input
          id="state"
          type="text"
          class="input input-bordered w-full"
          placeholder="NY"
          bind:value={userInfo.state}
        />

        <label class="label" for="zip_code">Zip/Postal Code</label>
        <input
          id="zip_code"
          type="text"
          class="input input-bordered w-full"
          placeholder="10001"
          bind:value={userInfo.zip_code}
        />

        <label class="label" for="country">Country</label>
        <select
          id="country"
          class="select select-bordered w-full"
          bind:value={userInfo.country}
        >
          {#each countryList as { code, name } (code)}
            <option value={code} selected={userInfo.country == code}>
              {name}
            </option>
          {/each}
        </select>

        <label class="label flex justify-between" for="dob">
          <span>Date of Birth</span>
          <span>This event is only for students {"<="}18</span>
        </label>
        <input
          id="dob"
          type="date"
          class="input input-bordered w-full"
          bind:value={userInfo.dob}
        />
      {/if}

      {#if turnstileSiteKey}
        <div class="flex justify-center mt-4">
          <Turnstile
            siteKey={turnstileSiteKey}
            action="authenticate"
            theme="auto"
            bind:reset={resetTurnstile}
            on:callback={(e) => {
              turnstileToken = e.detail.token;
            }}
            on:expired={() => (turnstileToken = "")}
            on:timeout={() => (turnstileToken = "")}
            on:error={() => {
              turnstileToken = "";
              toast.error("Security check failed to load. Please refresh the page.");
            }}
          />
        </div>
      {/if}

      <div class="flex justify-center">
        <button
          class="btn btn-primary mt-4"
          disabled={!!turnstileSiteKey && !turnstileToken}
          use:asyncClick={eitherLoginOrSignUp}
        >
          Login / Sign Up
        </button>
      </div>
    </fieldset>
    {/if}

  {/if}
  <div class="text-center mt-4">
    <a href="/" class="btn-sm btn-secondary btn">← Back Home</a>
  </div>
</div>
