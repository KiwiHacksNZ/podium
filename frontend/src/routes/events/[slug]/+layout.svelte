<script lang="ts">
  import { page } from "$app/state";
  import EventStatus from "$lib/components/EventStatus.svelte";

  let { children, data } = $props();

  const eventHeroImages: Record<string, string> = {
    kiwihacks: "/assets/kiwihacks/kiwi-text.png",
  };

  const eventHeroImage = $derived.by(() => {
    const slugImage = eventHeroImages[data.event.slug];
    if (slugImage) return slugImage;
    if (data.event.name.toLowerCase().includes("kiwihacks")) {
      return eventHeroImages.kiwihacks;
    }
    return "";
  });

  // Only the event's main page gets the full hero; sub-pages (showcase,
  // ballot, judging, leaderboard) keep a compact header so content is above the fold
  const isEventHome = $derived(page.url.pathname.replace(/\/$/, "") === `/events/${data.event.slug}`);
</script>

{#if isEventHome}
  {#if eventHeroImage}
    <div class="flex justify-center pt-6 pb-2">
      <img src={eventHeroImage} alt={data.event.name} class="h-20 sm:h-28 object-contain" />
    </div>
  {/if}

  <div class="text-center p-4 space-y-2">
    <h1 class="text-2xl sm:text-3xl font-semibold">{data.event.name}</h1>
    {#if data.event.description}
      <p class="mono text-base-content/80">{data.event.description}</p>
    {/if}
    <EventStatus event={data.event} />
  </div>
{:else}
  <div class="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 pt-4 pb-2">
    <a href="/events/{data.event.slug}" class="link link-hover text-sm font-semibold text-base-content/80">
      &larr; {data.event.name}
    </a>
    <EventStatus event={data.event} />
  </div>
{/if}

{@render children()}
