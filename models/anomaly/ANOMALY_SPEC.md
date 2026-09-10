# ANOMALY_SPEC.md — Module A: Dynamic Lot-Relative Outlier Detection

**Owner:** Data + ML Engineer · Implements FR-201..FR-210 · Grounded in D-CD-01..04

## 1. The question this engine answers

> *Is this component unusual **relative to its own lot, type, parameter, operating zone and
> read-point** — even while it sits inside every absolute limit?*

Not "is this part bad" (that requires physics we do not have) and not "is this part unusual among
all parts ever" (that is SPAT, and it is looser). The reference population is the thing that makes
the answer meaningful, so the reference population is **always** reported with the answer.

## 2. Reference population (the cohort)

For part `i`, parameter `p`, read-point `t`, the cohort is:

```
cohort(i,p,t) = { j : lot(j)=lot(i) ∧ type(j)=type(i) ∧ status(j,p,t)=OK ∧ j ≠ i }
```

Three things are load-bearing:

- **`j ≠ i` — leave-one-out.** The part under test is excluded from its own median and IQR. For
  `n = 30` including the part biases the centre toward it and *masks* the anomaly; for `n = 3` it is
  fatal. Closes LK-5. `TEST-STAT-002`.
- **`status = OK`** — censored and non-measured readings never enter a limit calculation.
- **Zonal refinement.** If `thermal_zone` is recorded and `n_zone ≥ n_min_zone` (default 20), a
  **second** cohort restricted to the zone is evaluated in parallel. Both results are reported; the
  divergence between them *is* the signal for zone attribution (§ 7).

If `n < 3`, the engine returns `INSUFFICIENT_COHORT` and defers to absolute limits with an explicit
warning. It never invents a statistic from two points.

## 3. Pre-processing

### 3.1 Unit normalisation
All values converted to the profile's canonical unit before any statistic. A cohort containing
mixed units is a **validation error**, not a computation.

### 3.2 Variance-stabilising transform
Leakage parameters are strongly right-skewed (D-B-04), which inflates the upper IQR and *loosens*
the upper limit — precisely the wrong direction for FN sensitivity. So:

- Candidate transforms: `identity`, `log1p`, `Box–Cox` (λ fitted on **training lots only**).
- Selection: per `(component_type, parameter)` by a fitted criterion (Anderson–Darling statistic
  of the transformed cohort), decided once at model-build time and **frozen in the model artifact**.
- The chosen transform and its λ are reported in every response's provenance.
- **Limits are computed in transformed space and inverse-transformed for display**, so the inspector
  always sees µA, never log-µA. The arithmetic panel shows both.

Skipping this step is the most likely quiet error in Module A, because DPAT's symmetric `± 6σ` form
implicitly assumes symmetry.

## 4. Ensemble members

All five run on every `(part, parameter, read-point)`. Isolation Forest runs as a cross-check.

### 4.1 M1 — DPAT (primary, AEC-Q001 anchored)

```
med  = median(cohort)                       # "Robust Mean" in AEC-Q001 terms
IQR  = Q3(cohort) − Q1(cohort)
rσ   = IQR / 1.35                           # 1.35 ≈ 2·Φ⁻¹(0.75) = 1.349
PAT_high = med + k·rσ ,  PAT_low = med − k·rσ         # k default 6
z_dpat   = (x − med) / rσ                             # signed robust distance
```

Reported as: the five statistics, the two limits, the signed `z_dpat`, and a `PASS`/`FAIL` verdict
against the PAT window separate from the absolute-limit verdict. **The two verdicts are never
merged** — the whole point is that they can disagree.

*Quantile convention:* linear interpolation (`numpy` default, "type 7"). Stated explicitly because
Q1/Q3 differ across conventions and a reviewer recomputing by hand needs to know which one.
`TEST-STAT-001` pins it with a hand-computed known answer.

### 4.2 M2 — MAD-z (primary when `n < 20`)

```
MAD  = median(|x_j − med|)
σ_MAD = 1.4826 · MAD                        # consistent for Gaussian
z_mad = (x − med) / σ_MAD
```

`1.4826 = 1/Φ⁻¹(0.75)`. Used as the primary robust scale when `n < 20`, because the `1.35` divisor
is documented as inexact below that size (D-CD-02). A finite-sample correction factor `c(n)` is
applied and tabulated in the artifact (RQ-03). MAD has the highest possible breakdown point (50 %),
which is exactly what a small cohort needs.

### 4.3 M3 — Tukey fences (severity banding)

`Q1 − k_t·IQR`, `Q3 + k_t·IQR` with `k_t = 1.5` (mild) and `k_t = 3.0` (extreme) — used to *band*
severity in language an inspector already knows from box plots, not to make the primary decision.

### 4.4 M4 — Adjusted boxplot (skew-aware)

```
MC = medcouple(cohort)
low  = Q1 − 1.5 · exp(−3·MC) · IQR
high = Q3 + 1.5 · exp(+3·MC) · IQR
```

For right-skewed data (`MC > 0`) this widens the upper fence and tightens the lower — the
statistically correct asymmetry. Exists because M1's symmetry assumption is wrong for leakage, and
it is the honest alternative to pretending the transform in § 3.2 fully fixes skew. Sign convention
must be verified against Hubert & Vandervieren before release (RQ-04, `TEST-STAT-006`).

### 4.5 M5 — Robust Mahalanobis (MCD) — the joint detector

```
(μ_MCD, Σ_MCD) = MinCovDet(support_fraction=0.75).fit(cohort_matrix)   # all parameters at read-point t
D² = (x − μ_MCD)ᵀ Σ_MCD⁻¹ (x − μ_MCD)
p  = 1 − χ²_cdf(D², df = n_parameters)
contribution_q = (x − μ)_q · [Σ⁻¹ (x − μ)]_q       # exact, additive, sums to D²
```

Requires `n ≥ 5·n_parameters`; otherwise skipped with a stated reason (never silently). This is the
only member that can see a part whose every individual margin is fine but whose *combination*
breaks the lot's correlation structure (`DATA_GENERATION_SPEC § 5.1`). The per-parameter
contribution decomposition is **exact and additive** — the reason we prefer it to KernelSHAP.

If the ablation table shows `joint_only` recall does not improve with M5, **M5 is deleted** (AG-10).

### 4.6 M6 — Isolation Forest (cross-check only, never a verdict)

Fixed seed, `n_estimators=200`. Its output is displayed in a panel explicitly labelled
*"non-parametric cross-check — does not affect the verdict"*. Present because judges will ask about
ML methods, and because a disagreement between M6 and M1–M5 is genuinely informative as a
"look again" signal. Absent from the decision path because its score has no physical meaning and
cannot be re-derived by an inspector.

## 5. Aggregation — max severity with unanimity reporting

```
severity(part) = max over (parameters × members) of member_severity
```

Severity bands, computed from the primary robust distance:

| Band | Rule (`|z|` against the primary robust scale) | Meaning |
|---|---|---|
| `NOMINAL` | < 3 | Within ordinary lot variation |
| `ELEVATED` | 3 ≤ · < 4.5 | Watch; usually not actionable alone |
| `ANOMALOUS` | 4.5 ≤ · < 6 | Below the AEC-Q001 PAT limit but clearly separated |
| `SEVERE` | ≥ 6 | Outside the DPAT window |
| `ABSOLUTE_FAIL` | Outside an absolute limit | Hard fail; supersedes everything (FR-210) |

**Why max, not average.** Averaging lets four quiet members bury one loud one — a textbook route to
a false negative, which the problem statement calls catastrophic. Max is conservative in the
direction the mission requires. The cost is a higher false-positive rate, which is why the response
also carries `members_fired` / `members_silent`: the inspector sees *"1 of 5 fired"* versus
*"5 of 5 fired"* and calibrates accordingly. Unanimity is reported, never used to soften the verdict.

An explicit consequence we accept and state: a single-member firing at `SEVERE` produces a `SEVERE`
part. That is intended.

### 5.1 Bands are not the threshold

The 3 / 4.5 / 6 boundaries are **presentation bands** grounded in the AEC-Q001 `k = 6` anchor. The
*operating threshold* that decides `flag` vs. `no flag` is chosen separately by § 6. Conflating the
two would be a hidden hard-coded threshold, which INV-1 forbids.

## 6. Threshold calibration — Neyman–Pearson (FR-209)

Bands are a display convention; the flag decision is calibrated.

```
Given calibration set C with labels, prioritised class = defective, target FNR ≤ α:
  1  score every part in C with the aggregate anomaly score s
  2  τ = the order statistic of { s_j : j defective in C } such that at most
       ⌊α·(n_def+1)⌋ − 1 defective scores fall below τ         (NP-style order-statistic rule)
  3  flag(part) ⟺ s(part) ≥ τ
  4  report the resulting FPR and flag rate at τ, and the whole NP-ROC curve
```

- `α` is the **Mission Risk Posture** (default 0.10), exposed in the UI with its FP cost visible.
- The exact order statistic and its confidence `δ` must be derived and unit-tested, not assumed
  (RQ-05, `TEST-NP-002`). We state the guarantee as *"FNR ≤ α with confidence ≥ 1 − δ on
  exchangeable data"* — with `δ` computed, or we do not state it at all.
- `τ` is fitted on `calib` **only** (LK-6) and frozen into the model artifact.
- If `n_def` in `calib` is too small for the requested `α`, the engine **refuses** and reports the
  minimum achievable `α`. Silently returning a threshold that cannot support the requested bound
  would be the worst possible failure here.

## 7. Attribution — part vs. socket vs. zone (FR-208)

Our extension of wafer-space GDBN into burn-in-oven space (D-CD-04), motivated by MSA practice
(D-I-03). For an anomalous part:

```
z_part  = robust distance vs. lot cohort
z_sock  = robust distance vs. its socket's other parts (across lots, same socket)
sock_med_offset = median(socket parts) − median(lot)   in robust σ
zone_med_offset = median(zone parts)   − median(lot)   in robust σ
```

| Verdict | Condition | Recommendation |
|---|---|---|
| `PART` | `z_part` high **and** `sock_med_offset` small **and** the part is an outlier *within* its own socket | Genuine part anomaly → disposition |
| `SOCKET` | The whole socket is shifted coherently, and the part is *typical* within its socket | **Retest in a different socket before disposition** |
| `ZONE` | The whole thermal zone is shifted, consistent with its recorded temperature via Arrhenius | Zonal DPAT limits apply; usually not a part defect |
| `TESTER` | Anomaly correlates with `tester_id` and drifts monotonically with `read_timestamp` | Flag for tester calibration |
| `INDETERMINATE` | Evidence conflicts, or position metadata absent | Report the conflict; recommend retest |

Two consequences worth stating plainly: (1) a `SOCKET` verdict means we **decline to condemn the
part** — in a live demo, the system protecting a good part is more persuasive than another red flag;
(2) attribution requires position metadata, and where it is absent the engine degrades to part-only
analysis and *says so* rather than guessing (KL-06).

## 8. Output contract

```json
{
  "component_id": "C-L2026-041-0137",
  "parameter": "iddq_standby",
  "read_point_h": 24,
  "observed": {"value": 45.2, "unit": "uA", "formula_id": "raw.measurement", "...": "TracedValue"},
  "cohort": {"n": 187, "n_excluded_self": 1, "scope": "lot+type", "zone_cohort_n": 46},
  "lot_statistics": {"median": 10.4, "q1": 9.1, "q3": 11.8, "iqr": 2.7,
                     "robust_sigma": 2.0, "transform": "log1p", "boxcox_lambda": null},
  "dpat": {"k": 6, "limit_low": -1.6, "limit_high": 22.4, "z": 17.4, "verdict": "FAIL"},
  "absolute": {"limit_high": 50.0, "verdict": "PASS", "margin": 4.8, "margin_pct": 9.6},
  "members": {"dpat": "SEVERE", "mad_z": "SEVERE", "tukey": "EXTREME",
              "adjusted_boxplot": "SEVERE", "mahalanobis": {"d2": 41.7, "p": 1.2e-7,
              "top_contributions": [{"parameter": "iddq_standby", "share": 0.71}]}},
  "members_fired": 5, "members_total": 5,
  "cross_check": {"isolation_forest": {"score": -0.41, "note": "does not affect verdict"}},
  "severity": "SEVERE",
  "percentile_in_lot": 99.5,
  "flagged": true,
  "threshold": {"tau": 6.12, "alpha": 0.10, "calibrated_on": "calib", "n_def_calib": 214},
  "attribution": {"verdict": "PART", "z_part": 17.4, "socket_median_offset_sigma": 0.3,
                  "zone_median_offset_sigma": 0.2},
  "guards": {"small_cohort": false, "zero_iqr": false, "reduced_power": false},
  "provenance": {"model_version": "anomaly-1.0.0", "dataset_hash": "sha256:...",
                 "profile_id": "mil_std_883_like@2", "data_provenance": "SYNTHETIC"}
}
```

Every numeric field is a `TracedValue` in the real payload (abbreviated above for readability).
The **flagship row** is `dpat.verdict = FAIL` next to `absolute.verdict = PASS`. That single
juxtaposition is the whole problem statement, rendered as data.

## 9. Degenerate cases — exact required behaviour

| Case | Behaviour |
|---|---|
| `n < 3` | `INSUFFICIENT_COHORT`; defer to absolute limits; explicit warning |
| `3 ≤ n < 20` | MAD path with `c(n)` correction; `reduced_power: true`; UI warning |
| `IQR = 0`, `MAD > 0` | Use MAD; record `zero_iqr: true` |
| `IQR = 0` **and** `MAD = 0` | `NO_VARIATION`; defer to absolute limits; **never** produce `inf` or `NaN` |
| Part is the cohort median | `z = 0`; not an error |
| All cohort values censored | `INSUFFICIENT_COHORT` |
| Mixed units in cohort | Validation error upstream; the engine is never reached |
| `n < 5·n_parameters` | M5 skipped, reason reported |

`RT-009` asserts every row of this table. A crash or an `inf` on any of them is a P0 defect —
these are exactly the inputs a red team will send first.

## 10. Ablation obligations

| Configuration | Purpose |
|---|---|
| Absolute limits only | Establishes `LER = 0` on the Escape Set |
| Classical mean ± 3σ | Demonstrates masking: the outlier corrupts the statistics meant to detect it |
| DPAT only (`k = 6`) | The standards baseline every extension must beat |
| DPAT + MAD | Small-`n` contribution |
| + adjusted boxplot | Skew contribution |
| + Mahalanobis | **Joint-only** recall contribution (its sole justification) |
| + Zonal | Zone-confound contribution |
| + NP threshold vs. fixed `k = 6` | Calibration contribution |
| Full | Headline |

Reported as `LER`, FPR, flag rate and F2, mean ± std over 5 seeds. **Any member that does not
improve the metric it exists to improve is removed from the product** (AG-10). This table is the
scientific content of Module A; the code is just its implementation.

