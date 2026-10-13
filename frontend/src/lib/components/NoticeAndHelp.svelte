<script lang="ts">
  import { onMount } from "svelte";
  import Modal from "./Modal.svelte";

  let noticeVisible = $state(true);
  let helpModal: Modal = $state() as Modal;

  onMount(() => {
    // Check localStorage for notice preference
    const noticeHidden = localStorage.getItem("podium-notice-hidden");
    if (noticeHidden === "true") {
      noticeVisible = false;
    }
  });

  function dismissNotice() {
    noticeVisible = false;
    localStorage.setItem("podium-notice-hidden", "true");
  }

  function showHelp() {
    helpModal.openModal();
  }
</script>

<!-- Dismissible Notice -->
{#if noticeVisible}
  <div
    class="mx-auto mb-4 flex max-w-2xl items-center justify-center gap-2 rounded-full border border-info/40 bg-info/10 py-1.5 pl-4 pr-1.5 text-sm"
    id="help-notice"
  >
    <span class="text-base-content/80">Something not working? Ask an organiser for help.</span>
    <button
      onclick={dismissNotice}
      class="btn btn-xs btn-circle btn-ghost"
      aria-label="Dismiss notice"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  </div>
{/if}

<!-- Help Button -->
<div class="fixed bottom-4 right-4 z-50">
  <button
    class="btn btn-info btn-square btn-md font-serif font-light"
    aria-label="Help"
    onclick={showHelp}
  >
    ?
  </button>
</div>

<!-- Help Modal -->
<Modal bind:this={helpModal} title="About Podium">
  <p class="py-4">
    Podium is Kiwihacks's peer-judging platform for hackathons, based on the
    open-source Podium project.
  </p>
  <p class="py-2">
    <strong>Urgent Help:</strong> If Podium is not working and you need
    immediate assistance, ask an organiser for help.
  </p>
</Modal>
