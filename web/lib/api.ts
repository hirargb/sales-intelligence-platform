// The API is called only from Server Components, so a server-side runtime
// variable works and avoids baking the URL in at build time. NEXT_PUBLIC_API_URL
// stays as a fallback for local development.
const BASE =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Company = {
  company: string;
  need_score: number;
  fit_score: number;
  priority: number;
  country: string | null;
  exposed_ips: number;
  distinct_ports: number;
  n_kev: number;
  worst_cvss: number;
  n_db: number;
  n_remote: number;
  n_legacy: number;
  n_eol: number;
  n_compromised: number;
  has_cert_identity: boolean;
  reasons: string[];
};

export type Stats = {
  companies: number;
  markets: number;
  high_confidence: number;
};

export type Market = { country: string; companies: number };

export type CompanyQuery = {
  market?: string;
  q?: string;
  minNeed?: number;
  highConfidence?: boolean;
  size?: string;
  sort?: string;
  limit?: number;
  offset?: number;
};

async function getJSON<T>(path: string): Promise<T> {
  // Server Components fetch fresh on each request; no client-side caching.
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export function getStats() {
  return getJSON<Stats>("/api/stats");
}

export function getMarkets() {
  return getJSON<Market[]>("/api/markets");
}

export async function getCompany(name: string): Promise<Company | null> {
  const res = await fetch(
    `${BASE}/api/company?name=${encodeURIComponent(name)}`,
    { cache: "no-store" }
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return (await res.json()) as Company;
}

export function getCompanies(query: CompanyQuery) {
  const p = new URLSearchParams();
  if (query.market) p.set("market", query.market);
  if (query.q) p.set("q", query.q);
  if (query.minNeed) p.set("min_need", String(query.minNeed));
  if (query.highConfidence) p.set("high_confidence", "true");
  if (query.size) p.set("size", query.size);
  if (query.sort) p.set("sort", query.sort);
  p.set("limit", String(query.limit ?? 50));
  p.set("offset", String(query.offset ?? 0));
  return getJSON<{ total: number; items: Company[] }>(
    `/api/companies?${p.toString()}`
  );
}
