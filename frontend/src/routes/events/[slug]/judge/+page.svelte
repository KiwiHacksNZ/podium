<svelte:options runes />

<script lang="ts">
  import { toast } from "svelte-sonner";
  import { client } from "$lib/client/sdk.gen";
  import StarRating from "$lib/components/StarRating.svelte";
  import { handleError, withHttpsIfMissing } from "$lib/misc";
  import { asyncClick } from "$lib/actions/asyncClick";
  import { getAuthenticatedUser } from "$lib/user.svelte";

  const { data } = $props();

  type JudgeScore = {
    originality: number;
    technicality: number;
    theme: number;
    usability: number;
    total: number;
    updated_at: string;
  };
  type JudgeProject = (typeof data.projects)[number];

  type Criterion = "originality" | "technicality" | "theme" | "usability";
  type Draft = Record<Criterion, number | null>;

  const criteria: {
    key: Criterion;
    name: string;
    question: string;
    card: string;
    pill: string;
    inset: string;
    helper: string;
  }[] = [
    {
      key: "originality",
      name: "Originality",
      question: "How distinct is the project from common projects?",
      card: "bg-rose-600 text-white",
      pill: "bg-rose-50 text-rose-700",
      inset: "bg-black/15 text-white",
      helper: "text-rose-50/90",
    },
    {
      key: "technicality",
      name: "Technicality",
      question:
        "How much effort did the builder put into the implementation?",
      card: "bg-amber-400 text-amber-950",
      pill: "bg-amber-950 text-amber-50",
      inset: "bg-amber-900/15 text-amber-950",
      helper: "text-amber-950/80",
    },
    {
      key: "theme",
      name: "Theme",
      question: "How well does the project fit the event theme?",
      card: "bg-emerald-600 text-white",
      pill: "bg-emerald-50 text-emerald-700",
      inset: "bg-black/15 text-white",
      helper: "text-emerald-50/90",
    },
    {
      key: "usability",
      name: "Usability",
      question: "Did you like using it? Could you use it at all?",
      card: "bg-sky-600 text-white",
      pill: "bg-sky-50 text-sky-700",
      inset: "bg-black/15 text-white",
      helper: "text-sky-50/90",
    },
  ];

  const isJudge = $derived(
    Boolean(getAuthenticatedUser().user.judge_event_ids?.includes(data.event.id)),
  );

  // Snapshot on mount: a fresh load remounts the page, so this never goes stale.
  // svelte-ignore state_referenced_locally
  const projects: JudgeProject[] = data.projects;

  function toDraft(score: JudgeScore | null): Draft {
    return {
      originality: score?.originality ?? null,
      technicality: score?.technicality ?? null,
      theme: score?.theme ?? null,
      usability: score?.usability ?? null,
    };
  }

  let drafts = $state<Record<string, Draft>>(
    Object.fromEntries(projects.map((p) => [p.id, toDraft(p.my_score)])),
  );
  let stored = $state<Record<string, Draft>>(
    Object.fromEntries(projects.map((p) => [p.id, toDraft(p.my_score)])),
  );
  let index = $state(0);

  const project = $derived(projects[index]);
  const draft = $derived(project ? drafts[project.id] : undefined);

  function isComplete(d: Draft | undefined): boolean {
    if (!d) return false;
    return criteria.every((c) => d[c.key] !== null);
  }

  function isScored(projectId: string): boolean {
    return isComplete(stored[projectId]);
  }

  const complete = $derived(isComplete(draft));
  const dirty = $derived(
    Boolean(
      draft && criteria.some((c) => draft[c.key] !== stored[project.id][c.key]),
    ),
  );
  const scoredCount = $derived(projects.filter((p) => isScored(p.id)).length);

  /** Returns false if the score could not be stored. `silent` suppresses the
      toast, used when saving happens as a side effect of navigating. */
  async function persist(silent: boolean): Promise<boolean> {
    if (!project || !draft) return false;
    if (!complete) {
      if (!silent) toast.error("Set all four criteria before saving");
      return false;
    }
    const { error: saveError } = await client.put<JudgeScore, unknown>({
      url: `/judging/${data.event.id}/scores/${project.id}`,
      body: {
        originality: draft.originality,
        technicality: draft.technicality,
        theme: draft.theme,
        usability: draft.usability,
      },
      throwOnError: false,
    });
    if (saveError) {
      handleError(saveError);
      return false;
    }
    stored[project.id] = { ...draft };
    if (!silent) toast.success(`Saved your grades for ${project.name}`);
    return true;
  }

  async function save() {
    await persist(false);
  }

  /** Move between projects, saving a complete-but-unsaved score on the way out
      so a judge never loses grades by tapping Next. A partly filled score is
      left alone — skipping a project is allowed. */
  async function go(delta: number) {
    const target = index + delta;
    if (target < 0 || target >= projects.length) return;
    if (complete && dirty && !(await persist(true))) return;
    index = target;
  }
</script>

{#if !isJudge}
  <div role="alert" class="alert alert-warning max-w-2xl mx-auto mt-6">
    <span>
      Judging access is required to grade projects for this event. If your
      organizer gave you a 6-digit judge code, <a class="link" href="/judge"
        >enter it here</a
      >.
    </span>
  </div>
{:else if projects.length === 0}
  <div role="alert" class="alert alert-info max-w-2xl mx-auto mt-6">
    <span>There are no projects to judge yet. Check back later.</span>
  </div>
{:else}
  <div class="container mx-auto max-w-3xl p-4 sm:p-6 flex flex-col gap-6">
    <header class="flex flex-col gap-2">
      <p class="text-sm font-semibold opacity-70">
        {data.event.name} · {scoredCount} of {projects.length} scored
      </p>
      <h1 class="text-3xl sm:text-4xl font-extrabold">Your grades</h1>
      <h2 class="text-xl sm:text-2xl font-bold break-words">{project.name}</h2>
      {#if project.owner_display_name}
        <p class="text-sm opacity-70">by {project.owner_display_name}</p>
      {/if}
    </header>

    <!-- Progress strip: jump to any project, filled means fully scored -->
    <div class="flex flex-wrap gap-2">
      {#each projects as p, i}
        <button
          type="button"
          class="btn btn-xs {i === index
            ? 'btn-primary'
            : isScored(p.id)
              ? 'btn-success'
              : 'btn-ghost border border-base-300'}"
          aria-current={i === index ? "true" : undefined}
          aria-label={`Project ${i + 1}: ${p.name}${isScored(p.id) ? " (scored)" : ""}`}
          onclick={() => (index = i)}
        >
          {i + 1}
        </button>
      {/each}
    </div>

    <div class="card bg-base-200 rounded-box">
      <div class="card-body gap-3">
        {#if project.description}
          <p class="break-words text-sm">{project.description}</p>
        {/if}
        <div class="flex flex-wrap gap-2">
          {#if project.repo}
            <a
              class="btn btn-secondary btn-sm"
              href={withHttpsIfMissing(project.repo)}
              target="_blank"
              rel="noopener">Repo</a
            >
          {/if}
          {#if project.demo}
            <a
              class="btn btn-primary btn-sm"
              href={withHttpsIfMissing(project.demo)}
              target="_blank"
              rel="noopener">Demo</a
            >
          {/if}
        </div>
      </div>
    </div>

    <div class="flex flex-col gap-4">
      {#each criteria as criterion (criterion.key)}
        <section class="rounded-box p-5 sm:p-6 {criterion.card}">
          <span
            class="inline-flex items-center rounded-full px-3 py-1 text-sm font-extrabold uppercase tracking-wide {criterion.pill}"
          >
            {criterion.name}
          </span>
          <div class="mt-4 rounded-box px-4 py-3 {criterion.inset}">
            <StarRating
              label={criterion.name}
              value={draft ? draft[criterion.key] : null}
              onchange={(v) => {
                if (draft) draft[criterion.key] = v;
              }}
            />
          </div>
          <p class="mt-3 text-sm font-medium {criterion.helper}">
            {criterion.question}
          </p>
        </section>
      {/each}
    </div>

    <div class="flex flex-wrap items-center justify-between gap-3">
      <span class="text-sm font-semibold opacity-70">
        Project {index + 1} of {projects.length}
      </span>
      {#if !complete}
        <span class="badge badge-warning">Score all four criteria</span>
      {:else if dirty}
        <span class="badge badge-warning">Unsaved changes</span>
      {:else}
        <span class="badge badge-success">Saved</span>
      {/if}
    </div>

    <button
      class="btn btn-primary btn-block"
      disabled={!complete || !dirty}
      use:asyncClick={save}>Save score</button
    >

    <div class="join grid grid-cols-2">
      <button
        class="btn join-item"
        disabled={index === 0}
        use:asyncClick={() => go(-1)}>Previous</button
      >
      <button
        class="btn join-item"
        disabled={index >= projects.length - 1}
        use:asyncClick={() => go(1)}>Next</button
      >
    </div>
  </div>
{/if}
