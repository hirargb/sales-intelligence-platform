"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import type { Market } from "@/lib/api";

const SORTS = [
  { value: "priority", label: "Priority" },
  { value: "need_score", label: "Need" },
  { value: "fit_score", label: "Fit" },
  { value: "exposed_ips", label: "Surface size" },
  { value: "n_kev", label: "Known-exploited CVEs" },
];

export function FilterBar({ markets }: { markets: Market[] }) {
  const router = useRouter();
  const params = useSearchParams();

  const setParam = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(params.toString());
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      router.replace(`/?${next.toString()}`);
    },
    [params, router]
  );

  const control =
    "rounded-lg border border-line bg-panel px-3 py-2 text-sm text-ink";

  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1">
        <span className="text-xs text-faint">Market</span>
        <select
          className={control}
          defaultValue={params.get("market") ?? ""}
          onChange={(e) => setParam("market", e.target.value)}
        >
          <option value="">All markets</option>
          {markets.map((m) => (
            <option key={m.country} value={m.country}>
              {m.country} ({m.companies.toLocaleString()})
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs text-faint">Sort by</span>
        <select
          className={control}
          defaultValue={params.get("sort") ?? "priority"}
          onChange={(e) => setParam("sort", e.target.value)}
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs text-faint">Minimum need</span>
        <input
          className={control}
          type="number"
          min={0}
          max={100}
          step={5}
          defaultValue={params.get("min_need") ?? "0"}
          onChange={(e) => setParam("min_need", e.target.value)}
        />
      </label>

      <form
        className="flex flex-col gap-1"
        onSubmit={(e) => {
          e.preventDefault();
          const value = new FormData(e.currentTarget).get("q");
          setParam("q", typeof value === "string" ? value : "");
        }}
      >
        <span className="text-xs text-faint">Search company</span>
        <input
          name="q"
          className={control}
          type="search"
          placeholder="search name (fuzzy)..."
          defaultValue={params.get("q") ?? ""}
        />
      </form>

      <label className="flex items-center gap-2 py-2 text-sm text-muted">
        <input
          type="checkbox"
          defaultChecked={params.get("high_confidence") === "true"}
          onChange={(e) =>
            setParam("high_confidence", e.target.checked ? "true" : "")
          }
        />
        Verified identity only
      </label>
    </div>
  );
}
