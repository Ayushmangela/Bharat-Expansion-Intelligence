# 08 — Frontend Specification

Next.js 14+ (App Router) + TypeScript + Tailwind. TanStack Query (server state), Zustand
(UI state). Recharts for standard charts, Apache ECharts for the choropleth and large
scatter.

Server Components fetch initial page data where it's simple (e.g. the National Overview
shell); anything interactive (live weight sliders, drill-downs, the SHAP waterfall) is a
Client Component wired to TanStack Query so it can re-fetch without a full navigation.

---

## Design principle

**The SHAP waterfall is the hero component. Everything else supports it.**

If a design decision trades explanation clarity for visual polish, choose explanation.

---

## Pages

### 1. National Overview `/`
- India district choropleth (ECharts geo), coloured by Opportunity Score
- Profile selector (persists to Zustand)
- Top 10 / Bottom 10 tables
- National KPI strip
- Month-over-month movers ("biggest risers / fallers")
- Data freshness banner if any source is stale

### 2. District Scorecard `/districts/[lgdCode]`
The most important page.

- Header: name, state, score, rank with CI (`rank 2 (1–6)`), **confidence badge**
- **SHAP waterfall** — positive contributions green, negative red, sorted by magnitude
- Pillar radar chart (4 axes)
- Indicator table: raw value, national median, percentile, source, vintage,
  **inherited badge**, imputed badge
- Trend charts: formation rate, score history
- Counterfactual panel: "to reach rank 10, these 3 levers"
- Similar districts (5 cards)
- **Source attribution panel** (from `dim_source`)
- Narrative block — only if `narrative_available`, rendered *below* the waterfall,
  never instead of it

### 3. Ranking Explorer `/explore`
- Sortable, filterable, virtualised table
- **Live weight sliders** → calls `POST /scores/simulate` → instant re-rank
- Profile presets
- CSV export
- Shows the interpreted weight vector so the user can see what they changed

### 4. Head-to-Head `/compare?d=532&d=474`
- 2–4 districts side by side
- Indicator-by-indicator diff with winner highlighting
- Trade-off summary
- Overlaid radar

### 5. Sector Intelligence `/sectors`
- NIC-2 selector
- Location Quotient map
- Where each industry concentrates

### 6. Trends & Forecasts `/trends`
- Time series with forecast bands
- Changepoints annotated
- Seasonality decomposition (trend / seasonal / residual)
- **MASE vs seasonal-naive displayed prominently** — if the model doesn't beat the
  baseline, say so on the chart

### 7. Ask `/ask`
- Natural language input
- **Interpreted query echoed back for verification before results**
- Results as ranked cards
- Falls back to the filter UI if the LLM is unavailable

### 8. Data & Sources `/data`
**Public, not an admin page.**
- Per-source: name, publisher, licence, URL, vintage, last success, staleness
- Geography resolution rate
- Quarantine counts
- Coverage gaps by district
- Known limitations list (from CLAUDE.md §9)
- Full GODL attribution text

Publishing your data problems reads as confidence, not weakness. Most portfolio
dashboards hide them.

---

## Key components

```
components/
├── ShapWaterfall.tsx        HERO. Horizontal bars, sorted by |contribution|.
│                            Inherited indicators get a distinct hatch pattern.
├── ConfidenceBadge.tsx      High / Moderate / Low — always beside a score
├── RankWithInterval.tsx     "2 (1–6)" — never a bare rank
├── VintageTag.tsx           e.g. "2011" on Census-derived values
├── InheritedBadge.tsx       "state-level" — on all 10 inherited indicators
├── IndiaChoropleth.tsx      ECharts geo, LGD district GeoJSON
├── PillarRadar.tsx          Recharts radar, 4 axes
├── WeightSliders.tsx        4 pillar sliders, auto-normalise to sum 1
├── IndicatorTable.tsx       Virtualised, sortable
├── CounterfactualPanel.tsx  Top 3 levers with feasibility
├── SourceAttribution.tsx    GODL-compliant, from /meta/sources
└── ForecastChart.tsx        Line + prediction interval band + MASE annotation
```

---

## Non-negotiable UI rules

1. **Never render a score without its confidence badge.**
2. **Never render a rank without its confidence interval.**
3. **Never render a Census-derived value without its 2011 vintage tag.**
4. **Always mark inherited (state-level) indicators visually.** 10 of 22 indicators are
   inherited — hiding this implies district-level precision that does not exist.
5. **Never encode meaning in colour alone.** India choropleths default to red-green,
   which is the single most common accessibility failure in this genre. Use pattern,
   label, or shape as well.
6. **The app must fully function with `LLM_ENABLED=false`.** Build it that way first.
7. Mobile: ranking table and scorecard must work on a phone. The map may degrade to a
   list.

---

## State management

```ts
// Zustand — UI state only
interface UIState {
  profile: ProfileCode;
  customWeights: PillarWeights | null;
  selectedDistricts: number[];   // for compare
  mapMetric: 'score' | 'pillar_economic' | ...;
}
```

Server state is TanStack Query only. Never duplicate API data into Zustand.

```ts
// Query keys must include profile + weights or you serve stale scores
['districts', { profile, filters }]
['district', lgdCode, { profile }]
['explain', lgdCode, { profile }]
```

---

## Typed API client

Generate from the FastAPI OpenAPI schema:

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.ts
```

Do not hand-write response types — they drift.

---

## Performance

- Virtualise the 750-row ranking table (`@tanstack/react-virtual`)
- Lazy-load ECharts (it is large)
- District GeoJSON: simplify geometry, serve gzipped, cache aggressively
- Debounce weight sliders at 300ms before hitting `/scores/simulate`
