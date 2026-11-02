import Link from "next/link";
import type { Company } from "@/lib/api";

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

export function CompanyCard({ company }: { company: Company }) {
  return (
    <Link
      href={`/company/${encodeURIComponent(company.company)}`}
      className="block rounded-xl border border-line bg-tile p-4 transition-colors hover:border-accent"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold">
            {company.company}
          </h3>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
            {company.country && (
              <span className="rounded-full bg-chip px-2 py-0.5 text-chipInk">
                {company.country}
              </span>
            )}
            <span>{company.exposed_ips.toLocaleString()} exposed hosts</span>
            {company.has_cert_identity && (
              <span className="rounded-full border border-line px-2 py-0.5">
                verified identity
              </span>
            )}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-2xl font-semibold text-accent">
            {company.priority.toFixed(0)}
          </div>
          <div className="text-xs text-faint">priority</div>
        </div>
      </div>

      {company.reasons[0] && (
        <p className="mt-3 rounded-lg bg-chip px-3 py-2 text-sm text-chipInk">
          {company.reasons[0]}
        </p>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3">
        <Bar label="Need" value={company.need_score} />
        <Bar label="Fit" value={company.fit_score} />
      </div>

      <ul className="mt-3 space-y-1">
        {company.reasons.slice(1).map((r) => (
          <li key={r} className="flex gap-2 text-sm text-muted">
            <span className="text-accent">-</span>
            <span>{r}</span>
          </li>
        ))}
      </ul>
    </Link>
  );
}
