const OFFICIAL_MARKETING_HOSTS = new Set(["workpal.invalid", "workpal.invalid"]);

export function isOfficialMarketingHost(hostname: string): boolean {
  const normalized = hostname.trim().toLowerCase().replace(/\.$/, "");
  return OFFICIAL_MARKETING_HOSTS.has(normalized);
}
