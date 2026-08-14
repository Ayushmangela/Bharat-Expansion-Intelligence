import { getOverview } from "@/lib/api";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4">
      <div className="text-sm text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

export default async function OverviewPage() {
  const data = await getOverview();

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold">National Overview</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Raw ingested data as loaded so far — this is a preview slice, not the scored/SHAP
          Opportunity Score product (Phase 3/4 haven&apos;t run yet). See{" "}
          <code className="rounded bg-zinc-100 px-1">STATUS.md</code> for what&apos;s real vs. simplified.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Companies loaded" value={data.total_companies.toLocaleString()} />
        <StatCard label="States covered" value={data.states_covered} />
        <StatCard label="Districts with data" value={`${data.districts_with_data} / ${data.total_districts}`} />
        <StatCard label="Quarantined rows" value={data.quarantined_rows.toLocaleString()} />
        <StatCard
          label="National sweep"
          value={`${data.states_covered}/36 states`}
        />
      </div>

      <section>
        <h2 className="text-lg font-semibold">Top 10 districts by company count</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Not a ranking — just raw registered-company counts. Metro/state-capital districts
          dominate here partly because registered office ≠ operating location (see CLAUDE.md §9).
          This is exactly why the real product normalises per-capita rather than showing raw counts.
        </p>
        <div className="mt-4 overflow-x-auto rounded-lg border border-zinc-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-zinc-500">
                <th className="px-4 py-2 font-medium">#</th>
                <th className="px-4 py-2 font-medium">District</th>
                <th className="px-4 py-2 font-medium">State</th>
                <th className="px-4 py-2 font-medium text-right">Companies</th>
              </tr>
            </thead>
            <tbody>
              {data.top_districts_by_company_count.map((d, i) => (
                <tr key={`${d.state_name}-${d.district_name}`} className="border-b border-zinc-100 last:border-0">
                  <td className="px-4 py-2 text-zinc-400">{i + 1}</td>
                  <td className="px-4 py-2 font-medium">{d.district_name}</td>
                  <td className="px-4 py-2 text-zinc-600">{d.state_name}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{d.company_count.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold">Recent ingestion runs</h2>
        <div className="mt-4 overflow-x-auto rounded-lg border border-zinc-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-zinc-500">
                <th className="px-4 py-2 font-medium">Source</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium text-right">Fetched</th>
                <th className="px-4 py-2 font-medium text-right">Loaded</th>
                <th className="px-4 py-2 font-medium text-right">Quarantined</th>
                <th className="px-4 py-2 font-medium">Started</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_ingestion_runs.map((r, i) => (
                <tr key={i} className="border-b border-zinc-100 last:border-0">
                  <td className="px-4 py-2 font-mono text-xs">{r.source}</td>
                  <td className="px-4 py-2">
                    <span
                      className={
                        r.status === "success"
                          ? "rounded bg-green-100 px-2 py-0.5 text-xs text-green-700"
                          : "rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-700"
                      }
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">{r.rows_fetched?.toLocaleString() ?? "—"}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{r.rows_loaded?.toLocaleString() ?? "—"}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{r.rows_quarantined?.toLocaleString() ?? "—"}</td>
                  <td className="px-4 py-2 text-zinc-500">{new Date(r.started_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
