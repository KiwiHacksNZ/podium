<script lang="ts">
  import { onMount } from "svelte";
  import { client } from "$lib/client/sdk.gen";
  import { env } from "$env/dynamic/public";
  import { authHeaders, getAuthenticatedUser, isAuthenticated } from "$lib/user.svelte";
  import type { EventPrivate, ProjectPrivate } from "$lib/client/types.gen";
  import { toast } from "svelte-sonner";
  import { formatDate } from "$lib/misc";

  type Page<T> = { items: T[]; total: number; page: number; size: number; pages: number };

  let eventsPage = $state<Page<EventPrivate>>({ items: [], total: 0, page: 1, size: 25, pages: 0 });
  let loading = $state(true);
  let loadingProjectsEventId = $state<string | null>(null);
  let expandedEventId = $state<string | null>(null);
  let deletingProjectId = $state<string | null>(null);
  let exportingEventId = $state<string | null>(null);
  let projectsByEvent = $state<Record<string, ProjectPrivate[]>>({});

  function hasPermission(permission: string): boolean {
    const user = getAuthenticatedUser().user;
    if (user.is_superadmin) return true;
    return !!user.admin_permissions?.includes(permission);
  }

  const canViewEvents = $derived(hasPermission("view_all_events"));
  const canExportCsv = $derived(hasPermission("export_projects_csv"));
  const canRemoveProjects = $derived(hasPermission("remove_projects"));

  async function loadEvents(page = eventsPage.page) {
    if (!canViewEvents) {
      loading = false;
      return;
    }

    const { data, error } = await client.get<Page<EventPrivate>, unknown>({
      url: "/admin/events",
      query: { page, size: 25 },
      throwOnError: false,
    });

    if (error) {
      toast.error("Failed to load events");
      return;
    }

    if (data) eventsPage = data;
  }

  async function toggleProjects(event: EventPrivate) {
    if (expandedEventId === event.id) {
      expandedEventId = null;
      return;
    }

    expandedEventId = event.id;
    if (projectsByEvent[event.id]) return;

    loadingProjectsEventId = event.id;
    try {
      const { data, error } = await client.get<ProjectPrivate[], unknown>({
        url: `/admin/events/${event.id}/projects`,
        throwOnError: false,
      });

      if (error || !data) {
        toast.error("Failed to load event projects");
        return;
      }

      projectsByEvent[event.id] = data;
    } finally {
      loadingProjectsEventId = null;
    }
  }

  async function deleteProject(project: ProjectPrivate, event: EventPrivate) {
    if (!canRemoveProjects) return;
    if (!confirm(`Delete project "${project.name}" from ${event.name}?`)) return;

    deletingProjectId = project.id;
    try {
      const { error } = await client.delete<unknown, unknown>({
        url: `/admin/projects/${project.id}`,
        throwOnError: false,
      });

      if (error) {
        toast.error("Failed to delete project");
        return;
      }

      projectsByEvent[event.id] = (projectsByEvent[event.id] || []).filter(
        (p) => p.id !== project.id,
      );
      toast.success("Project deleted");
    } finally {
      deletingProjectId = null;
    }
  }

  async function exportProjectsCsv(event: EventPrivate) {
    if (!canExportCsv) return;

    if (!isAuthenticated()) {
      toast.error("You must be signed in to export");
      return;
    }

    exportingEventId = event.id;
    try {
      const response = await fetch(`${env.PUBLIC_API_URL}/admin/events/${event.id}/projects/csv`, {
        headers: { ...authHeaders(), "ngrok-skip-browser-warning": "hi" },
        credentials: "include",
      });

      if (!response.ok) {
        toast.error("Failed to export projects CSV");
        return;
      }

      const disposition = response.headers.get("content-disposition") ?? "";
      const match = disposition.match(/filename="?([^"]+)"?/i);
      const filename =
        match?.[1] ??
        `podium_projects_${event.slug}_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(`Projects CSV downloaded for ${event.name}`);
    } catch (err) {
      console.error("Failed to export projects CSV", err);
      toast.error("Failed to export projects CSV");
    } finally {
      exportingEventId = null;
    }
  }

  onMount(async () => {
    await loadEvents(1);
    loading = false;
  });
</script>

<div class="max-w-6xl mx-auto space-y-6">
  <h1 class="text-3xl font-bold">Admin</h1>

  {#if !canViewEvents}
    <div class="alert alert-warning">
      <span>Your account is missing the <code>view_all_events</code> admin permission.</span>
    </div>
  {:else}
    <div class="card bg-base-100 shadow-lg">
      <div class="card-body">
        <h2 class="card-title">All Events</h2>

        {#if loading}
          <span class="loading loading-spinner loading-md"></span>
        {:else if eventsPage.total === 0}
          <p class="text-base-content/70">No events.</p>
        {:else}
          <div class="overflow-x-auto">
            <table class="table table-zebra w-full">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phase</th>
                  <th>Owner</th>
                  <th>Deleted</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {#each eventsPage.items as event (event.id)}
                  <tr class={event.deleted_at ? "opacity-50" : ""}>
                    <td>
                      {#if !event.deleted_at}
                        <a href="/events/{event.slug}" class="link link-primary font-medium">{event.name}</a>
                      {:else}
                        <span class="line-through">{event.name}</span>
                      {/if}
                    </td>
                    <td><span class="badge">{event.phase}</span></td>
                    <td class="font-mono text-xs">{event.owner_id}</td>
                    <td>{formatDate(event.deleted_at)}</td>
                    <td class="flex gap-2">
                      <button class="btn btn-outline btn-xs" onclick={() => toggleProjects(event)}>
                        {expandedEventId === event.id ? "Hide Projects" : "Projects"}
                      </button>
                      {#if canExportCsv}
                        <button
                          class="btn btn-outline btn-xs"
                          onclick={() => exportProjectsCsv(event)}
                          disabled={exportingEventId !== null}
                        >
                          {exportingEventId === event.id ? "Exporting…" : "Export CSV"}
                        </button>
                      {/if}
                    </td>
                  </tr>
                  {#if expandedEventId === event.id}
                    <tr>
                      <td colspan="5">
                        {#if loadingProjectsEventId === event.id}
                          <span class="loading loading-spinner loading-sm"></span>
                        {:else}
                          {@const projects = projectsByEvent[event.id] || []}
                          {#if projects.length === 0}
                            <p class="text-sm text-base-content/70 py-2">No projects for this event.</p>
                          {:else}
                            <div class="overflow-x-auto">
                              <table class="table table-sm w-full">
                                <thead>
                                  <tr><th>Name</th><th>Owner</th><th>Points</th><th></th></tr>
                                </thead>
                                <tbody>
                                  {#each projects as project (project.id)}
                                    <tr>
                                      <td>{project.name}</td>
                                      <td>{project.owner_display_name}</td>
                                      <td>{project.points}</td>
                                      <td>
                                        {#if canRemoveProjects}
                                          <button
                                            class="btn btn-error btn-xs"
                                            onclick={() => deleteProject(project, event)}
                                            disabled={deletingProjectId !== null}
                                          >
                                            {deletingProjectId === project.id ? "Deleting…" : "Delete"}
                                          </button>
                                        {/if}
                                      </td>
                                    </tr>
                                  {/each}
                                </tbody>
                              </table>
                            </div>
                          {/if}
                        {/if}
                      </td>
                    </tr>
                  {/if}
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>
