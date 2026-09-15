import type { HTTPValidationError } from "$lib/client/types.gen";
import { toast } from "svelte-sonner";
import { lightTheme, darkTheme, loadingTextOptions } from "$lib/consts";
import { invalidate, invalidateAll } from "$app/navigation";
import { getAuthenticatedUser, validateToken } from "./user.svelte";

const themeModeStorageKey = "theme-mode";

type ErrorWithDetail = {
  detail: string;
};

export function handleError(
  error: HTTPValidationError | ErrorWithDetail | Error | unknown,
) {
  console.error("Error", error);
  if (error && typeof error === "object") {
    if ("error" in error && typeof (error as any).error === "string") {
      const msg = (error as any).error as string;
      if (msg.toLowerCase().includes("rate limit")) {
        toast.error("Too many requests. Please wait a moment and try again.");
        return;
      }
    }
    if ("detail" in error) {
      if (Array.isArray(error?.detail)) {
        const invalidFields = (error as any).detail.map(
          (e: any) => `${e.loc.join(".")}: ${e.msg}`,
        );
        toast.error(invalidFields.join(" | "));
      } else if (typeof (error as any)?.detail === "string") {
        const detail = (error as any).detail as string;
        if (detail.toLowerCase().includes("rate limit")) {
          toast.error("Too many requests. Please wait a moment and try again.");
        } else {
          toast.error(detail);
        }
      }
      return;
    }
  }
  if (error instanceof Error) {
    toast.error(error.message);
  } else {
    toast.error("An error occurred, check the console for more details");
  }
}

function applySystemTheme() {
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
    document.documentElement.setAttribute("data-theme", darkTheme);
  } else {
    document.documentElement.setAttribute("data-theme", lightTheme);
  }
}

export function applyStoredTheme() {
  const storedTheme = localStorage.getItem("theme");
  if (storedTheme) {
    document.documentElement.setAttribute("data-theme", storedTheme);
    return;
  }
  if (localStorage.getItem(themeModeStorageKey) === "system") {
    applySystemTheme();
    return;
  }
  // Nova is the active series, so new visitors start in its brand theme.
  // A saved manual choice or explicit system mode still takes precedence.
  document.documentElement.setAttribute("data-theme", darkTheme);
}

export function setSystemTheme() {
  localStorage.setItem(themeModeStorageKey, "system");
  localStorage.removeItem("theme");
  applySystemTheme();
}

export function setManualTheme(theme: string) {
  localStorage.removeItem(themeModeStorageKey);
  localStorage.setItem("theme", theme);
  document.documentElement.setAttribute("data-theme", theme);
}

export function returnLoadingText(): string {
  return loadingTextOptions[
    Math.floor(Math.random() * loadingTextOptions.length)
  ];
}

export async function invalidateEvents() {
  await invalidate((url) => url.pathname.startsWith("/events"));
}
export async function invalidateProjects() {
  await invalidate((url) => url.pathname.startsWith("/projects"));
}

/**
 * Reload the user's data.
 * This does not actually call a load function but rather re-requests user data by checking the token again.
 */
export function invalidateUser(): Promise<void> {
  return validateToken(getAuthenticatedUser().access_token);
}

/**
 * Custom invalidate all function that also invalidates the user data.
 */
export async function customInvalidateAll() {
  await invalidateAll();
  await invalidateUser();
}

const URL_SCHEME_REGEX = /^[a-z][a-z\d+\-.]*:\/\//i;

/**
 * Make pasted host/path links usable by adding https:// when scheme is missing.
 */
export function withHttpsIfMissing(url: string | null | undefined): string {
  const trimmed = (url ?? "").trim();
  if (!trimmed) return "";
  if (trimmed.startsWith("//")) return `https:${trimmed}`;
  if (URL_SCHEME_REGEX.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

/**
 * Dates read as dd/mm/yy everywhere, not whatever the viewer's browser locale
 * defaults to — a US-defaulted browser renders 03/04 as April 3rd, which is the
 * wrong day for everyone here. The explicit numeric options pin the order, so
 * the locale tag alone is not doing the work.
 */
const DATE_PARTS = {
  day: "2-digit",
  month: "2-digit",
  year: "2-digit",
} as const;

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-NZ", DATE_PARTS);
}

export function formatDateTime(
  value: string | Date | null | undefined,
): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-NZ", {
    ...DATE_PARTS,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}
