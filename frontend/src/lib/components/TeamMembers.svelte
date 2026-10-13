<script lang="ts">
  import { memberNames, teamLabel } from "$lib/misc";

  // Team name, then its members on the line below. Used wherever a project is shown.
  let {
    project,
    class: className = "",
  }: {
    project: {
      team_name?: string | null;
      owner_display_name?: string | null;
      collaborator_display_names?: string[] | null;
      member_names?: string[] | null;
    };
    class?: string;
  } = $props();

  const team = $derived(teamLabel(project.team_name));
  const members = $derived(memberNames(project));
</script>

{#if team || members}
  <div class="leading-snug {className}">
    {#if team}
      <p class="text-sm font-semibold text-base-content/80">{team}</p>
    {/if}
    {#if members}
      <p class="text-sm text-base-content/60">{members}</p>
    {/if}
  </div>
{/if}
