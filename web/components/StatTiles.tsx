import type { Stats } from "@/lib/api";

export function StatTiles({ stats }: { stats: Stats | null }) {
  const tiles = [
    { label: "Ranked companies", value: stats?.companies, hero: true },
    { label: "Markets", value: stats?.markets, hero: false },
    {
      label: "High-confidence identities",
      value: stats?.high_confidence,
      hero: false,
    },
  ];
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {tiles.map((t) => (
        <div
          key={t.label}
          className="rounded-xl border border-line bg-tile px-4 py-4"
        >
          <div
            className={`text-2xl ${t.hero ? "font-bold" : "font-semibold"}`}
          >
            {t.value === undefined ? "--" : t.value.toLocaleString()}
          </div>
          <div className="mt-1 text-sm text-muted">{t.label}</div>
        </div>
      ))}
    </div>
  );
}
