import Link from "next/link";
import { ArrowUp, ArrowDown, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";
import { listRankings, listStates, getRankingsMeta } from "@/lib/api";
import Card from "@/app/components/Card";
import ConfidenceBadge from "@/app/components/ConfidenceBadge";

const SORT_COLUMNS: { key: string; label: string; align?: "right" }[] = [
  { key: "rank_national", label: "Rank" },
  { key: "district_name", label: "District" },
  { key: "state_name", label: "State" },
  { key: "opportunity_score", label: "Opportunity Score", align: "right" },
];

export default async function RankingsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; offset?: string; state_code?: string; sort?: string; direction?: string; show_all?: string }>;
}) {
  const params = await searchParams;
  const q = params.q ?? "";
  const offset = Number(params.offset ?? 0);
  const stateCode = params.state_code ? Number(params.state_code) : undefined;
  const sort = params.sort ?? "opportunity_score";
  const direction = params.direction === "asc" ? "asc" : "desc";
  const showAll = params.show_all === "1";
  const limit = 50;

  const [data, states, meta] = await Promise.all([
    listRankings({ q: q || undefined, state_code: stateCode, limit, offset, sort, direction, ranked_only: !showAll }),
    listStates(),
    getRankingsMeta(),
  ]);

  const sortedStates = [...states].sort((a, b) => a.state_name.localeCompare(b.state_name));
  const activeVersion = meta.active_versions.find((v) => v.profile_code === "balanced");

  function sortHref(column: string) {
    const nextDirection = sort === column && direction === "desc" ? "asc" : "desc";
    const sp = new URLSearchParams();
    if (q) sp.set("q", q);
    if (stateCode) sp.set("state_code", String(stateCode));
    if (showAll) sp.set("show_all", "1");
    sp.set("sort", column);
    sp.set("direction", nextDirection);
    return `/rankings?${sp.toString()}`;
  }

  function pageHref(nextOffset: number) {
    const sp = new URLSearchParams();
    if (q) sp.set("q", q);
    if (stateCode) sp.set("state_code", String(stateCode));
    if (showAll) sp.set("show_all", "1");
    sp.set("sort", sort);
    sp.set("direction", direction);
    sp.set("offset", String(nextOffset));
    return `/rankings?${sp.toString()}`;
  }

  function toggleShowAllHref() {
    const sp = new URLSearchParams();
    if (q) sp.set("q", q);
    if (stateCode) sp.set("state_code", String(stateCode));
    sp.set("sort", sort);
    sp.set("direction", direction);
    if (!showAll) sp.set("show_all", "1");
    return `/rankings?${sp.toString()}`;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Opportunity Score rankings</h1>
        <p className="mt-1 text-sm text-ink-secondary">
          {data.total.toLocaleString()} districts {showAll ? "" : "ranked (confidence ≥ 75%)"} · profile:{" "}
          <span className="font-medium text-ink">balanced</span>
          {activeVersion && <span className="text-ink-muted"> · weight version #{activeVersion.weight_version_id}</span>}
        </p>
      </div>

      <Card
        className="border-[#eda100]/30 bg-[#eda100]/5"
        title="Reduced-scope score — read before trusting a rank"
      >
        <p className="text-sm text-ink-secondary">{meta.scope_note}</p>
        <p className="mt-2 text-sm text-ink-secondary">
          Districts with fewer indicators present (confidence below 75%) are excluded from ranking by default —
          a rank built from 1 of 7 indicators is not a stable ranking, only a data point.{" "}
          <Link href={toggleShowAllHref()} className="font-medium text-accent hover:underline">
            {showAll ? "Hide unranked districts" : "Show all districts, including unranked"}
          </Link>
          .
        </p>
      </Card>

      <form className="flex flex-wrap gap-2" action="/rankings">
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
        {showAll && <input type="hidden" name="show_all" value="1" />}
        <input type="hidden" name="sort" value={sort} />
        <input type="hidden" name="direction" value={direction} />
        <button type="submit" className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90">
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
                <th className="px-5 py-2 text-left font-medium">95% rank CI</th>
                <th className="px-5 py-2 text-left font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((d) => (
                <tr key={d.lgd_district_code} className="border-b border-hairline/20 last:border-0 hover:bg-ink/[0.02]">
                  <td className="px-5 py-2 tabular-nums text-ink-secondary">
                    {d.rank_national ?? <span className="text-ink-muted">—</span>}
                  </td>
                  <td className="px-5 py-2 font-medium text-ink">
                    <Link href={`/districts/${d.lgd_district_code}`} className="hover:text-accent hover:underline">
                      {d.district_name}
                    </Link>
                  </td>
                  <td className="px-5 py-2 text-ink-secondary">{d.state_name}</td>
                  <td className="px-5 py-2 text-right tabular-nums font-medium text-ink">{d.opportunity_score.toFixed(1)}</td>
                  <td className="px-5 py-2 tabular-nums text-ink-muted">
                    {d.rank_ci_low && d.rank_ci_high ? `${d.rank_ci_low}–${d.rank_ci_high}` : "—"}
                  </td>
                  <td className="px-5 py-2">
                    <ConfidenceBadge band={d.confidence_band} score={d.confidence_score} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="flex items-center justify-between text-sm text-ink-secondary">
        <span>
          Showing {data.total === 0 ? 0 : offset + 1}-{Math.min(offset + limit, data.total)} of {data.total.toLocaleString()}
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
