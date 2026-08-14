# 06 — Scoring Methodology

**The score is not the product. The explanation is the product.**

Most composite-index projects die on one question: *"how did you pick the weights?"*
This methodology answers it two ways and then proves the answer doesn't matter much.

---

## 1. Direction alignment

Some indicators are good when high (BFR), some when low (CMR, ICON). Invert the
negatives so all point the same way.

```python
aligned = value if direction == "higher_better" else -value
```

**Unit-test every direction.** One wrong sign silently inverts the whole ranking and it
will look plausible.

---

## 2. Winsorisation — do this BEFORE normalising

Clip each indicator at the 1st and 99th percentile across all districts.

**Why this is non-negotiable:** Mumbai, Bengaluru and Delhi have company counts orders
of magnitude above the median. Without winsorising, min-max normalisation squashes 740
districts into the bottom 5% of the range and your "Opportunity Score" becomes a
metro-detector.

Set `quality_flags` bit 3 on winsorised values.

---

## 3. Normalisation

Robust min-max to [0, 100] on winsorised values:

```python
normalised = 100 * (x - p01) / (p99 - p01)
normalised = clip(normalised, 0, 100)
```

Use 0–100 for the **presented** score (interpretable to a business user). Keep z-scores
internally for the statistics.

### THE CHECKPOINT

After the first scoring run, **look at the top 10 districts.**

If it is just the 10 largest metros, the normalisation is broken. Fix it before building
anything else. Specifically check:
- Are per-capita indicators actually per-capita, or did an absolute count leak through?
- Is winsorisation applied before, not after, scaling?
- Is `POPS` log-transformed?

Do not proceed on a broken ranking. Everything downstream inherits the error.

---

## 4. Missingness — explicit, never silent

Preference order:

1. **Use a finer grain** if available
2. **Inherit from parent geography** (state → district), set `is_inherited = true`,
   `quality_flags` bit 1
3. **Exclude the indicator** for that district and **reduce `confidence_score`**

**Never impute with the national mean and stay quiet.** That manufactures a
plausible-looking number out of nothing, which is worse than a gap.

---

## 5. Pillar aggregation

| Pillar | Indicators |
|---|---|
| `economic` | BFR, FMOM, CAPI, CMR, NCV, AMOM, EOD |
| `ecosystem` | MSMED, MMS, SI, FTBD, IBD, ICON |
| `infrastructure` | PRS, PKRS, FCAP, CCRED, RDEN |
| `human_capital` | LFPR, PCI, POPS, LIT |

Weighted average within pillar → pillar score. Then weighted across pillars → Opportunity
Score.

---

## 6. Weighting — compute BOTH

### 6a. Entropy weighting (data-driven default)

Indicators that discriminate more between districts get more weight. This removes the
"you just made the weights up" objection entirely.

```
p_ij = x_ij / sum_i(x_ij)                       # normalise column j
e_j  = -k * sum_i(p_ij * ln(p_ij)),  k = 1/ln(n)  # entropy
d_j  = 1 - e_j                                   # divergence
w_j  = d_j / sum_j(d_j)                          # weight
```
Handle `p_ij = 0` as contributing 0 to the entropy sum.

### 6b. Profile weighting (user-driven)

Stored in `dim_profile.pillar_weights`.

| Profile | economic | ecosystem | infrastructure | human_capital |
|---|---|---|---|---|
| `manufacturing` | 0.25 | 0.25 | 0.35 | 0.15 |
| `logistics` | 0.30 | 0.20 | 0.35 | 0.15 |
| `retail` | 0.30 | 0.20 | 0.15 | 0.35 |
| `services` | 0.30 | 0.30 | 0.15 | 0.25 |
| `balanced` | 0.25 | 0.25 | 0.25 | 0.25 |

These are starting values. The UI exposes live sliders.

### 6c. Present both

Show that the ranking is stable across weighting schemes — or be honest that it isn't.

**A composite index whose ranking flips under mild reweighting is not measuring anything
real.** The sensitivity analysis is what tells you which one you have built.

---

## 7. Monte Carlo sensitivity — MANDATORY

```
for trial in 1..1000:
    perturbed_w = w * (1 + uniform(-0.20, +0.20))
    perturbed_w = perturbed_w / sum(perturbed_w)
    recompute scores, record rank per district

report: rank_ci_low  = 2.5th percentile of ranks
        rank_ci_high = 97.5th percentile of ranks
```

Publish **"Chittoor: rank 2 (95% CI: 1–6)"**, never a bare "rank 2".

This single feature does more for credibility than any model you could add. It is also
the thing a good reviewer will notice immediately.

---

## 8. Explanation engine — SHAP

Train a LightGBM regressor predicting a held-out outcome (e.g. GSDP-per-capita growth,
or forward formation momentum) from the indicator vector.

**The prediction is not the point.** The SHAP values are. They convert
*"score 84"* into:

```
+12.3  Formation Momentum       (BFR trailing growth well above median)
 +9.1  Power Reliability        (energy deficit 0.4% vs national 2.1%)
 +6.4  MSME Density
 -6.2  Labour Availability      (LFPR below national median)  [inherited from state]
 -3.8  Per Capita Income        [inherited from state]
```

Store every contribution in `gold.fact_score_contribution` with `is_imputed`,
`is_inherited`, and `source_code`.

`SHAP TreeExplainer` on the LightGBM model. Cache aggressively — expensive, changes
monthly.

---

## 9. Counterfactual — "what would have to change"

For each district, for each indicator, compute the delta required to move up N ranks:

```
for each indicator i:
    binary search delta such that
    rank(score with indicator_i + delta) <= target_rank
    subject to delta keeping indicator within observed national range
```

Report the 3 cheapest levers. Reject counterfactuals requiring values outside the
observed national range — "become the best district in India at everything" is not
actionable advice.

This is the highest-value feature and almost nobody builds it. A state investment agency
reads it as a policy to-do list.

---

## 10. Confidence score

```
confidence = sum(w_i for i in indicators_present) / sum(w_i for i in all_indicators)
```

Display bands: `≥0.90 High` · `0.75–0.89 Moderate` · `<0.75 Low — interpret with caution`

**Never render an Opportunity Score without its Confidence Score adjacent.**

---

## 11. Nearest comparable districts

Cosine similarity on the normalised indicator vector. Return top 5.
Used for "districts most similar to your shortlist."

---

## 12. Additional statistics to compute and report

| Method | Purpose |
|---|---|
| Spearman correlation matrix | Detect redundant indicators double-counting one signal |
| Variance Inflation Factor | Flag multicollinearity distorting weights (VIF > 10 = investigate) |
| PCA | Confirm dimensionality — do the 4 pillars actually exist in the data? |
| Moran's I | Spatial autocorrelation — are high scores geographically clustered? |
| STL decomposition | Separate trend from Indian fiscal-year seasonality |
| PELT changepoints | Structural breaks in district formation series |

**Indian fiscal-year seasonality matters.** Incorporations spike around March/April for
tax and compliance reasons. Without seasonal adjustment every March looks like a boom
and every April like a crash.

---

## 13. Clustering — district archetypes

- **HDBSCAN** primary: no `k` required, handles noise, leaves genuinely odd districts
  as outliers instead of forcing them into a cluster
- **K-means (k=5–8)** alongside, for interpretable labels
- Compare the two. Where they disagree, investigate.

---

## 14. Forecasting

| Target | Horizon | Method |
|---|---|---|
| District monthly incorporations | 12m | SARIMA (fiscal seasonality); Prophet where breaks exist |
| State energy deficit % | 12m | SARIMA |
| State GST collections | 6m | SARIMA + trend |

**Always benchmark against a seasonal-naive baseline (same month last year) and report
the comparison via MASE.** A forecast that doesn't beat seasonal-naive is not a forecast,
and publishing that honestly is worth more than a good-looking chart.

Always show prediction intervals. A bare forecast line implies certainty you do not have.

---

## 15. Reproducibility

Every score row stores `weight_version_id`. Every weight vector is persisted in
`meta.weight_version` with its method and JSONB weights.

**Any historical score must be exactly reproducible from its weight version + load
version.** If it isn't, the pipeline has a bug.
