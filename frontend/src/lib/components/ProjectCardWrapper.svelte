<script lang="ts">
  import UpdateProjectModal from "./UpdateProjectModal.svelte";
  import Modal from "./Modal.svelte";
  import type { EventPrivate, EventPublic, ProjectPrivate } from "$lib/client/types.gen";
  import { validateProject } from "$lib/validation";
  import { customInvalidateAll } from "$lib/misc";
  import TeamMembers from "./TeamMembers.svelte";
  import { toast } from "svelte-sonner";
  import { client } from "$lib/client/sdk.gen";
  import { getAuthenticatedUser } from "$lib/user.svelte";

  interface Props {
    project: ProjectPrivate;
    events: Array<EventPrivate | EventPublic>;
  }

  let { project, events }: Props = $props();

  let editModal = $state<Modal>();
  let validationModal = $state<Modal>();
  let revalidating = $state(false);
  let imageReady = $state(false);
  let imageFailed = $state(false);
  let teamBusy = $state(false);

  // The API includes the event name; fall back to the attending list
  const eventForProject = $derived(events.find((event) => event.id === project.event_id));
  const eventName = $derived(project.event_name || eventForProject?.name || "");
  const eventSlug = $derived(project.event_slug || eventForProject?.slug || "");


  const collaboratorEntries = $derived.by(() => {
    const ids = project.collaborator_ids ?? [];
    const names = project.collaborator_display_names ?? [];
    return ids.map((id, index) => ({
      id,
      name: names[index] || id,
    }));
  });

  const isOwner = $derived(project.owner_id === getAuthenticatedUser().user.id);
  const currentCollaborator = $derived(
    collaboratorEntries.find((collaborator) => collaborator.id === getAuthenticatedUser().user.id)
  );

  const statusBadge = $derived(
    project.is_draft
      ? { cls: "badge-ghost", label: "Draft" }
      : project.validation_status === "valid"
      ? { cls: "badge-success", label: "Valid" }
      : project.validation_status === "warning"
        ? { cls: "badge-warning", label: "Check links" }
        : { cls: "badge-neutral", label: "Checking" }
  );

  async function triggerRevalidation() {
    revalidating = true;
    try {
      await validateProject(project.id);
      await new Promise((resolve) => setTimeout(resolve, 1500));
      await customInvalidateAll();
    } finally {
      revalidating = false;
    }
  }

  async function copyJoinCode() {
    try {
      await navigator.clipboard.writeText(project.join_code);
      toast.success("Join code copied");
    } catch (err) {
      console.error("Failed to copy join code", err);
      toast.error("Could not copy join code");
    }
  }

  async function copyInviteLink() {
    const path = `/projects/join?join_code=${encodeURIComponent(project.join_code)}`;
    const inviteUrl = new URL(path, window.location.origin).toString();
    try {
      await navigator.clipboard.writeText(inviteUrl);
      toast.success("Invite link copied");
    } catch (err) {
      console.error("Failed to copy invite link", err);
      toast.error("Could not copy invite link");
    }
  }

  async function removeCollaborator(userId: string) {
    teamBusy = true;
    try {
      const { error } = await client.delete({
        url: `/projects/${project.id}/collaborators/${userId}`,
      });
      if (error) {
        toast.error(typeof error === "string" ? error : "Could not update team");
        return;
      }
      toast.success(userId === getAuthenticatedUser().user.id ? "Left project" : "Collaborator removed");
      await customInvalidateAll();
    } finally {
      teamBusy = false;
    }
  }

  async function transferOwner(userId: string) {
    teamBusy = true;
    try {
      const { error } = await client.post({
        url: `/projects/${project.id}/transfer-owner`,
        body: { new_owner_id: userId },
      });
      if (error) {
        toast.error(typeof error === "string" ? error : "Could not transfer owner");
        return;
      }
      toast.success("Owner transferred");
      await customInvalidateAll();
    } finally {
      teamBusy = false;
    }
  }
</script>

<article class="card h-full overflow-hidden border border-base-content/10 bg-base-100 shadow-sm">
  <figure class="relative bg-base-200">
    {#if project.image_url && !imageFailed}
      <img
        src={project.image_url}
        alt={project.name}
        class="aspect-[3/2] w-full object-cover"
        loading="lazy"
        onload={() => (imageReady = true)}
        onerror={() => {
          imageReady = true;
          imageFailed = true;
        }}
        style={`opacity: ${imageReady ? 1 : 0}; transition: opacity 180ms ease;`}
      />
      {#if !imageReady}
        <div class="skeleton absolute inset-0"></div>
      {/if}
    {:else}
      <div class="flex aspect-[3/2] w-full items-center justify-center text-sm text-base-content/50">
        No image
      </div>
    {/if}
    {#if revalidating}
      <span class="badge badge-neutral absolute left-3 top-3">
        <span class="loading loading-dots loading-xs"></span>
      </span>
    {:else}
      <button
        type="button"
        class={`badge absolute left-3 top-3 ${statusBadge.cls}`}
        onclick={() => validationModal?.openModal()}
        title="Validation details"
      >
        {statusBadge.label}
      </button>
    {/if}
  </figure>

  <div class="card-body gap-3 p-5">
    <div>
      {#if eventName}
        <a
          href={`/events/${eventSlug}`}
          class="link link-hover text-sm text-base-content/60"
          data-sveltekit-noscroll
        >
          {eventName}
        </a>
      {/if}
      <h2 class="card-title break-words text-xl leading-tight">{project.name}</h2>
      <TeamMembers {project} class="mt-0.5" />
    </div>

    <p class="line-clamp-2 text-sm text-base-content/75">
      {project.description || "No description yet."}
    </p>

    <div class="flex flex-wrap items-center gap-2 rounded-box bg-base-200 px-3 py-2 text-sm">
      <span class="text-base-content/60">Join code</span>
      <button
        type="button"
        class="font-mono font-semibold tracking-wider"
        onclick={copyJoinCode}
        title="Copy join code"
      >
        {project.join_code}
      </button>
      <button type="button" class="link link-hover ml-auto text-sm" onclick={copyInviteLink}>
        Copy invite link
      </button>
    </div>

    <div class="card-actions mt-1 grid grid-cols-3 gap-2">
      {#if project.repo}
        <a href={project.repo} target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-secondary">
          Repo
        </a>
      {:else}
        <span class="btn btn-sm btn-disabled">Repo</span>
      {/if}
      {#if project.demo}
        <a href={project.demo} target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-primary">
          Demo
        </a>
      {:else}
        <span class="btn btn-sm btn-disabled">Demo</span>
      {/if}
      <button class="btn btn-sm btn-outline" onclick={() => editModal?.openModal()}>
        {project.is_draft ? "Finish & ship" : "Edit"}
      </button>
    </div>

    {#if (isOwner || currentCollaborator) && collaboratorEntries.length > 0}
      <div class="border-t border-base-content/10 pt-3">
        <p class="text-sm font-semibold text-base-content/70">Team</p>
        <div class="mt-2 space-y-2">
          {#each collaboratorEntries as collaborator}
            <div class="flex items-center justify-between gap-2">
              <span class="min-w-0 truncate text-sm">{collaborator.name}</span>
              <div class="flex shrink-0 gap-1">
                {#if isOwner}
                  <button
                    class="btn btn-xs btn-ghost"
                    onclick={() => transferOwner(collaborator.id)}
                    disabled={teamBusy}
                  >
                    Make owner
                  </button>
                {/if}
                {#if isOwner || collaborator.id === currentCollaborator?.id}
                  <button
                    class="btn btn-xs btn-ghost text-error"
                    onclick={() => removeCollaborator(collaborator.id)}
                    disabled={teamBusy}
                  >
                    {collaborator.id === currentCollaborator?.id ? "Leave" : "Remove"}
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {:else if isOwner}
      <p class="text-xs text-base-content/50">No teammates yet. Share the invite link to add them.</p>
    {/if}
  </div>
</article>

<Modal title="Validation Details" bind:this={validationModal}>
  <div class="space-y-4">
    <div class="flex items-center gap-2 mb-2">
      {#if project.is_draft}
        <span class="text-base-content/70 text-lg">Draft — hidden from judges and voting until you ship it.</span>
      {:else if project.validation_status === "valid"}
        <span class="text-success text-lg">Your project looks good</span>
      {:else if project.validation_status === "warning"}
        <span class="text-warning text-lg">Potential issue detected</span>
      {:else}
        <span class="text-base-content/70 text-lg">Validation pending…</span>
      {/if}
    </div>
    {#if project.validation_message}
      <p class="text-sm text-base-content/70">{project.validation_message}</p>
    {/if}
    <p class="text-xs text-base-content/50">
      Validation warnings are informational - your project is never blocked.
    </p>
    {#if !project.is_draft}
      <button
        class="btn btn-sm btn-outline"
        onclick={triggerRevalidation}
        disabled={revalidating}
      >
        {revalidating ? "Re-validating…" : "Re-validate"}
      </button>
    {/if}
  </div>
</Modal>

<UpdateProjectModal preselectedProject={project} {events} bind:modal={editModal} />
