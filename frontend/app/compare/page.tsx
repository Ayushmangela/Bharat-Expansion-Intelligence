"use client";

import { useState } from "react";
import { X, Plus, GitCompare } from "lucide-react";
import { listDistricts, compareDistricts, DistrictListItem, CompareResponse } from "@/lib/api";
import Card from "@/app/components/Card";

// Client-rendered end to end — comparison is inherently interactive (pick
// districts, see results, change the picks). No server component wrapper
// needed since there's no useful initial state to render before a user
// picks anything.
export default function ComparePage() {
  const [selected, setSelected] = useState<{ lgd_district_code: number; district_name: string; state_name: string }[]>([]);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<DistrictListItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onQueryChange(value: string) {
    setQuery(value);
    if (value.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    setSearching(true);
    try {
      const data = await listDistricts({ q: value, limit: 8 });
      setSuggestions(data.items.filter((d) => !selected.some((s) => s.lgd_district_code === d.lgd_district_code)));
    } finally {
      setSearching(false);
    }
  }

  function addDistrict(d: DistrictListItem) {
    // Functional update, not `[...selected, d]` off the render-time closure
    // — matters if two adds ever land in the same React batch (e.g. fast
    // double-clicks), where a closure-captured `selected` would silently
    // drop one of them.
    setSelected((prev) => (prev.length >= 5 ? prev : [...prev, { lgd_district_code: d.lgd_district_code, district_name: d.district_name, state_name: d.state_name }]));
    setQuery("");
    setSuggestions([]);
    setResult(null);
  }

  function removeDistrict(code: number) {
    setSelected((prev) => prev.filter((s) => s.lgd_district_code !== code));
    setResult(null);
  }

  async function runCompare() {
    setLoading(true);
    setError(null);
    try {
      const r = await compareDistricts(selected.map((s) => s.lgd_district_code));
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "request failed");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Compare districts</h1>
        <p className="mt-1 text-sm text-ink-secondary">
          Pick 2–5 districts for an aligned, indicator-by-indicator comparison — per docs/07-API-SPEC.md.
        </p>
      </div>

      <Card>
        <div className="flex flex-wrap gap-2">
          {selected.map((d) => (
            <span
              key={d.lgd_district_code}
              className="inline-flex items-center gap-1.5 rounded-full bg-accent/10 px-3 py-1 text-sm font-medium text-accent"
            >
              {d.district_name}, {d.state_name}
              <button onClick={() => removeDistrict(d.lgd_district_code)} aria-label={`remove ${d.district_name}`}>
                <X size={13} strokeWidth={2.5} />
              </button>
            </span>
          ))}
        </div>

        {selected.length < 5 && (
          <div className="relative mt-3">
            <input
              type="text"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              placeholder="Search district name to add..."
              className="w-full max-w-sm rounded-md border border-hairline bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-accent focus:outline-none"
            />
            {suggestions.length > 0 && (
              <div className="absolute z-10 mt-1 w-full max-w-sm overflow-hidden rounded-md border border-hairline bg-surface shadow-lg">
                {suggestions.map((d) => (
                  <button
                    key={d.lgd_district_code}
                    onClick={() => addDistrict(d)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent/5"
                  >
                    <Plus size={13} strokeWidth={2} className="text-ink-muted" />
                    <span className="font-medium text-ink">{d.district_name}</span>
                    <span className="text-ink-muted">{d.state_name}</span>
                  </button>
                ))}
              </div>
            )}
            {searching && <div className="mt-1 text-xs text-ink-muted">Searching…</div>}
          </div>
        )}

        <button
          onClick={runCompare}
          disabled={selected.length < 2 || loading}
          className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          <GitCompare size={14} strokeWidth={2} />
          {loading ? "Comparing…" : `Compare ${selected.length} district${selected.length === 1 ? "" : "s"}`}
        </button>
        {selected.length === 1 && <p className="mt-2 text-xs text-ink-muted">Add at least one more district to compare.</p>}
        {error && <p className="mt-2 text-sm text-[#b93231]">{error}</p>}
      </Card>

      {result && (
        <>
          <Card title="Trade-off summary" subtitle="Derived from the data below — never generated text.">
            <div className="flex flex-wrap gap-6 text-sm">
              <div>
                <div className="text-xs text-ink-muted">Overall score leader</div>
                <div className="mt-1 font-medium text-ink">
                  {result.districts.find((d) => d.lgd_district_code === result.trade_off_summary.overall_score_leader)
                    ?.district_name ?? "tied / none scored"}
                </div>
              </div>
              {result.districts.map((d) => (
                <div key={d.lgd_district_code}>
                  <div className="text-xs text-ink-muted">{d.district_name}</div>
                  <div className="mt-1 font-medium text-ink">
                    leads {result.trade_off_summary.indicators_led_count[String(d.lgd_district_code)] ?? 0} of{" "}
                    {result.indicators.length} indicators
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card padded={false} title="Indicator-by-indicator">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-hairline/40 text-left text-ink-muted">
                    <th className="px-5 py-2 font-medium">Indicator</th>
                    {result.districts.map((d) => (
                      <th key={d.lgd_district_code} className="px-5 py-2 text-right font-medium">
                        {d.district_name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-hairline/20 bg-page/60">
                    <td className="px-5 py-2 font-medium text-ink">Opportunity Score</td>
                    {result.districts.map((d) => (
                      <td key={d.lgd_district_code} className="px-5 py-2 text-right tabular-nums font-semibold text-ink">
                        {d.opportunity_score !== null ? d.opportunity_score.toFixed(1) : "—"}
                        {d.rank_national !== null && <span className="ml-1 text-xs font-normal text-ink-muted">#{d.rank_national}</span>}
                      </td>
                    ))}
                  </tr>
                  {result.indicators.map((ind) => (
                    <tr key={ind.indicator_code} className="border-b border-hairline/20 last:border-0">
                      <td className="px-5 py-2 text-ink-secondary">{ind.name}</td>
                      {result.districts.map((d) => {
                        const v = ind.values[String(d.lgd_district_code)];
                        const isLeader = ind.leader === d.lgd_district_code;
                        return (
                          <td
                            key={d.lgd_district_code}
                            className={`px-5 py-2 text-right tabular-nums ${isLeader ? "font-semibold text-accent" : "text-ink-secondary"}`}
                          >
                            {v?.raw_value !== null && v?.raw_value !== undefined ? v.raw_value.toLocaleString() : "—"}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
