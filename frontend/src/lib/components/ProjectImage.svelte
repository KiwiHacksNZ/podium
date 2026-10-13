<script lang="ts">
  import { hueFor, initials } from "$lib/misc";

  // A project's image, or a tile with its initials when there is none (or it
  // fails to load), so every project gets a recognisable picture.
  let {
    project,
    class: className = "",
    alt = "",
  }: {
    project: { id: string; name: string; image_url?: string | null };
    class?: string;
    alt?: string;
  } = $props();

  let failed = $state(false);
  const hue = $derived(hueFor(project.id));
</script>

{#if project.image_url && !failed}
  <img
    src={project.image_url}
    {alt}
    class="object-cover {className}"
    loading="lazy"
    onerror={() => (failed = true)}
  />
{:else}
  <div
    class="flex items-center justify-center overflow-hidden font-semibold text-white/90 select-none {className}"
    style="background: linear-gradient(135deg, oklch(0.55 0.13 {hue}), oklch(0.38 0.11 {(hue + 50) % 360})); container-type: size;"
    role={alt ? "img" : undefined}
    aria-label={alt || undefined}
    aria-hidden={alt ? undefined : "true"}
  >
    <span style="font-size: clamp(0.75rem, 35cqmin, 4rem);">{initials(project.name)}</span>
  </div>
{/if}
