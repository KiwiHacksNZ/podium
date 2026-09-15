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

  const criteria: { key: Criterion; name: string; question: string }[] = [
    {
      key: "originality",
      name: "Originality",
      question: "How distinct is the project from common projects?",
    },
    {
      key: "technicality",
      name: "Technicality",
      question: "How much effort did the builder put into the implementation?",
    },
    {
      key: "theme",
      name: "Theme",
      question: "How well does the project fit the event theme?",
    },
    {
      key: "usability",
      name: "Usability",
      question: "Did you like using it? Could you use it at all?",
    },
  ];

  const isJudge = $derived(
    Boolean(
      getAuthenticatedUser().user.judge_event_ids?.includes(data.event.id),
    ),
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
  const allScored = $derived(
    projects.length > 0 && scoredCount === projects.length,
  );
  // Once everything is graded the grading UI is replaced by a thank-you, unless
  // the judge asks to go back and change something.
  let reviewing = $state(false);

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

  /** Move to a project, saving a complete-but-unsaved score on the way out so a
      judge never loses grades by navigating. A partly filled score is left
      alone — skipping a project is allowed. */
  async function goTo(target: number) {
    if (target < 0 || target >= projects.length || target === index) return;
    if (complete && dirty && !(await persist(true))) return;
    index = target;
  }

  async function go(delta: number) {
    await goTo(index + delta);
  }

  async function pick(event: Event) {
    await goTo(Number((event.currentTarget as HTMLSelectElement).value));
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
{:else if allScored && !reviewing}
  <div class="container mx-auto max-w-3xl p-4 sm:p-6">
    <section
      class="rounded-box bg-success text-success-content p-8 text-center"
    >
      <span
        class="inline-flex items-center rounded-full bg-success-content text-success px-3 py-1 text-sm font-extrabold uppercase tracking-wide"
      >
        All done
      </span>
      <h1 class="mt-4 text-3xl sm:text-4xl font-extrabold">Thanks!</h1>
      <p class="mt-3 opacity-90">
        You have graded all {projects.length}
        {projects.length === 1 ? "project" : "projects"} for {data.event.name}.
        Your scores are saved — nothing else to do.
      </p>
      <button
        class="btn btn-sm mt-6 bg-success-content text-success border-none"
        onclick={() => (reviewing = true)}
      >
        Review my grades
      </button>
    </section>
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

    <!-- Judges rarely grade in list order — presenters run late, swap slots —
         so pick by name rather than stepping through. -->
    <label class="form-control">
      <span class="label-text font-semibold">Jump to a project</span>
      <select
        class="select select-bordered w-full mt-1"
        value={index}
        onchange={pick}
      >
        {#each projects as p, i}
          <option value={i}>
            {isScored(p.id) ? "✓" : "○"}
            {p.name}
          </option>
        {/each}
      </select>
    </label>

    <div class="card bg-base-200 rounded-box">
      {#if project.image_url}
        <figure class="w-full bg-base-300/60">
          <img
            src={project.image_url}
            alt={`${project.name} project`}
            class="max-h-96 w-full object-contain"
          />
        </figure>
      {/if}
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
        <section class="judge-criterion-card rounded-box p-5 sm:p-6">
          <span
            class="judge-criterion-pill inline-flex items-center rounded-full px-3 py-1 text-sm font-extrabold uppercase tracking-wide"
          >
            {criterion.name}
          </span>
          <div class="judge-criterion-rating mt-4 rounded-box px-4 py-3">
            <StarRating
              label={criterion.name}
              value={draft ? draft[criterion.key] : null}
              onchange={(v) => {
                if (draft) draft[criterion.key] = v;
              }}
            />
          </div>
          <p class="mt-3 text-sm font-medium opacity-80">
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
