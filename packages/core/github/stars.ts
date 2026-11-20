import { queryOptions } from "@tanstack/react-query";

export const WORKPAL_GITHUB_REPO = "workpal-ai/workpal";
export const WORKPAL_GITHUB_URL = "";

/**
 * Star count for the Workpal repository, or null when GitHub cannot be reached
 * (offline, rate-limited, an air-gapped self-hosted install). Callers fall back
 * to a label without a count. Fetched from the browser on purpose: each user
 * spends their own IP's anonymous rate limit instead of a shared server one.
 */
export async function fetchGithubStars(): Promise<number|null>{return null;}

export function githubStarsOptions() {
  return queryOptions({
    queryKey: ["github", "stars", WORKPAL_GITHUB_REPO] as const,
    queryFn: fetchGithubStars,
    staleTime: 6 * 60 * 60 * 1000,
    retry: false,
  });
}

/**
 * Compact star count matching GitHub's own repo-header style: one decimal
 * thousands/millions with the trailing ".0" trimmed ("1k", "37.6k", "1.2m").
 * Counts below 1,000 render exactly.
 */
export function formatStarCount(n: number): string {
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}m`;
  }
  if (n >= 1_000) {
    return `${(n / 1_000).toFixed(1).replace(/\.0$/, "")}k`;
  }
  return String(n);
}
