<script lang="ts">
  import AiDeclarationFields from "./AiDeclarationFields.svelte";
  import { EventsService, ProjectsService } from "$lib/client/sdk.gen";
  import type { EventPublic, ProjectPublic } from "$lib/client";
  import { toast } from "svelte-sonner";
  import { customInvalidateAll, handleError, withHttpsIfMissing } from "$lib/misc";
  import { asyncClick } from "$lib/actions/asyncClick";
  import type { ProjectPrivate, ProjectUpdate } from "$lib/client/types.gen";
  import { onMount } from "svelte";
  import Modal from "$lib/components/Modal.svelte";
  import ConfirmationModal from "$lib/components/ConfirmationModal.svelte";
  import { authHeaders } from "$lib/user.svelte";
  import { env } from "$env/dynamic/public";

  // let events: Event[] = $state([]);
  // let fetchedEvents = false;

  // async function fetchEvents() {
  //   try {
  //     toast("Fetching events; please wait");
  //     const { data: userEvents } =
  //       await EventsService.getAttendingEventsEventsGet({ throwOnError: true });
  //     events = userEvents.attending_events;
  //     fetchedEvents = true;
  //   } catch (err) {
  //     handleError(err);
  //   }
  // }

  let {
    preselectedProject,
    events,
    modal = $bindable(),
    onProjectUpdated,
  }: { preselectedProject: ProjectPrivate; events: Array<EventPublic>; modal?: Modal; onProjectUpdated?: () => void } = $props();

  let localModal: Modal = $state() as Modal;
  let deleteConfirmation: ConfirmationModal = $state() as ConfirmationModal;
  let imageUploading = $state(false);

  // Sync local modal to bindable prop
  $effect(() => {
    if (localModal) {
      modal = localModal;
    }
  });

  // Track the selected event's demo_links_optional setting
  let selectedEvent = $derived(
    events.find((e) => e.id === preselectedProject.event_id),
  );
  let demoLinksOptional = $derived(selectedEvent?.demo_links_optional || false);

  const emptyProjectUpdate: ProjectUpdate = {
    name: "",
    team_name: "",
    repo: "",
    image_url: "",
    demo: "",
    description: "",
    hours_spent: 0,
  };
  const emptyProject: ProjectPublic = {
    id: "",
    name: "",
    team_name: "",
    repo: "",
    image_url: "",
    demo: "",
    description: "",
    points: 0,
    owner_id: "",
    owner_display_name: "",
    collaborator_display_names: [],
  };
  // Derive           project = { ...chosenProject };
  let project: ProjectUpdate = $derived({ ...preselectedProject });
  $inspect(project);

  async function deleteProject() {
    const { error: err } =
      await ProjectsService.deleteProjectProjectsProjectIdDelete({
        path: { project_id: preselectedProject.id },
        throwOnError: false,
      });
    if (err) {
      handleError(err);
      return;
    }
    toast.success("Project deleted successfully");
    await customInvalidateAll();
    localModal.closeModal();
  }

  function confirmDeleteProject() {
    deleteConfirmation.open();
  }

  // onMount(() => {
  //   fetchEvents();
  // });

  async function updateProject(ship = false) {
    const payload: ProjectUpdate = {
      ...preselectedProject,
      ...(ship && { is_draft: false }),
      image_url: withHttpsIfMissing(preselectedProject.image_url),
      demo: withHttpsIfMissing(preselectedProject.demo),
      repo: withHttpsIfMissing(preselectedProject.repo),
    };

    Object.assign(preselectedProject, payload);

    const { error: err } =
      await ProjectsService.updateProjectProjectsProjectIdPut({
        path: { project_id: preselectedProject.id },
        body: payload,
        throwOnError: false,
      });
    if (err) {
      handleError(err);
      return;
    }
    toast.success(ship ? "Project shipped!" : "Project updated successfully");
    await customInvalidateAll();
    localModal.closeModal();
    onProjectUpdated?.();
  }

  async function uploadProjectImage(file: File | undefined) {
    if (!file) return;
    imageUploading = true;
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${env.PUBLIC_API_URL}/projects/image-upload`, {
        method: "POST",
        headers: authHeaders(),
        credentials: "include",
        body: formData,
      });
      const body = await response.json();
      if (!response.ok) {
        toast.error(body?.detail || "Image upload failed");
        return;
      }
      preselectedProject.image_url = body.url;
      toast.success("Image uploaded");
    } catch {
      toast.error("Image upload failed");
    } finally {
      imageUploading = false;
    }
  }
</script>

<Modal bind:this={localModal} title="Update Project">
  <div class="mx-auto w-full max-w-3xl px-2 py-3 sm:px-4 sm:py-4">
    <!-- <form onsubmit={updateProject} class="space-y-4"> -->
    <div class="space-y-4">
      <fieldset class="fieldset gap-3 p-4 sm:p-5">
        <label class="label" for="project_name">Project Name</label>
        <input
          id="project_name"
          type="text"
          bind:value={preselectedProject.name}
          placeholder="A really cool project!"
          class="input input-bordered w-full"
        />

        <label class="label" for="team_name">Team Name</label>
        <input
          id="team_name"
          type="text"
          maxlength="100"
          bind:value={preselectedProject.team_name}
          placeholder="Optional — judges use this to find you"
          class="input input-bordered w-full"
        />

        <label class="label" for="event">Event</label>
        <select
          id="event"
          bind:value={preselectedProject.event_id}
          class="select select-bordered w-full"
        >
          <option value="" disabled selected>Select an event</option>
          {#each events as event}
            <option value={event.id}>{event.name}</option>
          {/each}
        </select>

        <label class="label" for="project_description"
          >Project Description</label
        >
        <textarea
          id="project_description"
          bind:value={preselectedProject.description}
          placeholder="Some cool description"
          class="textarea textarea-bordered w-full"
        ></textarea>

        <label class="label" for="project_image">Project thumbnail</label>
        <input
          id="project_image"
          type="file"
          accept="image/*"
          class="file-input file-input-bordered w-full"
          disabled={imageUploading}
          onchange={(event) =>
            uploadProjectImage(event.currentTarget.files?.[0])}
        />
        {#if imageUploading}
          <div class="text-sm text-base-content/70 mt-1">Uploading image...</div>
        {/if}

        <label class="label" for="image_url">Image URL</label>
        <input
          id="image_url"
          type="text"
          bind:value={preselectedProject.image_url}
          placeholder="Image URL"
          class="input input-bordered w-full"
        />

        <label class="label" for="demo_url">
          Demo URL
          {#if demoLinksOptional}
            <span class="text-sm text-base-content/70"
              >(Optional for this event)</span
            >
          {/if}
        </label>
        <input
          id="demo_url"
          type="text"
          bind:value={preselectedProject.demo}
          placeholder="Demo URL"
          class="input input-bordered w-full"
        />
        {#if demoLinksOptional}
          <div class="text-sm text-base-content/70 mt-1">
            Demo links are optional for this event. Your project won't be marked
            as invalid if only the demo link fails validation.
          </div>
        {/if}

        <label class="label" for="repo_url">Repository URL</label>
        <input
          id="repo_url"
          type="text"
          bind:value={preselectedProject.repo}
          placeholder="Repository URL"
          class="input input-bordered w-full"
        />

        {#if selectedEvent?.require_ai_declaration}
          <AiDeclarationFields
            bind:declaration={preselectedProject.ai_declaration}
            bind:underLimit={preselectedProject.ai_under_limit}
          />
        {/if}

        <label class="label" for="hours_spent">Hours Spent</label>
        <input
          id="hours_spent"
          type="number"
          bind:value={preselectedProject.hours_spent}
          placeholder="Hours spent"
          class="input input-bordered w-full"
          min="0"
        />

        {#if preselectedProject.is_draft}
          <button class="btn btn-block mt-4 btn-accent" use:asyncClick={() => updateProject(true)}>
            Ship it!
          </button>
          <button class="btn btn-block mt-2 btn-outline" use:asyncClick={() => updateProject()}>
            Save draft
          </button>
        {:else}
          <button class="btn btn-block mt-4 btn-primary" use:asyncClick={() => updateProject()}>
            Update Project
          </button>
        {/if}
        <button
          class="btn btn-block mt-4 btn-warning"
          type="button"
          onclick={confirmDeleteProject}
        >
          Delete Project
        </button>
      </fieldset>
    </div>
    <!-- </form> -->
  </div>
</Modal>

<ConfirmationModal
  bind:this={deleteConfirmation}
  title="Delete Project"
  message="Are you sure you want to delete this project? This action cannot be undone."
  confirmText="Delete"
  cancelText="Cancel"
  confirmClass="btn-error"
  onConfirm={deleteProject}
  onCancel={() => {}}
/>
