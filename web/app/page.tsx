import { Suspense } from "react";
import { CompanyCard } from "@/components/CompanyCard";
import { FilterBar } from "@/components/FilterBar";
import { StatTiles } from "@/components/StatTiles";
import {
  getCompanies,
  getMarkets,
  getStats,
  type Company,
  type Market,
  type Stats,
} from "@/lib/api";

type SearchParams = { [key: string]: string | string[] | undefined };

function str(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function Page({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const query = {
    market: str(searchParams.market),
    q: str(searchParams.q),
    minNeed: Number(str(searchParams.min_need) ?? 0) || 0,
    highConfidence: str(searchParams.high_confidence) === "true",
    sort: str(searchParams.sort) ?? "priority",
    limit: 50,
  };

  let stats: Stats | null = null;
  let markets: Market[] = [];
  let items: Company[] = [];
  let total = 0;
  let error = "";

  try {
    const [s, m, c] = await Promise.all([
      getStats(),
      getMarkets(),
      getCompanies(query),
    ]);
    stats = s;
    markets = m;
    items = c.items;
    total = c.total;
  } catch (e) {
    console.error("API fetch failed:", e);
    error =
      "Cannot reach the API. Start the backend on port 8000, then reload.";
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">Sales Intelligence Platform</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          The companies most likely to need cybersecurity help, ranked from
          their exposed internet footprint, with the reason each one ranks.
        </p>
      </header>

      <StatTiles stats={stats} />

      <div className="mt-6 rounded-xl border border-line bg-panel p-4">
        <Suspense fallback={null}>
          <FilterBar markets={markets} />
        </Suspense>
      </div>

      {error ? (
        <p className="mt-8 rounded-xl border border-line bg-tile p-4 text-sm text-muted">
          {error}
        </p>
      ) : (
        <>
          <p className="mt-6 text-sm text-faint">
            {total.toLocaleString()} companies match. Showing the top{" "}
            {items.length}.
          </p>
          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
            {items.map((company) => (
              <CompanyCard key={company.company} company={company} />
            ))}
          </div>
        </>
      )}
    </main>
  );
}
