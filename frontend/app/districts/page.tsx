import Link from "next/link";
import { ArrowUp, ArrowDown, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";
import { listDistricts, listStates } from "@/lib/api";
import Card from "@/app/components/Card";

const SORT_COLUMNS: { key: string; label: string; align?: "right" }[] = [
  { key: "district_name", label: "District" },
  { key: "state_name", label: "State" },
  { key: "company_count", label: "Companies", align: "right" },
  { key: "active_company_count", label: "Active", align: "right" },
];

export default async function DistrictsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; offset?: string; state_code?: string; sort?: string; direction?: string }>;
}) {
  const params = await searchParams;
  const q = params.q ?? "";
  const offset = Number(params.offset ?? 0);
  const stateCode = params.state_code ? Number(params.state_code) : undefined;
  const sort = params.sort ?? "company_count";
  const direction = params.direction === "asc" ? "asc" : "desc";
  const limit = 50;

  const [data, states] = await Promise.all([
    listDistricts({ q: q || undefined, state_code: stateCode, limit, offset, sort, direction }),
    listStates(),
  ]);

  const sortedStates = [...states].sort((a, b) => a.state_name.localeCompare(b.state_name));
  const maxCompanyCount = Math.max(1, ...data.items.map((d) => d.company_count ?? 0));

  function sortHref(column: string) {
    const nextDirection = sort === column && direction === "desc" ? "asc" : "desc";
    const sp = new URLSearchParams();
    if (q) sp.set("q", q);
    if (stateCode) sp.set("state_code", String(stateCode));
    sp.set("sort", column);
    sp.set("direction", nextDirection);
    return `/districts?${sp.toString()}`;
  }

  function pageHref(nextOffset: number) {
    const sp = new URLSearchParams();
    if (q) sp.set("q", q);
    if (stateCode) sp.set("state_code", String(stateCode));
    sp.set("sort", sort);
    sp.set("direction", direction);
    sp.set("offset", String(nextOffset));
    return `/districts?${sp.toString()}`;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Districts</h1>
        <p className="mt-1 text-sm text-ink-secondary">
          {data.total.toLocaleString()} districts nationally · sorted by {sort.replace("_", " ")} (
          {direction === "desc" ? "high to low" : "low to high"})
        </p>
      </div>

      <form className="flex flex-wrap gap-2" action="/districts">
        <input
          type="text"
          name="q"
          defaultValue={q}
          placeholder="Search district name..."
          className="w-full max-w-xs rounded-md border border-hairline bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-accent focus:outline-none"
        />
        <select
          name="state_code"
          defaultValue={stateCode ?? ""}
          className="rounded-md border border-hairline bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
        >
          <option value="">All states</option>
          {sortedStates.map((s) => (
            <option key={s.lgd_state_code} value={s.lgd_state_code}>
              {s.state_name}
            </option>
          ))}
        </select>
        <input type="hidden" name="sort" value={sort} />
        <input type="hidden" name="direction" value={direction} />
        <button
          type="submit"
          className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          Apply
        </button>
      </form>

      <Card padded={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline/40 text-left text-ink-muted">
                {SORT_COLUMNS.map((col) => {
                  const active = sort === col.key;
                  return (
                    <th key={col.key} className={`px-5 py-2 font-medium ${col.align === "right" ? "text-right" : ""}`}>
                      <Link
                        href={sortHref(col.key)}
                        className={`inline-flex items-center gap-1 hover:text-ink ${active ? "text-ink" : ""} ${col.align === "right" ? "flex-row-reverse" : ""}`}
                      >
                        {col.label}
                        {active ? (
                          direction === "desc" ? (
                            <ArrowDown size={12} strokeWidth={2.5} className="text-accent" />
                          ) : (
                            <ArrowUp size={12} strokeWidth={2.5} className="text-accent" />
                          )
                        ) : (
                          <ArrowUpDown size={12} strokeWidth={2} className="text-ink-muted/60" />
                        )}
                      </Link>
                    </th>
                  );
                })}
                <th className="px-5 py-2 text-right font-medium">MSME (micro)</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((d) => {
                const barPct = Math.max(2, ((d.company_count ?? 0) / maxCompanyCount) * 100);
                return (
                  <tr key={d.lgd_district_code} className="border-b border-hairline/20 last:border-0 hover:bg-ink/[0.02]">
                    <td className="px-5 py-2 font-medium text-ink">
                      <Link href={`/districts/${d.lgd_district_code}`} className="hover:text-accent hover:underline">
                        {d.district_name}
                      </Link>
                    </td>
                    <td className="px-5 py-2 text-ink-secondary">{d.state_name}</td>
                    <td className="px-5 py-2">
                      <div className="flex items-center justify-end gap-2">
                        <div className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-accent/10 sm:block">
                          <div className="h-full rounded-full bg-accent/50" style={{ width: `${barPct}%` }} />
                        </div>
                        <span className="tabular-nums text-ink-secondary">
                          {d.company_count?.toLocaleString() ?? 0}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-2 text-right tabular-nums text-ink-secondary">
                      {d.active_company_count?.toLocaleString() ?? 0}
                    </td>
                    <td className="px-5 py-2 text-right tabular-nums text-ink-secondary">
                      {d.msme_micro?.toLocaleString() ?? "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="flex items-center justify-between text-sm text-ink-secondary">
        <span>
          Showing {data.total === 0 ? 0 : offset + 1}-{Math.min(offset + limit, data.total)} of{" "}
          {data.total.toLocaleString()}
        </span>
        <div className="flex gap-4">
          {offset > 0 && (
            <Link href={pageHref(Math.max(0, offset - limit))} className="inline-flex items-center gap-1 hover:text-ink hover:underline">
              <ChevronLeft size={14} strokeWidth={2} />
              Previous
            </Link>
          )}
          {offset + limit < data.total && (
            <Link href={pageHref(offset + limit)} className="inline-flex items-center gap-1 hover:text-ink hover:underline">
              Next
              <ChevronRight size={14} strokeWidth={2} />
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
