import Link from "next/link";
import { getOverview, listStates } from "@/lib/api";
import { Building2, MapPinned, Globe2, AlertTriangle } from "lucide-react";
import TopDistrictsChart from "@/app/components/TopDistrictsChart";
import StateChoropleth from "@/app/components/StateChoropleth";
import Card from "@/app/components/Card";
import StatTile from "@/app/components/StatTile";
import MeterTile from "@/app/components/MeterTile";

export default async function OverviewPage() {
  const [data, states] = await Promise.all([getOverview(), listStates()]);
  const rankedStates = [...states].sort((a, b) => b.company_count - a.company_count);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold text-ink">National Overview</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-secondary">
          Raw ingested data, nationally complete for MCA/Udyam/Census. The scored{" "}
          <Link href="/rankings" className="font-medium text-accent hover:underline">
            Opportunity Score rankings
          </Link>{" "}
          are live (7 of 22 documented indicators — SHAP explanation is Phase 4, not yet built). See{" "}
          <code className="rounded bg-ink/5 px-1 py-0.5 text-xs">STATUS.md</code> for what&apos;s real vs.
          simplified.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile
          label="Companies loaded"
          value={data.total_companies.toLocaleString()}
          icon={<Building2 size={16} strokeWidth={2} />}
          hint="MCA registered-company records, all statuses"
          emphasis
        />
        <MeterTile
          label="Districts with data"
          value={data.districts_with_data}
          max={data.total_districts}
          formattedValue={`${data.districts_with_data.toLocaleString()} / ${data.total_districts.toLocaleString()}`}
          icon={<MapPinned size={16} strokeWidth={2} />}
        />
        <MeterTile
          label="National sweep"
          value={data.states_covered}
          max={36}
          formattedValue={`${data.states_covered} / 36 states`}
          icon={<Globe2 size={16} strokeWidth={2} />}
        />
        <StatTile
          label="Quarantined rows"
          value={data.quarantined_rows.toLocaleString()}
          icon={<AlertTriangle size={16} strokeWidth={2} />}
          hint="Unresolved geography — held for review, not discarded"
          tone="warning"
        />
      </div>

      <Card
        title="Companies by state"
        subtitle="Sequential shading by registered-company count · gray = state/UT not yet ingested. States are inherited-geometry approximations for display only — the backend joins on LGD codes, never state-name strings."
      >
        <StateChoropleth states={states} />
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <Card
          title="Top 10 districts by company count"
          subtitle="Not a ranking — raw registered-company counts. Metro/state-capital districts dominate partly because registered office ≠ operating location (CLAUDE.md §9)."
          className="xl:col-span-3"
        >
          <TopDistrictsChart districts={data.top_districts_by_company_count} />
        </Card>

        <Card title="States by company count" padded={false} className="xl:col-span-2">
          <div className="max-h-[420px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface">
                <tr className="border-b border-hairline/40 text-left text-ink-muted">
                  <th className="px-5 py-2 font-medium">#</th>
                  <th className="px-5 py-2 font-medium">State / UT</th>
                  <th className="px-5 py-2 text-right font-medium">Companies</th>
                </tr>
              </thead>
              <tbody>
                {rankedStates.map((s, i) => (
                  <tr key={s.lgd_state_code} className="border-b border-hairline/20 last:border-0">
                    <td className="px-5 py-2 text-ink-muted">{i + 1}</td>
                    <td className="px-5 py-2 font-medium text-ink">{s.state_name}</td>
                    <td className="px-5 py-2 text-right tabular-nums text-ink-secondary">
                      {s.company_count > 0 ? s.company_count.toLocaleString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card title="Top 10 districts — detail" padded={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline/40 text-left text-ink-muted">
                <th className="px-5 py-2 font-medium">#</th>
                <th className="px-5 py-2 font-medium">District</th>
                <th className="px-5 py-2 font-medium">State</th>
                <th className="px-5 py-2 text-right font-medium">Companies</th>
              </tr>
            </thead>
            <tbody>
              {data.top_districts_by_company_count.map((d, i) => (
                <tr key={`${d.state_name}-${d.district_name}`} className="border-b border-hairline/20 last:border-0">
                  <td className="px-5 py-2 text-ink-muted">{i + 1}</td>
                  <td className="px-5 py-2 font-medium text-ink">{d.district_name}</td>
                  <td className="px-5 py-2 text-ink-secondary">{d.state_name}</td>
                  <td className="px-5 py-2 text-right tabular-nums text-ink-secondary">
                    {d.company_count.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Recent ingestion runs" padded={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline/40 text-left text-ink-muted">
                <th className="px-5 py-2 font-medium">Source</th>
                <th className="px-5 py-2 font-medium">Status</th>
                <th className="px-5 py-2 text-right font-medium">Fetched</th>
                <th className="px-5 py-2 text-right font-medium">Loaded</th>
                <th className="px-5 py-2 text-right font-medium">Quarantined</th>
                <th className="px-5 py-2 font-medium">Started</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_ingestion_runs.map((r, i) => (
                <tr key={i} className="border-b border-hairline/20 last:border-0">
                  <td className="px-5 py-2 font-mono text-xs text-ink-secondary">{r.source}</td>
                  <td className="px-5 py-2">
                    <span
                      className={
                        r.status === "success"
                          ? "rounded bg-status-good/15 px-2 py-0.5 text-xs font-medium text-[#0a7a0a]"
                          : "rounded bg-status-warning/20 px-2 py-0.5 text-xs font-medium text-[#9a6400]"
                      }
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="px-5 py-2 text-right tabular-nums text-ink-secondary">
                    {r.rows_fetched?.toLocaleString() ?? "—"}
                  </td>
                  <td className="px-5 py-2 text-right tabular-nums text-ink-secondary">
                    {r.rows_loaded?.toLocaleString() ?? "—"}
                  </td>
                  <td className="px-5 py-2 text-right tabular-nums text-ink-secondary">
                    {r.rows_quarantined?.toLocaleString() ?? "—"}
                  </td>
                  <td className="px-5 py-2 text-ink-muted">{new Date(r.started_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
