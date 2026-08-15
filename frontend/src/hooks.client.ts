import * as Sentry from "@sentry/sveltekit";
import type { ServerInit } from "@sveltejs/kit";
import { client } from "$lib/client/sdk.gen";
import { getAuthenticatedUser, validateToken } from "$lib/user.svelte";
import { addAirtableHits } from "$lib/airtable-hits.svelte";
// @ts-ignore
import { PUBLIC_API_URL } from "$env/static/public";
import { env } from "$env/dynamic/public";

// If you don't want to use Session Replay, remove the `Replay` integration,
// `replaysSessionSampleRate` and `replaysOnErrorSampleRate` options.
Sentry.init({
  dsn: env.PUBLIC_SENTRY_DSN,
  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 0.1,
  integrations: [
    Sentry.browserTracingIntegration(),
    Sentry.replayIntegration({
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],
  sendDefaultPii: false,
});

// Override global fetch to track Airtable API hits transparently
const originalFetch = globalThis.fetch;
globalThis.fetch = async (
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> => {
  const response = await originalFetch(input, init);

  // Check for Airtable hits header and add to store
  const airtableHits = response.headers.get("X-Airtable-Hits");
  if (airtableHits) {
    const hits = parseInt(airtableHits, 10);
    if (!isNaN(hits)) {
      addAirtableHits(hits);
    }
  }

  return response;
};

client.setConfig({
  baseUrl: PUBLIC_API_URL,
  credentials: "include",
  headers: {
    Authorization: `Bearer ${getAuthenticatedUser().access_token}`,
  },
  // Use throwOnError: false to get proper error handling with response codes
  // When using a conditional to check the err:
  // - For endpoints that return data: use `if (err || !data)` to check both error and null data
  // - For endpoints that don't return data (like POST create/update/delete): use `if (err)` to check only for errors
  throwOnError: false,
});
export const init: ServerInit = async () => {
  if (getAuthenticatedUser().access_token) {
    console.debug("User is already authenticated, checking token");
    await validateToken(getAuthenticatedUser().access_token);
    console.log("Finished auth");
  } else {
    console.debug("Checking HttpOnly auth cookie");
    await validateToken();
    console.log("Finished auth");
  }
};
export const handleError = Sentry.handleErrorWithSentry();
