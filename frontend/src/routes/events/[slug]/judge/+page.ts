import { error } from "@sveltejs/kit";
import type { PageLoad } from "./$types";
import { client } from "$lib/client/sdk.gen";

export type JudgeScore = {
  originality: number;
  technicality: number;
  theme: number;
  usability: number;
  total: number;
  updated_at: string;
};

export type JudgeProject = {
  id: string;
  name: string;
  repo?: string | null;
  demo?: string | null;
  description?: string | null;
  image_url?: string | null;
  owner_display_name?: string | null;
  my_score: JudgeScore | null;
};

export const load: PageLoad = async ({ fetch, parent }) => {
  client.setConfig({ fetch });
  const { event } = await parent();

  if (!event.judging_open) {
    throw error(404, "Judging is not open for this event");
  }

  const {
    data,
    error: projectsError,
    response,
  } = await client.get<{ projects: JudgeProject[] }, unknown>({
    url: `/judging/${event.id}/projects`,
    throwOnError: false,
  });

  // Let the page render the "judging access required" alert instead of an error screen
  if (response?.status === 403) {
    return { projects: [] as JudgeProject[], forbidden: true };
  }

  if (projectsError || !data) {
    console.error(projectsError, response);
    throw error(response?.status ?? 500, "Failed to load projects to judge");
  }

  return { projects: data.projects, forbidden: false };
};
