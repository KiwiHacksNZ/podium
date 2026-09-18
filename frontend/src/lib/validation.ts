import { client } from "./client/sdk.gen";

/**
 * Regex for itch.io URL validation
 */
export function isValidItchUrl(url: string): boolean {
  const regex = /^(https?:\/\/)?[a-zA-Z0-9\-_]+\.itch\.io\/[a-zA-Z0-9\-_]+/;
  return regex.test(url?.trim() || "");
}

/**
 * Hosts the backend can existence-check via a public API. Keep in sync with
 * CHECKED_HOSTS in backend/podium/validators/repo.py.
 */
const CHECKED_HOSTS = ["github.com", "gitlab.com", "codeberg.org", "bitbucket.org"];

function repoHostAndPath(url: string): { host: string; segments: string[] } | null {
  const value = url?.trim() || "";
  if (!value) return null;
  try {
    const parsed = new URL(value.includes("://") ? value : `https://${value}`);
    const host = parsed.hostname.toLowerCase().replace(/^www\./, "");
    const path = parsed.pathname.split("/-/")[0];
    return { host, segments: path.split("/").filter(Boolean) };
  } catch {
    return null;
  }
}

/**
 * Whether a URL plausibly names a repository.
 *
 * Deliberately permissive about the host: teams use self-hosted Gitea, Replit
 * and more, and the backend accepts anything it can't check rather than
 * flagging a working submission. Only the shape is warned about here.
 */
export function isValidRepoUrl(url: string): boolean {
  const parsed = repoHostAndPath(url);
  if (!parsed) return false;
  return parsed.segments.length >= 2;
}

/**
 * Git repo URL validation for a known host, or another host containing "git"
 */
export function isValidGitUrl(url: string): boolean {
  const parsed = repoHostAndPath(url);
  if (!parsed) return false;
  return (
    (CHECKED_HOSTS.includes(parsed.host) || parsed.host.includes("git")) &&
    parsed.segments.length >= 2
  );
}

import type { ValidationResult } from "$lib/client/types.gen";
export type { ValidationResult };

/**
 * Queues background validation for a project.
 * Calls POST /projects/validate
 */
export async function validateProject(
  projectId: string,
): Promise<ValidationResult> {
  try {
    const response = await client.post<ValidationResult>({
      url: "/projects/validate",
      query: { project_id: projectId },
    });

    if (response.error || !response.data) {
      return {
        valid: false,
        message: "Validation request failed. Please try again.",
      };
    }

    return {
      valid: response.data.valid,
      message: response.data.message,
    };
  } catch (err) {
    console.error("Validation error:", err);
    return {
      valid: false,
      message: "Validation request failed. Please try again.",
    };
  }
}
