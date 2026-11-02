import Link from "next/link";
import { getCompany } from "@/lib/api";

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-faint">
        <span>{label}</span>
        <span>{value.toFixed(0)}</span>
      </div>
      <div className="mt-1 h-1.5 w-full rounded-full bg-line">
        <div
          className="h-1.5 rounded-full bg-accent"
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-line bg-tile px-3 py-3">
      <div className="text-lg font-semibold">{value}</div>
      <div className="mt-0.5 text-xs text-muted">{label}</div>
    </div>
  );
}

export default async function CompanyPage({
  params,
}: {
  params: { name: string };
}) {
  const name = decodeURIComponent(params.name);
  const company = await getCompany(name).catch(() => null);

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <Link href="/" className="text-sm text-accent">
        &larr; Back to the ranked list
      </Link>

      {!company ? (
        <p className="mt-6 rounded-xl border border-line bg-tile p-4 text-sm text-muted">
          No company found for &quot;{name}&quot;.
        </p>
      ) : (
        <>
          <header className="mt-4 flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="truncate text-2xl font-semibold">
                {company.company}
              </h1>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
                {company.country && (
                  <span className="rounded-full bg-chip px-2 py-0.5 text-chipInk">
                    {company.country}
                  </span>
                )}
                {company.has_cert_identity && (
                  <span className="rounded-full border border-line px-2 py-0.5">
                    verified identity
                  </span>
                )}
                <span>
                  {company.exposed_ips.toLocaleString()} exposed hosts across{" "}
                  {company.distinct_ports} ports
                </span>
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-3xl font-bold text-accent">
                {company.priority.toFixed(0)}
              </div>
              <div className="text-xs text-faint">priority</div>
            </div>
          </header>

          <div className="mt-6 grid grid-cols-2 gap-3">
            <Bar label="Need" value={company.need_score} />
            <Bar label="Fit" value={company.fit_score} />
          </div>

          <h2 className="mt-8 text-sm font-semibold">Why it ranks</h2>
          <ul className="mt-2 space-y-1">
            {company.reasons.map((r) => (
              <li key={r} className="flex gap-2 text-sm text-muted">
                <span className="text-accent">-</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>

          <h2 className="mt-8 text-sm font-semibold">Exposure</h2>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Metric label="Exposed hosts" value={company.exposed_ips.toLocaleString()} />
            <Metric label="Distinct ports" value={company.distinct_ports} />
            <Metric label="Known-exploited CVEs" value={company.n_kev} />
            <Metric label="Worst CVSS" value={company.worst_cvss.toFixed(1)} />
            <Metric label="Databases exposed" value={company.n_db} />
            <Metric label="Remote desktop" value={company.n_remote} />
            <Metric label="Legacy services" value={company.n_legacy} />
            <Metric label="End-of-life software" value={company.n_eol} />
            <Metric label="Flagged compromised" value={company.n_compromised} />
          </div>
        </>
      )}
    </main>
  );
}
