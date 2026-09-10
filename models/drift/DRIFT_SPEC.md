# DRIFT_SPEC.md — Module B: Predictive Delta-Limit Screening

**Owner:** Data + ML Engineer · Implements FR-301..FR-310 · Grounded in D-A-04, D-B-01/03, D-H-02

## 1. Framing

Delta limits — screening on the *change* between pre- and post-burn-in measurements — are already
normative in military/space microcircuit specifications (D-A-04). Module B makes that criterion
**predictive**: instead of waiting 168 h and then applying a delta limit, forecast the 168 h value
from the 0 h and 24 h reads and act at 24 h.

This framing matters. "Predictive delta-limit screening" is a phrase a reliability engineer
recognises. "AI drift prediction" is a phrase they distrust. Same system, and the first one is
accurate.

**Operational value:** a decision at 24 h instead of 168 h removes 144 h of oven occupancy for
rejected parts. We state that as a *capability of the workflow*, and we do not attach a cost saving
we have not measured.

## 2. The identifiability constraint (read this before writing any code)

Inputs are `Value_0h` and `Value_24h`. Two observations ⇒ **two degrees of freedom per part**.

- **Identifiable:** one baseline + one amplitude.
- **Not identifiable:** curvature, exponent, time constant, or any second shape parameter.

Any model that appears to fit a per-part nonlinear curve from two points is borrowing its shape from
somewhere else and should declare where. Ours declares it explicitly. This is the question a strong
judge will ask, and the answer is the design.

## 3. Features — allow-list enforced in code (FR-301, LK-1)

| Feature | Source |
|---|---|
| `v0` | 0 h reading |
| `v24` | 24 h reading |
| `delta_24 = v24 − v0` | Derived |
| `rel_delta_24 = (v24 − v0) / max(|v0|, ε)` | Derived (scale-free) |
| `v0_lot_z`, `v24_lot_z` | Lot-relative robust z from Module A at those read-points |
| `lot_median_v0`, `lot_median_delta_24`, `lot_robust_sigma_delta_24` | Cohort context (leave-one-out) |
| `component_type` | Static |
| `temperature_c_mean_0_24`, `af_arrhenius` | Actual measured zone temperature and its AF |
| `voltage_v` | Static bias |
| `n_lot`, `data_quality_score` | Context, and drives the guards |

**Forbidden, and enforced:** anything at 96 h or 168 h, any label, `stratum`, `is_escape`,
`degradation_mode`, any generator state, and any aggregate computed over the test split. The
implementation holds a literal allow-list; `TEST-DL-001` asserts the fitted model's input schema
equals it exactly. A feature not on the list cannot enter by accident.

## 4. The Shape–Amplitude model (FR-302)

### 4.1 Formulation

```
value_i(t) = v0_i + A_i · Φ_g(t)          with  Φ_g(24) ≡ 1  (normalisation)
A_i        = v24_i − v0_i                  (the per-part amplitude — identifiable)
V̂168_i    = v0_i + (v24_i − v0_i) · Φ_g(168)
```

`Φ_g` is the **population degradation shape** for group `g = (component_type, parameter)`, fitted on
**training lots only** using their full 0/24/96/168 h trajectories. Exactly one scalar per group is
needed at inference: `Φ_g(168)`.

### 4.2 Candidate shape families

| Family | Form (normalised so `Φ(24)=1`) | Motivation |
|---|---|---|
| Power law | `(t/24)^n` | NBTI/TDDB-like power-law degradation (D-B-03) |
| Log-time | `log(1+t/τ) / log(1+24/τ)` | Log-time relaxation behaviour |
| Saturating | `(1−e^(−t/τ)) / (1−e^(−24/τ))` | Mechanisms that exhaust |
| Linear | `t/24` ⇒ `Φ(168) = 7` | The **baseline**, and the degenerate case of the power law at `n=1` |

Selection: per group, by out-of-sample MAE on the training folds, with a parsimony tie-break. The
selected family, its parameter, and its fit quality are **published** in the model card and
displayed in the UI's Model Info surface as a plotted curve an engineer can look at and dispute.

### 4.3 Why this is the right answer

- **Identifiable** from two points — nothing is invented per part.
- The only quantity borrowed across parts is the *shape*, which is exactly what physics says is
  shared within a mechanism and a technology, while the *amplitude* is what varies per part.
- It **contains** the naïve baseline: if the fitted `Φ_g(168) = 7`, the model *is* linear
  extrapolation. So we can never do worse than the baseline by more than fit error, and the
  comparison is a fair one.
- `Φ_g(168)` is one number per group. An inspector can be told: *"in this family, 168 h drift is
  typically 3.1× the 24 h drift, not 7×"* — and that sentence is the entire model.
- Sub-linear shapes mean linear extrapolation **over-predicts** (D-B-03), so the baseline is
  *conservative but noisy*: it inflates false positives. Quantifying that trade-off is a real result.

### 4.4 Residual correction (FR-304)

```
V̂168_final = V̂168_shape + r̂(features)
```

`r̂` is Ridge (primary) or `HistGradientBoostingRegressor` (adopted **only if** it beats Ridge on
out-of-sample MAE by more than the seed-to-seed spread). Ridge coefficients are published with
signs; GBT is explained with exact TreeSHAP. The residual model captures lot-context effects the
population shape cannot — e.g. hotter zones drifting faster than `AF` alone predicts.

If neither model beats the plain shape model, **both are deleted** (AG-10).

## 5. Uncertainty — the conformal upper bound (FR-305)

**The rejection decision uses the bound, never the point estimate.** See `models/CONFORMAL_SPEC.md`
for the full construction, coverage tests, Mondrian grouping and the exchangeability guard. In brief:

```
Û168(1−α) = V̂168_final + q̂_g(1−α)
q̂_g(1−α)  = ⌈(n_cal_g + 1)(1−α)⌉-th smallest signed residual (y − ŷ) in Mondrian group g
```

One-sided, because only *under*-prediction is dangerous. For a two-sided parameter (`vth_shift`) two
one-sided bounds are computed and the relevant one is used per direction.

## 6. Safety criterion (FR-306) — derived, never a universal constant

There is no universal engineering constant for "safe drift". The criterion is **derived from
configuration**, and the derivation is shown to the inspector.

### 6.1 Definitions

```
observed_early_slope_i  = (v24 − v0) / 24                                     [unit/h]
predicted_long_slope_i  = (V̂168_final − v0) / 168                            [unit/h]
```

### 6.2 Safety slope

```
usable_margin  = (limit_high − v0) · (1 − margin_fraction)     # margin_fraction default 0.20
safety_slope   = usable_margin / horizon_hours                 # horizon_hours default 168
```

- `limit_high` — the profile's absolute limit for the parameter (config).
- `margin_fraction` — the configured reserve held back for post-screen life, tester
  reproducibility, and temperature variation. **Default 0.20, `assumed` provenance, exposed in the
  UI, and swept in sensitivity analysis.** It is a policy input, not a discovered truth, and we say so.
- `horizon_hours` — the screening horizon; optionally extended to a mission horizon via the
  Arrhenius AF (FR-309), which converts oven hours to equivalent field hours.

Where a profile supplies an explicit **delta limit** `Δ_max(p)` (as military drawings do, D-A-04),
that limit takes precedence and `safety_slope = Δ_max / horizon_hours`. The system prefers the
specified engineering criterion over its own derivation whenever one exists — which is the correct
order of authority.

### 6.3 Predicted margin and the decision

```
predicted_margin      = limit_high − Û168(1−α)        # uses the BOUND
predicted_margin_pct  = predicted_margin / (limit_high − v0)
slope_ratio           = predicted_long_slope / safety_slope
```

| Band | Condition | Meaning |
|---|---|---|
| `SAFE` | `Û168 < limit_high − usable_margin` and `slope_ratio < 0.7` | Comfortable |
| `WATCH` | `slope_ratio` in `[0.7, 1.0)` | Inside criterion, trending |
| `EARLY_WARNING` | `slope_ratio ≥ 1.0` but `Û168 < limit_high` | Exceeds the safety slope while staying inside the absolute limit — **this is the flagship band** |
| `REJECT` | `Û168 ≥ limit_high` | The upper bound crosses the absolute limit |

**`EARLY_WARNING` is the whole product.** It is the band that exists only because we forecast, and
it is empty under conventional screening.

Using `Û168` rather than `V̂168` means the boundary is crossed *earlier*, deliberately: the FN
sensitivity requirement is satisfied by the construction of the rule, not by a tuned threshold. The
cost is more false positives at small `α`, and the NP-ROC makes that cost visible.

## 7. Insufficient data (FR-303, FR-308)

| Case | Behaviour |
|---|---|
| Missing `v0` or `v24` | `INSUFFICIENT_DATA` with the missing read-point named. **No imputation of a decision input** — imputing a value we then treat as measured would be fabrication. |
| `v24` censored (`BELOW_LOD` / `OVERRANGE`) | Interval-censored handling: use the censoring bound in the *conservative* direction and mark `censored: true` |
| Group has no fitted `Φ_g` | Fall back to the parent group (type-agnostic, parameter-specific), then to linear; the fallback level is reported |
| `n_cal_g` too small for the requested `α` | Fall back to the marginal (non-Mondrian) quantile, mark `mondrian: false`, and report the widened basis |
| Exchangeability guard fires | `guarantee_status: VOID`; use the most conservative available bound; banner in UI and in the report |

## 8. Output contract

```json
{
  "component_id": "C-L2026-041-0137", "parameter": "iddq_standby", "unit": "uA",
  "inputs": {"v0": 12.1, "v24": 18.7, "delta_24": 6.6},
  "shape": {"group": "CMOS_LOGIC/iddq_standby", "family": "power_law", "n": 0.58,
            "phi_168": 3.06, "fitted_on_lots": 26, "fallback_level": 0},
  "prediction": {"point": 32.3, "baseline_linear": 58.3, "residual_correction": 1.1},
  "bound": {"upper_168h": 39.8, "alpha": 0.10, "coverage_target": 0.90,
            "mondrian_group": "CMOS_LOGIC", "n_cal": 412, "q_hat": 7.5,
            "guarantee_status": "VALID"},
  "slopes": {"observed_early": 0.2750, "predicted_long": 0.1202,
             "safety_slope": 0.1804, "slope_ratio": 0.666, "unit": "uA/h"},
  "margin": {"absolute_limit": 50.0, "predicted_margin": 10.2, "predicted_margin_pct": 0.269,
             "equivalent_field_hours": 4012.5, "ea_ev": 0.7},
  "band": "WATCH",
  "guards": {"censored": false, "exchangeability": "PASS", "insufficient_data": false},
  "provenance": {"model_version": "drift-1.0.0", "profile_id": "mil_std_883_like@2",
                 "dataset_hash": "sha256:...", "data_provenance": "SYNTHETIC"}
}
```

Note `baseline_linear: 58.3` sitting beside `point: 32.3`. The baseline is **in the payload**, so the
UI can show *"naïve linear extrapolation would have predicted 58.3 µA and rejected this part; the
fitted population shape predicts 32.3 µA and the 90 % upper bound is 39.8 µA"*. That is a false
positive avoided, visible, with its arithmetic — and it is a far better demo moment than another
red flag.

## 9. Evaluation obligations

MAE / RMSE / MedAE per parameter in physical units; **Tail MAE** on the top decile of true drift;
per-stratum MAE with `S2` called out; calibration curve of the point model; conformal coverage
(marginal and per group) with binomial bands; mean and median interval width; Winkler score; and the
ablation ladder: linear baseline → shape → shape+residual → +conformal. All mean ± std over 5 seeds.

Expected and *predicted in advance* (so it is a test of the theory, not a post-hoc story): the
linear baseline should show a clear **positive bias** on 168 h values, because `Φ` is sub-linear
(D-B-03). If it does not, either the generator or our understanding is wrong, and we investigate
before publishing anything.
