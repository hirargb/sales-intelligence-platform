"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import type { Market } from "@/lib/api";
import { Select } from "@/components/Select";

const SORTS = [
  { value: "priority", label: "Priority" },
  { value: "need_score", label: "Need" },
  { value: "fit_score", label: "Fit" },
  { value: "exposed_ips", label: "Surface size" },
  { value: "n_kev", label: "Known-exploited CVEs" },
];

const SIZES = [
  { value: "", label: "Any surface" },
  { value: "small", label: "Small (2-9 hosts)" },
  { value: "medium", label: "Medium (10-49)" },
  { value: "large", label: "Large (50-199)" },
  { value: "xlarge", label: "Very large (200+)" },
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
    "rounded-lg border border-line bg-tile px-3 py-2 text-sm text-ink";

  const marketOptions = [
    { value: "", label: "All markets" },
    ...markets.map((m) => ({
      value: m.country,
      label: `${m.country} (${m.companies.toLocaleString()})`,
    })),
  ];

  return (
    <div className="flex flex-wrap items-end gap-3">
      <Select
        label="Market"
        value={params.get("market") ?? ""}
        options={marketOptions}
        onChange={(v) => setParam("market", v)}
      />

      <Select
        label="Surface size"
        value={params.get("size") ?? ""}
        options={SIZES}
        onChange={(v) => setParam("size", v)}
      />

      <Select
        label="Sort by"
        value={params.get("sort") ?? "priority"}
        options={SORTS}
        onChange={(v) => setParam("sort", v)}
      />

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
