# 07 — API Specification

FastAPI. Base path `/api/v1`. All responses Pydantic-typed. OpenAPI auto-generated at
`/docs`.

No auth initially (public read-only). Add JWT only when saved views ship.

---

## Conventions

- Pagination: `?limit=50&offset=0`, response wraps `{items, total, limit, offset}`
- Errors: RFC 7807 problem+json `{type, title, status, detail, instance}`
- All money in ₹ lakh unless the field name says otherwise
- Every metric response includes `vintage` and `is_inherited`
- `profile` defaults to `balanced`

---

## Endpoints

### `GET /api/v1/districts`
List districts with filters.

Query: `state_code`, `region`, `min_score`, `profile`, `q` (name search), `limit`, `offset`

```json
{
  "items": [{
    "lgd_district_code": 532,
    "district_name": "Chittoor",
    "state_name": "Andhra Pradesh",
    "lgd_state_code": 28,
    "opportunity_score": 78.4,
    "rank_national": 2,
    "rank_ci_low": 1,
    "rank_ci_high": 6,
    "confidence_score": 0.91,
    "confidence_band": "High"
  }],
  "total": 766, "limit": 50, "offset": 0
}
```

### `GET /api/v1/districts/{lgd_district_code}`
Full scorecard.

```json
{
  "geography": { "lgd_district_code": 532, "district_name": "Chittoor",
                 "state_name": "Andhra Pradesh", "area_sq_km": 15152.0,
                 "centroid": {"lat": 13.21, "lon": 79.10} },
  "score": { "opportunity_score": 78.4, "profile": "manufacturing",
             "rank_national": 2, "rank_ci_low": 1, "rank_ci_high": 6,
             "confidence_score": 0.91, "indicators_used": 20, "indicators_total": 22,
             "weight_version_id": 7, "computed_at": "2026-08-01T00:00:00Z" },
  "pillars": { "economic": 81.2, "ecosystem": 74.9,
               "infrastructure": 88.1, "human_capital": 61.3 },
  "indicators": [{
      "code": "BFR", "name": "Business Formation Rate",
      "raw_value": 42.7, "unit": "per 100k working-age pop",
      "normalised_value": 76.2, "national_median": 28.1,
      "percentile": 84, "direction": "higher_better",
      "is_imputed": false, "is_inherited": false,
      "source_code": "S02", "vintage": "2026-06"
  }],
  "warnings": ["10 of 22 indicators are inherited from state-level data"]
}
```

### `GET /api/v1/districts/{code}/explain`
SHAP decomposition. **This is the core endpoint of the product.**

```json
{
  "lgd_district_code": 532,
  "profile": "manufacturing",
  "base_value": 50.0,
  "final_score": 78.4,
  "contributions": [
    {"indicator_code":"FMOM","indicator_name":"Formation Momentum",
     "shap_contribution": 12.3,"raw_value":0.34,"is_inherited":false,"source_code":"S02"},
    {"indicator_code":"LFPR","indicator_name":"Labour Availability",
     "shap_contribution": -6.2,"raw_value":48.1,"is_inherited":true,"source_code":"S06"}
  ],
  "narrative": null,
  "narrative_available": false
}
```
`narrative` is populated only when `LLM_ENABLED=true`. **The client must render the
contributions table regardless.**

### `GET /api/v1/districts/{code}/counterfactual?target_rank=10`
```json
{ "current_rank": 42, "target_rank": 10,
  "levers": [
    {"indicator_code":"PRS","required_delta": 4.2,
     "required_value": 96.1,"current_value": 91.9,
     "feasibility":"within observed national range",
     "description":"Reduce energy deficit from 8.1% to 3.9%"}
  ],
  "infeasible": ["PCI"] }
```

### `GET /api/v1/districts/{code}/similar?limit=5`
Cosine similarity on the normalised indicator vector.

### `GET /api/v1/scores`
Ranked scores, profile-parameterised, with optional custom weights.

Query: `profile`, `weights` (JSON, overrides profile), `date_key`, `limit`, `offset`

### `POST /api/v1/scores/simulate`
Live re-ranking for the weight sliders. Does not persist.
```json
{ "weights": {"economic":0.4,"ecosystem":0.2,"infrastructure":0.3,"human_capital":0.1},
  "limit": 50 }
```

### `POST /api/v1/compare`
```json
{ "district_codes": [532, 474], "profile": "manufacturing" }
```
Returns aligned indicator-by-indicator diff plus trade-off summary.

### `GET /api/v1/districts/{code}/forecast?metric=new_incorporations&horizon=12`
```json
{ "metric":"new_incorporations","method":"SARIMA",
  "baseline_method":"seasonal_naive","mase_vs_baseline": 0.83,
  "points":[{"date_key":202609,"forecast":118.2,"lower_95":94.1,"upper_95":142.3}] }
```
`mase_vs_baseline < 1` means it beats seasonal-naive. **Always return this.**

### `GET /api/v1/sectors/{nic_2digit}/districts`
Where a given industry is concentrating. Returns Location Quotient per district.

### `POST /api/v1/query`
Natural language → validated params → results.

```json
{ "query": "manufacturing districts in south india with low power deficit" }
```
```json
{ "interpreted": {"profile":"manufacturing","region":"South",
                  "filters":[{"indicator":"PRS","op":">=","value":95}]},
  "items": [ ... ],
  "note": "Showing interpreted query for verification" }
```

**SECURITY — non-negotiable:** the LLM extracts *parameters only*, validated against an
allowlist of indicator codes and operators. The SQL is then built in code with bound
parameters. **Never let an LLM emit raw SQL against the warehouse.**

### `GET /api/v1/meta/sources`
Source registry with freshness — drives the attribution panel and the public data
quality page.
```json
[{"source_code":"S02","source_name":"MCA Company Master Data",
  "publisher":"Ministry of Corporate Affairs","licence":"GODL-India",
  "url":"https://www.data.gov.in/catalog/company-master-data",
  "attribution_text":"...","data_vintage":"2026-06-30",
  "last_success_at":"2026-08-01T03:12:00Z","is_stale":false,"tier":"A"}]
```

### `GET /api/v1/meta/quality`
Public. Resolution rates, quarantine counts, failed loads, coverage gaps.

### `GET /api/v1/meta/profiles`
### `GET /api/v1/health`
```json
{"status":"ok","database":"ok","redis":"ok",
 "stalest_source":{"source_code":"S20","days_overdue":0},
 "llm":"disabled"}
```

---

## Caching

| Endpoint | TTL | Key includes |
|---|---|---|
| `/districts`, `/scores` | 24h | profile, filters, `weight_version`, `load_version` |
| `/districts/{c}/explain` | until recompute | code, profile, `weight_version` |
| `/scores/simulate` | 5 min | hash of weights |
| `/meta/*` | 5 min | — |

Omitting `weight_version` or `load_version` from cache keys produces stale scores that
look correct. Genuinely painful to debug. Don't.

---

## Error handling

| Case | Status |
|---|---|
| Unknown LGD code | 404 |
| Invalid profile | 422 |
| Weights don't sum to 1 (±0.01) | 422 |
| Score not yet computed for period | 409 with `retry_after` |
| LLM unavailable on `/query` | 200 with `narrative_available: false`, degrade to filters |
