<script lang="ts">
  import type { VoteAuditResponse } from "$lib/client/types.gen";
  import { formatDateTime } from "$lib/misc";

  interface Props {
    logs: VoteAuditResponse[];
    userLookup: Map<string, string>;
    projectLookup: Map<string, string>;
  }

  let { logs, userLookup, projectLookup }: Props = $props();
</script>

<div class="card bg-base-200">
  <div class="card-body">
    <h2 class="card-title">Vote Audit ({logs.length})</h2>

    {#if logs.length === 0}
      <p class="text-base-content/70">No vote audit entries yet.</p>
    {:else}
      <div class="overflow-x-auto">
        <table class="table table-zebra w-full">
          <thead>
            <tr>
              <th>Action</th>
              <th>Voter</th>
              <th>Project</th>
              <th>When</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            {#each logs as log}
              <tr>
                <td>
                  <span class="badge badge-outline">{log.action}</span>
                  {#if log.reason}
                    <div class="text-xs text-base-content/60">{log.reason}</div>
                  {/if}
                </td>
                <td>{userLookup.get(log.voter_id) || log.voter_id}</td>
                <td>{projectLookup.get(log.project_id) || log.project_id}</td>
                <td class="whitespace-nowrap text-xs">{formatDateTime(log.created_at)}</td>
                <td class="font-mono text-xs">{log.ip_address || "unknown"}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</div>
