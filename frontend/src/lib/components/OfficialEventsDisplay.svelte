<script lang="ts">
  import type { EventPublic } from "$lib/client";
  import { eventStatus } from "$lib/misc";

  let {
    events = [],
    loading = false,
    error = false,
  }: {
    events: EventPublic[];
    loading?: boolean;
    error?: boolean;
  } = $props();

  const eventHeroImages: Record<string, string> = {
    kiwihacks: "/assets/kiwihacks/kiwi-logo.png",
  };

  function getEventHeroImage(event: EventPublic): string | undefined {
    const bySlug = eventHeroImages[event.slug];
    if (bySlug) return bySlug;

    if (event.name.toLowerCase().includes("kiwihacks")) {
      return eventHeroImages.kiwihacks;
    }

    return undefined;
  }
</script>

{#if loading}
  <div class="flex justify-center py-12">
    <span class="loading loading-spinner loading-lg text-primary"></span>
  </div>
{:else if error}
  <div class="alert alert-error">
    <span>Failed to load events. Please refresh the page.</span>
  </div>
{:else if events.length === 1}
  <div class="flex justify-center">
    <a
      href={`/events/${events[0].slug}`}
      class="official-event-card card bg-base-100 border border-base-300 shadow-sm hover:shadow-md hover:border-primary/30 transition-all group w-full max-w-lg"
    >
      {#if getEventHeroImage(events[0])}
        <figure class="px-10 pt-8 pb-2">
          <img
            src={getEventHeroImage(events[0])}
            alt={events[0].name}
            class="official-event-hero h-36 object-contain"
          />
        </figure>
      {/if}
      <div class="card-body gap-4 items-center text-center">
        <div class="flex flex-col items-center gap-2">
          <span class="badge {eventStatus(events[0]).badge} text-xs">
            {eventStatus(events[0]).label}
          </span>
          <h2 class="card-title text-2xl group-hover:text-primary transition-colors">
            {events[0].name}
          </h2>
        </div>
        {#if events[0].description}
          <p class="text-base-content/60 text-sm">{events[0].description}</p>
        {/if}
        <div class="card-actions mt-2">
          <span class="btn btn-primary btn-sm">View event →</span>
        </div>
      </div>
    </a>
  </div>
{:else if events.length > 1}
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {#each events as event (event.id)}
      <a
        href={`/events/${event.slug}`}
        class="official-event-card card bg-base-100 border border-base-300 shadow-sm hover:shadow-md hover:border-primary/30 transition-all group"
      >
        <div class="card-body gap-3">
          <div class="flex items-start justify-between gap-2">
            <h2 class="card-title text-base group-hover:text-primary transition-colors">
              {event.name}
            </h2>
            <span class="badge {eventStatus(event).badge} shrink-0 text-xs">
              {eventStatus(event).label}
            </span>
          </div>
          {#if event.description}
            <p class="text-base-content/60 text-sm line-clamp-2">
              {event.description}
            </p>
          {/if}
        </div>
      </a>
    {/each}
  </div>
{:else}
  <div class="card bg-base-100">
    <div class="card-body items-center gap-1 py-8 text-center">
      <p class="font-semibold">No events are running right now.</p>
      <p class="text-sm text-base-content/70">
        The next KiwiHacks will show up here. Until then,
        <a href="/past-events" class="link link-primary">see past results</a>.
      </p>
    </div>
  </div>
{/if}
