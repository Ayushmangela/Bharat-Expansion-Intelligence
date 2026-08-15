import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { getDistrict, getDistrictScore } from "@/lib/api";
import CompanyStatusPieChart from "@/app/components/CompanyStatusPieChart";
import MonthlyIncorporationsChart from "@/app/components/MonthlyIncorporationsChart";
import MsmeBarChart from "@/app/components/MsmeBarChart";
import ContributionBarChart from "@/app/components/ContributionBarChart";
import ConfidenceBadge from "@/app/components/ConfidenceBadge";
import Card from "@/app/components/Card";

const PILLAR_LABELS: Record<string, string> = {
  economic: "Economic",
  ecosystem: "Ecosystem",
  infrastructure: "Infrastructure",
  human_capital: "Human Capital",
};

export default async function DistrictDetailPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  let data;
  try {
    data = await getDistrict(Number(code));
  } catch {
    notFound();
  }
  const scorecard = await getDistrictScore(Number(code)).catch(() => null);

  const { geography, company_status_breakdown, msme, monthly_incorporations } = data;
  const totalCompanies = company_status_breakdown.reduce((sum, s) => sum + s.count, 0);
  // API returns newest-first (LIMIT 24, ORDER BY month DESC); a trend line reads
  // more naturally chronological, oldest to newest.
  const chronologicalIncorporations = [...monthly_incorporations].reverse();

  return (
    <div className="flex flex-col gap-8">
      <div>
        <Link href="/districts" className="inline-flex items-center gap-1.5 text-sm text-ink-secondary hover:text-ink hover:underline">
          <ArrowLeft size={14} strokeWidth={2} />
          All districts
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-ink">{geography.district_name}</h1>
        <p className="text-sm text-ink-secondary">
          {geography.state_name} · LGD district code {geography.lgd_district_code}
        </p>
      </div>

      {scorecard?.score && (
        <Card
          title="Opportunity Score"
          subtitle="Score decomposes into the indicator contributions below — see docs/06-SCORING-METHODOLOGY.md."
          action={<ConfidenceBadge band={scorecard.score.confidence_band} score={scorecard.score.confidence_score} />}
        >
          <div className="flex flex-wrap items-end gap-8">
            <div>
              <div className="text-4xl font-semibold tabular-nums text-ink">{scorecard.score.opportunity_score.toFixed(1)}</div>
              <div className="text-xs text-ink-muted">out of 100 · profile: {scorecard.score.profile}</div>
            </div>
            <div>
              <div className="text-lg font-semibold tabular-nums text-ink">
                {scorecard.score.rank_national ? `#${scorecard.score.rank_national}` : "Unranked"}
              </div>
              <div className="text-xs text-ink-muted">
                national rank
                {scorecard.score.rank_ci_low && scorecard.score.rank_ci_high
                  ? ` (95% CI: ${scorecard.score.rank_ci_low}–${scorecard.score.rank_ci_high})`
                  : ""}
              </div>
            </div>
            {scorecard.score.rank_within_state && (
              <div>
                <div className="text-lg font-semibold tabular-nums text-ink">#{scorecard.score.rank_within_state}</div>
                <div className="text-xs text-ink-muted">within {geography.state_name}</div>
              </div>
            )}
            <div>
              <div className="text-lg font-semibold tabular-nums text-ink">
                {scorecard.score.indicators_used}/{scorecard.score.indicators_total}
              </div>
              <div className="text-xs text-ink-muted">indicators present</div>
            </div>
          </div>

          {scorecard.pillars && (
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {Object.entries(scorecard.pillars).map(([key, value]) => (
                <div key={key} className="rounded-lg border border-hairline/40 bg-page p-3">
                  <div className="text-xs text-ink-muted">{PILLAR_LABELS[key] ?? key}</div>
                  <div className="mt-1 text-lg font-semibold tabular-nums text-ink">
                    {value !== null ? value.toFixed(1) : <span className="text-sm font-normal text-ink-muted">not computable</span>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {scorecard.indicators && (
            <div className="mt-5">
              <div className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-muted">
                Contribution to score (score-points, sums to {scorecard.score.opportunity_score.toFixed(1)})
              </div>
              <ContributionBarChart indicators={scorecard.indicators} />
            </div>
          )}

          {scorecard.warnings.length > 0 && (
            <ul className="mt-4 space-y-1 border-t border-hairline/40 pt-3 text-xs text-ink-muted">
              {scorecard.warnings.map((w, i) => (
                <li key={i}>⚠ {w}</li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <Card title={`Company status (${totalCompanies.toLocaleString()} total)`}>
        {totalCompanies === 0 ? (
          <div className="flex h-32 items-center justify-center text-sm text-ink-muted">
            No registered companies loaded for this district yet.
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {company_status_breakdown.map((s) => (
                <div key={s.status} className="rounded-lg border border-hairline/40 bg-page p-3">
                  <div className="text-xs text-ink-muted">{s.status}</div>
                  <div className="mt-1 text-xl font-semibold tabular-nums text-ink">{s.count.toLocaleString()}</div>
                  <div className="text-xs text-ink-muted">{((s.count / totalCompanies) * 100).toFixed(1)}%</div>
                </div>
              ))}
            </div>
            <div className="mt-4">
              <CompanyStatusPieChart breakdown={company_status_breakdown} />
            </div>
          </>
        )}
      </Card>

      {msme && (
        <Card
          title="MSME (Udyam, cumulative-to-date)"
          subtitle="Manufacturing is derived as total − services (no Udyam manufacturing-specific resource exists — see STATUS.md item 15)."
        >
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-hairline/40 bg-page p-3">
              <div className="text-xs text-ink-muted">Micro</div>
              <div className="mt-1 text-xl font-semibold tabular-nums text-ink">{msme.micro.toLocaleString()}</div>
            </div>
            <div className="rounded-lg border border-hairline/40 bg-page p-3">
              <div className="text-xs text-ink-muted">Small</div>
              <div className="mt-1 text-xl font-semibold tabular-nums text-ink">{msme.small.toLocaleString()}</div>
            </div>
            <div className="rounded-lg border border-hairline/40 bg-page p-3">
              <div className="text-xs text-ink-muted">Medium</div>
              <div className="mt-1 text-xl font-semibold tabular-nums text-ink">{msme.medium.toLocaleString()}</div>
            </div>
            <div className="rounded-lg border border-hairline/40 bg-page p-3">
              <div className="text-xs text-ink-muted">Manufacturing (derived)</div>
              <div className="mt-1 text-xl font-semibold tabular-nums text-ink">
                {msme.manufacturing.toLocaleString()}
              </div>
            </div>
            <div className="rounded-lg border border-hairline/40 bg-page p-3">
              <div className="text-xs text-ink-muted">Services</div>
              <div className="mt-1 text-xl font-semibold tabular-nums text-ink">{msme.services.toLocaleString()}</div>
            </div>
          </div>
          <div className="mt-4">
            <MsmeBarChart msme={msme} />
          </div>
        </Card>
      )}

      {monthly_incorporations.length > 0 && (
        <Card
          title="Recent monthly incorporations"
          subtitle="Raw new-company counts by month (date-outlier rows excluded, per quality_flags)."
        >
          <MonthlyIncorporationsChart monthly={chronologicalIncorporations} />
          <div className="mt-4 max-h-64 overflow-y-auto rounded-lg border border-hairline/40">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-page">
                <tr className="border-b border-hairline/40 text-left text-ink-muted">
                  <th className="px-4 py-2 font-medium">Month</th>
                  <th className="px-4 py-2 text-right font-medium">New incorporations</th>
                </tr>
              </thead>
              <tbody>
                {monthly_incorporations.map((m) => (
                  <tr key={m.month} className="border-b border-hairline/20 last:border-0">
                    <td className="px-4 py-2 text-ink-secondary">{m.month.slice(0, 7)}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-ink-secondary">{m.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
