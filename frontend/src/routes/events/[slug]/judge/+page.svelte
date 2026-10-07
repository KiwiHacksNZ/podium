<svelte:options runes />

<script lang="ts">
  import { onMount } from "svelte";
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

  // Seeded from the load, then topped up by polling: projects submitted after a
  // judge opened this page must still reach them, or they go unscored.
  // svelte-ignore state_referenced_locally
  let projects = $state<JudgeProject[]>(data.projects);

  function toDraft(score: JudgeScore | null): Draft {
    return {
      originality: score?.originality ?? null,
      technicality: score?.technicality ?? null,
      theme: score?.theme ?? null,
      usability: score?.usability ?? null,
    };
  }

  // Seeded once; refreshProjects() adds entries for projects that arrive later.
  // svelte-ignore state_referenced_locally
  let drafts = $state<Record<string, Draft>>(
    Object.fromEntries(projects.map((p) => [p.id, toDraft(p.my_score)])),
  );
  // svelte-ignore state_referenced_locally
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

  let saving = $state(false);
  let saveFailed = $state(false);

  /** Returns false if the score could not be stored. `silent` suppresses the
      success toast, used for autosave and saving on navigation. */
  async function persist(target: JudgeProject, silent: boolean): Promise<boolean> {
    const d = drafts[target.id];
    if (!isComplete(d)) {
      if (!silent) toast.error("Set all four criteria before saving");
      return false;
    }
    const sent = { ...d };
    saving = true;
    const { error: saveError } = await client.put<JudgeScore, unknown>({
      url: `/judging/${data.event.id}/scores/${target.id}`,
      body: sent,
      throwOnError: false,
    });
    saving = false;
    if (saveError) {
      saveFailed = true;
      handleError(saveError);
      return false;
    }
    saveFailed = false;
    stored[target.id] = sent;
    if (!silent) toast.success(`Saved your grades for ${target.name}`);
    return true;
  }

  async function save() {
    if (project) await persist(project, false);
  }

  // Autosave: once all four criteria are set, any change is saved shortly after
  // the judge stops tapping, so there is no Save step to forget.
  let autosaveTimer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    if (!project || !complete || !dirty) return;
    const target = project;
    // Read every criterion so the effect re-runs on each tap.
    criteria.forEach((c) => draft?.[c.key]);
    clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(() => {
      // Stay on the grading screen: jumping to "Thanks!" mid-tap would yank the
      // judge away while they're still adjusting the last project.
      reviewing = true;
      persist(target, true);
    }, 600);
    return () => clearTimeout(autosaveTimer);
  });

  async function refreshProjects() {
    const { data: fresh, response } = await client.get<
      { projects: JudgeProject[] },
      unknown
    >({ url: `/judging/${data.event.id}/projects`, throwOnError: false });
    // Judging closed or access revoked: nothing more will arrive.
    if (response?.status === 403) return;
    if (!fresh) return;
    const known = new Set(projects.map((p) => p.id));
    const added = fresh.projects.filter((p) => !known.has(p.id));
    if (added.length === 0) return;
    for (const p of added) {
      drafts[p.id] = toDraft(p.my_score);
      stored[p.id] = toDraft(p.my_score);
    }
    // Append rather than re-sort so the project on screen keeps its index.
    projects = [...projects, ...added];
    toast.info(
      `${added.length} new project${added.length === 1 ? "" : "s"} to judge`,
    );
  }
  onMount(() => {
    const poll = setInterval(refreshProjects, 20_000);
    return () => clearInterval(poll);
  });

  /** Jump straight to a project from the review list. */
  async function edit(projectId: string) {
    reviewing = true;
    await goTo(projects.findIndex((p) => p.id === projectId));
  }

  /** Move to a project, saving a complete-but-unsaved score on the way out so a
      judge never loses grades by navigating. A partly filled score is left
      alone — skipping a project is allowed. */
  async function goTo(target: number) {
    if (target < 0 || target >= projects.length || target === index) return;
    if (project && complete && dirty) {
      clearTimeout(autosaveTimer);
      if (!(await persist(project, true))) return;
    }
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
    </section>

    <section class="mt-6 rounded-box bg-base-200 p-5 sm:p-6">
      <h2 class="text-xl font-extrabold">Change a grade</h2>
      <p class="mt-1 text-sm opacity-70">
        Tap a project to edit it. Changes save automatically.
      </p>
      <ul class="mt-4 flex flex-col gap-2">
        {#each projects as p (p.id)}
          <li>
            <button
              type="button"
              class="btn btn-block justify-between h-auto py-3 normal-case"
              onclick={() => edit(p.id)}
            >
              <span class="font-bold text-left break-words">{p.name}</span>
              <span class="flex items-center gap-3 whitespace-nowrap">
                {#if stored[p.id]}
                  <span class="opacity-70"
                    >{criteria.reduce((sum, c) => sum + (stored[p.id][c.key] ?? 0), 0)}/40</span
                  >
                {/if}
                <span class="link link-primary">Edit</span>
              </span>
            </button>
          </li>
        {/each}
      </ul>
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
      {:else if dirty || saving}
        <span class="badge badge-info">Saving…</span>
      {:else}
        <span class="badge badge-success">Saved</span>
      {/if}
    </div>

    {#if allScored}
      <button
        class="btn btn-success btn-block"
        onclick={() => (reviewing = false)}>All scored — finish</button
      >
    {/if}

    <p class="text-xs opacity-70 -mt-3">
      Grades save automatically once all four are set. You can come back and
      change them any time while judging is open.
    </p>
    <!-- Manual fallback if an autosave failed (e.g. flaky venue wifi). -->
    {#if saveFailed && complete && dirty && !saving}
      <button class="btn btn-primary btn-block" use:asyncClick={save}
        >Retry save</button
      >
    {/if}

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
