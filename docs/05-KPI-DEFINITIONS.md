# 05 — KPI Definitions

Every KPI is defined precisely. "Business formation rate" means nothing until you say
*per what*.

Each entry gives: formula, grain, sources, direction (higher-is-better `↑` or
lower-is-better `↓`), and known caveats.

---

## Pillar 1 — Economic Activity

### BFR — Business Formation Rate ↑
```
new_incorporations_in_period / working_age_population * 100_000
```
Grain: district × month · Sources: S02, S19
Caveat: registered office ≠ operating location; metros inflated.

### FMOM — Formation Momentum ↑
```
(trailing_12m_incorporations / prior_12m_incorporations) - 1
```
Grain: district × month · Source: S02
Caveat: requires 24 months of history; NULL before that. Seasonally sensitive — use
seasonally adjusted series.

### CAPI — Capital Intensity ↑
```
median(paid_up_capital_lakh) of companies incorporated in period
```
Grain: district × month · Source: S02
Median not mean — the distribution is extremely right-skewed.

### CMR — Corporate Mortality Rate ↓
```
companies_transitioning_to_struck_off / active_companies_at_period_start * 1_000
```
Grain: district × month · Source: S02
Caveat: strike-off is an **administrative** action, frequently dormant-shell cleanup.
It is NOT synonymous with business failure. State this wherever it appears.

### NCV — Net Corporate Vitality ↑
```
BFR - CMR
```

### AMOM — Activity Momentum ↑
```
(trailing_12m_gst_collection / prior_12m_gst_collection) - 1
```
Grain: state × month · Source: S13 · **Inherited by districts — flag it.**

### EOD — Economic Output Density ↑
```
gsdp_constant_cr * 10_000_000 / population
```
Grain: state × year · Sources: S07, S19 · **Inherited by districts — flag it.**

---

## Pillar 2 — Business Ecosystem

### MSMED — MSME Density ↑
```
(msme_micro + msme_small + msme_medium) / population * 1_000
```
Grain: district · Sources: S03, S19

### MMS — Manufacturing MSME Share ↑
```
msme_manufacturing / (msme_manufacturing + msme_services)
```
Grain: district · Source: S03
Direction is profile-dependent: ↑ for manufacturing profile, neutral for retail.

### SI — Startup Intensity ↑
```
startups_recognised / population * 1_000_000
```
Grain: state × year · Sources: S04, S19 · Counts, **not funding**. Inherited — flag.

### FTBD — Formal Tax Base Density ↑
```
gst_active_taxpayers / population * 1_000
```
Grain: state × month · Sources: S13, S19 · Inherited — flag.

### IBD — Industrial Base Depth ↑
```
asi_employment / total_workers
```
Grain: state × year · Sources: S06, S19 · ASI lags 2–3 years. Tag vintage.

### ICON — Industry Concentration (HHI) ↓
```
sum over NIC-2 sectors of (sector_share_of_district_incorporations)^2
```
Grain: district · Source: S02
Range 0–1. High = undiversified = concentration risk. Direction is ↓ for resilience,
but note a manufacturing-seeking user may *want* concentration in their own sector —
handled by profile weighting, not by flipping the indicator.

---

## Pillar 3 — Infrastructure & Reliability

### PRS — Power Reliability Score ↑
```
max(0, 100 - energy_deficit_pct)
```
Grain: state × month · Source: S08 · Inherited — flag.

### PKRS — Peak Reliability Score ↑
```
max(0, 100 - peak_deficit_pct)
```
Grain: state × month · Source: S08 · Inherited — flag.

### FCAP — Fiscal Capacity ↑
```
state_capex_cr * 10_000_000 / population
```
Grain: state × year · Sources: S16, S19 · Inherited — flag.

### CCRED — Capex Credibility ↑
```
actual_capex_cr / budgeted_capex_cr
```
Grain: state × year · Source: S16
Cap at 1.5 before normalising — overspend beyond that usually signals a restatement
rather than execution excellence.

### RDEN — Road Density ↑
```
road_length_km / area_sq_km * 1_000
```
Grain: state × year · Sources: S07, S09
Slow-moving structural variable. Vintage may lag several years — acceptable here
because road stock changes slowly, but tag it.

---

## Pillar 4 — Human Capital & Market

### LFPR — Labour Availability ↑
```
plfs_lfpr    (direct from PLFS)
```
Grain: state × year · Source: S06 · Inherited — flag.

### PCI — Per Capita Income ↑
```
per_capita_income    (direct from RBI Handbook)
```
Grain: state × year · Source: S07 · Inherited — flag.

### POPS — Population Scale ↑
```
log10(population)
```
Grain: district · Source: S19 (2011 + projections)
Log transform because raw population spans four orders of magnitude and would otherwise
dominate normalisation.

### LIT — Literacy Rate ↑
```
literate_population / population_7_plus * 100
```
Grain: district · Source: S19 · **Vintage 2011. Label it.**

---

## Derived

### OS — Opportunity Score
See `06-SCORING-METHODOLOGY.md`. Range 0–100.

### CONF — Confidence Score
```
sum(weight_i for indicators present) / sum(weight_i for all indicators)
```
Range 0–1. **Never display an Opportunity Score without its Confidence Score.**

---

## Implementation rules

1. Every indicator gets a stable `indicator_code` (the bold codes above). These appear
   in `fact_score_contribution.indicator_code` and in the API.
2. Every indicator registers its **direction** — used to invert lower-is-better
   indicators before normalisation. **Getting one direction wrong silently inverts your
   entire ranking.** Unit-test every direction.
3. Every indicator records whether it is `is_inherited` (state value applied to
   district). Currently 10 of 20 indicators are state-grain and inherited. The UI must
   show this — otherwise you are implying district-level precision you do not have.
4. KPI computation lives in materialised views where possible, `backend/app/ml/kpis.py`
   where not.
