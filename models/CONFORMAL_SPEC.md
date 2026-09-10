# CONFORMAL_SPEC.md — Distribution-Free Uncertainty for the Rejection Decision

**Owner:** Data + ML Engineer · Implements FR-305, FR-307, MLR-06 · Grounded in D-H-02

## 1. Why this document exists separately

The conformal bound is the single most attackable claim in the project, because it is the one place
we say the words *"finite-sample guarantee"*. If that claim is loose, a reliability engineer will
find it in one question. So the construction, the assumptions, the failure mode and the measurement
of the guarantee all live in one auditable place instead of being scattered through model code.

The claim we make, in full, and never abbreviated in the UI:

> Under exchangeability between the calibration set and the part under test, the one-sided upper
> bound `Û168(1−α)` covers the true 168 h value with marginal probability ≥ `1 − α`. Coverage is
> **measured** on a held-out test split and reported per Mondrian group with binomial confidence
> intervals. When the exchangeability guard fires, we state that the guarantee is **void** for that
> part and fall back to a conservative rule.

Everything below is what makes each clause of that paragraph true.

## 2. Split conformal — the construction (FR-305)

Three **disjoint, lot-disjoint** splits: `train` (fit `Φ_g` and the residual model), `calib` (fit
nothing but the quantiles), `test` (scored once per release tag).

```
1  Fit the point model M on `train` only.
2  On `calib`, for each part i and parameter p:
       s_i = y_i − ŷ_i                        # SIGNED residual, not absolute
3  Sort the s_i ascending within the Mondrian group g.
4  k        = ⌈(n_cal_g + 1)(1 − α)⌉
5  q̂_g(1−α) = s_(k)                            # k-th smallest; if k > n_cal_g the bound is +∞
6  At inference: Û168 = ŷ + q̂_g(1−α)
```

### 2.1 Details that are load-bearing, and the reason for each

- **Signed, not absolute residuals.** Absolute residuals give a *two-sided* interval and waste half
  the width on the direction we do not care about. Only under-prediction is dangerous: a part
  predicted at 30 µA that actually reaches 55 µA is an escape; one that reaches 12 µA is not.
- **`⌈(n+1)(1−α)⌉`, not `⌈n(1−α)⌉`.** The `+1` is what makes the coverage bound *finite-sample*
  rather than asymptotic. Getting this wrong is the classic conformal implementation bug, so it is
  pinned by a hand-computed test with a tiny `n` (`TEST-CONF-001`).
- **`k > n_cal_g` ⇒ the bound is `+∞`, and we say so.** With `α = 0.05` and `n_cal_g = 15`,
  `⌈16 × 0.95⌉ = 16 > 15`: the requested confidence is not attainable from that calibration set. The
  engine does **not** silently return the maximum residual. It reports `bound: INFINITE`,
  `attainable_alpha = 1/(n_cal_g+1)`, and the part is routed to `INSUFFICIENT_CALIBRATION`. Returning
  a finite number here would be inventing confidence we do not have.
- **Ties** are handled by the sorted order statistic directly; no interpolation, because interpolated
  conformal quantiles do not carry the same finite-sample statement.
- **Per parameter and per direction.** `vth_shift` is two-sided (`DATASET_SPEC § 4`), so it gets two
  one-sided bounds from two signed-residual sets, and the band logic uses whichever direction the
  part is drifting in. A single symmetric interval would be wrong for it.

## 3. Mondrian (group-conditional) conformal — FR-307

Marginal coverage is a weak promise: a method can hit 90 % overall while covering only 60 % of
`POWER_MOSFET` parts and 98 % of `SRAM` parts. For a screening tool that is unacceptable — the
under-covered group is exactly where escapes concentrate.

So quantiles are computed **within groups**:

```
g = (component_type, parameter)            # primary grouping
```

with a documented fallback ladder when a group is too small:

| Level | Group | Condition to use it |
|---|---|---|
| 0 | `(component_type, parameter)` | `n_cal_g ≥ n_min_mondrian` (default 50) **and** `k ≤ n_cal_g` |
| 1 | `(parameter)` | Level 0 unavailable |
| 2 | marginal (all parts) | Level 1 unavailable |
| 3 | `INSUFFICIENT_CALIBRATION` | Even marginal cannot support `α` |

The level actually used is in the payload as `mondrian_level` and shown in the UI. A widened
grouping is a real weakening of the conditional guarantee, and hiding it would be the quiet kind of
dishonesty this project is built to avoid.

**Considered and deferred:** conditioning additionally on thermal zone or on a binned predicted
value. Both further fragment `n_cal`, and the honest trade-off (conditional validity vs. attainable
`α`) needs the measured coverage table to settle. Tracked as R17.

## 4. CQR — adopted only if it earns it

Split conformal on a mean-regression model gives a **constant-width** band: `q̂_g` does not depend on
the part. But drift uncertainty plainly grows with drift magnitude — a part with `delta_24 = 0.1 µA`
and one with `delta_24 = 12 µA` should not receive the same `±` width.

Conformalised Quantile Regression fixes that:

```
1  Fit q_lo, q_hi at levels α/2, 1−α/2 on `train`   (QuantileRegressor or GBT quantile loss)
2  Conformity score on calib:  E_i = max(q_lo(x_i) − y_i,  y_i − q_hi(x_i))
3  q̂_CQR = ⌈(n_cal+1)(1−α)⌉-th smallest E_i
4  Interval: [q_lo(x) − q̂_CQR,  q_hi(x) + q̂_CQR]   → we use the upper end only
```

CQR keeps the same finite-sample coverage while allowing the width to vary with `x`.

**Adoption rule (AG-10):** CQR ships only if, on the test split, it achieves coverage within the
binomial CI of the target **and** a smaller mean interval width than split conformal. If it is wider
or under-covers, split conformal ships and the CQR code is deleted rather than kept as an unused
option. Both are measured in `reports/COVERAGE_<tag>.md`.

## 5. The exchangeability guard — declaring our own guarantee void

Conformal coverage assumes calibration and test data are exchangeable. Burn-in data breaks that
assumption routinely and *for real reasons*: a new lot from a shifted process, a re-calibrated
tester, an oven zone running hot. The literature is explicit that coverage degrades under
distribution shift (D-H-02). Most implementations ignore this. We detect it and say so.

### 5.1 Signals (computed at inference, all from screening-visible data only)

| Signal | Statistic | Fires when |
|---|---|---|
| Feature shift | Population Stability Index of each model input, lot vs. calibration | `PSI > 0.25` on any input |
| Lot-centre shift | Robust z of `lot_median_v0` vs. the calibration distribution of lot medians | `|z| > 3` |
| Amplitude shift | KS statistic of `delta_24` distribution, lot vs. calibration | `p < 0.01` |
| Temperature | `mean(temperature_c)` outside the calibration temperature range | Outside observed range |
| Tester novelty | `tester_id` unseen in calibration | Unseen |
| Group novelty | `(component_type, parameter)` unseen in calibration | Unseen |

Thresholds are **configuration with `assumed` provenance**, exposed in the profile and swept in
sensitivity analysis. PSI `> 0.25` is the conventional "significant shift" band in credit-risk
monitoring practice and is used because it is a *published convention we can name*, not because we
tuned it.

### 5.2 Verdicts and behaviour

| Verdict | Trigger | Behaviour |
|---|---|---|
| `PASS` | No signal fires | Normal bound, `guarantee_status: VALID` |
| `WARN` | One signal, PSI in `[0.10, 0.25]` | Bound used, `guarantee_status: DEGRADED`, banner, reason listed |
| `VOID` | Any signal at its firing threshold, or group novelty | `guarantee_status: VOID`; use `max(q̂_g, q̂_marginal, q̂_conservative)` where `q̂_conservative` is the `1−α/2` quantile; UI banner; recorded in the report and in the disposition snapshot |

A `VOID` verdict never suppresses the analysis — it makes the analysis more conservative and labels
it. Silence would be the failure. `RT-011` red-teams this by injecting a synthetic lot shift and
asserting the guard fires and the banner reaches the exported PDF.

## 6. Measuring coverage — the obligation

Coverage is not asserted, it is measured on `test` and published:

```
empirical_coverage_g = (1/n_g) · Σ 1[y_i ≤ Û_i]
```

Reported per group and marginally, each with a **Clopper–Pearson 95 % interval**, because a group
with `n = 40` will bounce around 90 % by pure chance and a bare point estimate invites both false
alarm and false comfort. The test is: *is the target inside the interval?* — not *is the point
estimate ≥ the target?*

Also reported: mean and median interval width in physical units, the Winkler interval score (which
penalises both under-coverage and needless width, so it cannot be gamed by widening), and a coverage
histogram over deciles of predicted drift, which is where miscoverage hides.

`TEST-CONF-002` is a synthetic end-to-end test with a known noise distribution, asserting empirical
coverage lands inside its binomial interval for `α ∈ {0.20, 0.10, 0.05}`. `TEST-CONF-003` asserts the
monotonicity property: smaller `α` ⇒ wider bound ⇒ weakly more rejections, never fewer.

## 7. What conformal prediction does **not** give us

Stated here so it can be stated in the demo, and so no slide over-claims (INV-9):

1. **Not per-part validity.** The guarantee is marginal (or group-conditional), not conditional on the
   individual part. We report the group level so the audience knows how conditional it actually is.
2. **Not a statement about defectiveness.** It bounds the 168 h *measured value*. A part can be inside
   its bound and still be a bad part; the bound is about the forecast, not the physics.
3. **Not valid under shift** — § 5 exists precisely because of this, and it is the honest response.
4. **Not free.** Smaller `α` means wider bounds means more false positives. The Mission Risk Posture
   dial exposes that trade-off to the operator instead of hiding a chosen value in code.
5. **Not a replacement for the absolute limit.** The absolute limit is authoritative; the bound only
   decides whether we predict the part will cross it.

## 8. Output fields

```json
"bound": {
  "upper_168h": 39.8, "alpha": 0.10, "coverage_target": 0.90,
  "q_hat": 7.5, "method": "split_conformal", "score": "signed_residual",
  "mondrian_group": "CMOS_LOGIC/iddq_standby", "mondrian_level": 0, "n_cal": 412,
  "k_order_statistic": 372, "guarantee_status": "VALID",
  "exchangeability": {"verdict": "PASS", "max_psi": 0.07, "signals_fired": []},
  "measured_coverage_this_group": {"value": 0.912, "n_test": 388,
                                   "ci95": [0.879, 0.938], "source": "reports/COVERAGE_v0.4.0.md"}
}
```

`measured_coverage_this_group` is the field that converts a theoretical claim into an auditable one:
the UI can show the *measured* coverage for exactly this group next to the *target*, sourced from a
committed artifact. That is the difference between "conformal prediction guarantees 90 %" and "we
measured 91.2 % (95 % CI 87.9–93.8 %) on 388 held-out parts of this group".

