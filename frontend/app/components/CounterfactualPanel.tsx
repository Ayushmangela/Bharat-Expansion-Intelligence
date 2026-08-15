"use client";

import { useState } from "react";
import { TrendingUp } from "lucide-react";
import { getCounterfactual, CounterfactualResult } from "@/lib/api";

// docs/06-SCORING-METHODOLOGY.md §9: "the highest-value feature and almost
// nobody builds it" — turns the score into a policy to-do list instead of a
// bare number. Client-rendered (not server-rendered like the rest of the
// page) because the target rank is genuinely interactive — the whole point
// is letting the reader try different targets.
export default function CounterfactualPanel({ lgdDistrictCode, currentRank }: { lgdDistrictCode: number; currentRank: number | null }) {
  const [targetRank, setTargetRank] = useState(Math.max(1, (currentRank ?? 50) - 10));
  const [result, setResult] = useState<CounterfactualResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const r = await getCounterfactual(lgdDistrictCode, targetRank);
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "request failed");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  if (currentRank === null) {
    return (
      <p className="text-sm text-ink-muted">
        This district is below the ranking confidence floor, so &quot;what would it take to reach rank N&quot; isn&apos;t a
        meaningful question yet — there&apos;s no trustworthy current rank to move from.
      </p>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1 block text-xs text-ink-muted" htmlFor="target-rank">
            Target national rank
          </label>
          <input
            id="target-rank"
            type="number"
            min={1}
            value={targetRank}
            onChange={(e) => setTargetRank(Number(e.target.value))}
            className="w-28 rounded-md border border-hairline bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
          />
        </div>
        <button
          onClick={run}
          disabled={loading || targetRank < 1}
          className="inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          <TrendingUp size={14} strokeWidth={2} />
          {loading ? "Computing…" : "What would it take?"}
        </button>
        <span className="text-xs text-ink-muted">currently rank #{currentRank}</span>
      </div>

      {error && <p className="mt-3 text-sm text-[#b93231]">{error}</p>}

      {result?.already_achieved && (
        <p className="mt-4 text-sm text-ink-secondary">
          Already at rank #{result.current_rank}, which meets or beats target rank #{result.target_rank} — no changes needed.
        </p>
      )}

      {result && !result.already_achieved && (
        <div className="mt-4">
          <p className="text-sm text-ink-secondary">
            To reach rank #{result.target_rank} (score ≥ {result.target_score?.toFixed(1)}, currently {result.current_score?.toFixed(1)}
            ), holding every other district fixed — the 3 cheapest single-indicator levers:
          </p>
          {result.levers.length === 0 ? (
            <p className="mt-3 text-sm text-ink-muted">
              No single-indicator lever reaches this target within the observed national range. All {result.infeasible.length}{" "}
              present indicators would need to exceed the best district in India — not actionable advice as a single change.
            </p>
          ) : (
            <div className="mt-3 space-y-2">
              {result.levers.map((lever) => (
                <div key={lever.indicator_code} className="rounded-lg border border-hairline/40 bg-page p-3">
                  <div className="text-sm font-medium text-ink">{lever.description}</div>
                  <div className="mt-1 text-xs text-ink-muted">
                    {lever.current_value.toLocaleString()} → {lever.required_value.toLocaleString()} (Δ
                    {lever.required_delta > 0 ? "+" : ""}
                    {lever.required_delta.toLocaleString()})
                  </div>
                </div>
              ))}
            </div>
          )}
          {result.infeasible.length > 0 && (
            <p className="mt-3 text-xs text-ink-muted">
              Rejected as infeasible (would require exceeding the best district in India on that indicator alone):{" "}
              {result.infeasible.join(", ")}.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
