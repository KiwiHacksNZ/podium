<script lang="ts">
  import { AI_CODE_LIMIT_PERCENT } from "$lib/misc";

  // Form section for events with require_ai_declaration on
  let {
    declaration = $bindable(""),
    underLimit = $bindable(null),
  }: {
    declaration?: string | null;
    underLimit?: boolean | null;
  } = $props();
</script>

<div class="rounded-box border border-base-content/15 bg-base-200/60 p-4 mt-4 flex flex-col gap-3">
  <div>
    <span class="font-semibold">AI Declaration</span>
    <p class="text-sm text-base-content/70">
      This event requires every team to declare their AI use. AI can't write more than
      {AI_CODE_LIMIT_PERCENT}% of your code.
    </p>
  </div>

  <fieldset class="flex flex-col gap-2">
    <legend class="label mb-1">Did AI write less than {AI_CODE_LIMIT_PERCENT}% of your code?</legend>
    <label class="flex items-center gap-2 cursor-pointer">
      <input type="radio" class="radio radio-sm radio-primary" name="ai_under_limit" value={true} bind:group={underLimit} />
      <span>Yes, under {AI_CODE_LIMIT_PERCENT}% (or no AI at all)</span>
    </label>
    <label class="flex items-center gap-2 cursor-pointer">
      <input type="radio" class="radio radio-sm radio-primary" name="ai_under_limit" value={false} bind:group={underLimit} />
      <span>No, AI wrote {AI_CODE_LIMIT_PERCENT}% or more</span>
    </label>
  </fieldset>

  <label class="label" for="ai_declaration">How did you use AI?</label>
  <textarea
    id="ai_declaration"
    bind:value={declaration}
    maxlength="1000"
    rows="3"
    placeholder="e.g. 'Copilot for autocomplete', 'ChatGPT to debug a CORS error'. Write 'None' if you didn't use any."
    class="textarea textarea-bordered w-full"
  ></textarea>
</div>
