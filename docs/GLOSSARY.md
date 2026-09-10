# GLOSSARY.md — Bound Vocabulary

**Owner:** Lead Orchestrator · Referenced by `CLAUDE.md § 5` · **Binding on code, UI, docs and slides**

Terms here are **bound**: the listed word is the only word used for the concept, in identifiers, in API
fields, in UI labels, and in the presentation. Synonyms are listed so they can be rejected in review.

The reason this file has teeth: "outlier score", "anomaly score" and "risk index" are three different
quantities in this system. A document that uses them interchangeably is not sloppy prose — it is a
document that cannot be audited, and it invites a judge's question we would answer badly.

## A — Domain terms

| Term | Definition | Not to be called |
|---|---|---|
| **Burn-in** | Accelerated stress (elevated temperature and bias) applied to precipitate latent defects before delivery. MIL-STD-883 Method 1015. | "baking", "stress test" |
| **ESS** | Environmental Stress Screening: the wider screening flow burn-in sits inside. | — |
| **Latent defect** | A defect present but not detectable by a pass/fail measurement at time zero, which manifests under stress or in service. | "hidden failure", "soft fail" |
| **Escape** | A defective part that passes every absolute limit at every read-point and is therefore shipped. In this project, ground-truth defective **and** inside all limits at all read-points. | "miss", "leaker" |
| **Escape Set** | `S1 ∪ S2` — the evaluation subset on which static screening scores `LER = 0` by construction. | "hard cases" |
| **Read-point** | A scheduled electrical measurement during burn-in: `0, 24, 96, 168 h`. | "timestep", "epoch", "checkpoint" |
| **Interim electrical test** | The standard's term for a measurement taken partway through burn-in. | — |
| **Delta limit** | A normative screening criterion on the *change* between two read-points (MIL-PRF-38535). | "drift threshold" |
| **PDA** | Percent Defective Allowable: the lot-level rejection criterion (default 5 %). | "yield limit", "AQL" |
| **Absolute limit** | The datasheet/profile min–max for a parameter. Violation is a hard fail that supersedes everything. | "spec limit" is acceptable prose but the field is `absolute_limit` |
| **Lot** | A manufacturing/assembly batch sharing process history; the reference population for lot-relative screening. | "batch", "group" |
| **Cohort** | The specific reference population for one part: same lot, same type, same read-point, `status = OK`, **self excluded**. | "peer group", "neighbours" |
| **Thermal zone** | A region of the burn-in chamber with a measurably distinct temperature. | "shelf", "area" |
| **Socket** | The physical position holding one part on a burn-in board. | "slot", "site" |
| **Activation energy (`Ea`)** | The Arrhenius exponent term for a degradation mechanism, in eV. | — |
| **Acceleration factor (AF)** | `exp[(Ea/k_B)(1/T_ref − 1/T_zone)]`; converts oven hours to equivalent hours at a reference temperature. | "speed-up" |
| **Equivalent field hours** | Screening hours × AF, at the stated `Ea`. Always reported *with* the `Ea` used. | "lifetime" — we do not predict lifetime |

## B — Statistical terms

| Term | Definition | Not to be called |
|---|---|---|
| **PAT** | Part Average Testing (AEC-Q001): screening against limits derived from the parts themselves. | — |
| **SPAT** | Static PAT: limits fixed across lots. | — |
| **DPAT** | **Dynamic** PAT: limits recomputed per lot from that lot's robust statistics. Module A's anchor. | "adaptive limits" |
| **Robust sigma** | `IQR / 1.35` (`1.35 ≈ 2·Φ⁻¹(0.75) = 1.349`). The AEC-Q001 scale estimate. | "sigma", "std dev" — it is neither |
| **`σ_MAD`** | `1.4826 × MAD`; the primary scale when `n < 20`. | "MAD" alone (MAD is the unscaled median absolute deviation) |
| **Robust distance (`z`)** | `(x − median) / robust scale`. Signed. | "z-score" — that implies mean and standard deviation, which we deliberately do not use |
| **PAT limit** | `median ± k · robust sigma`, `k` default 6. | "control limit" — SPC control limits are a different construct |
| **Tukey fence** | `Q1 − k_t·IQR`, `Q3 + k_t·IQR`; `k_t = 1.5` mild, `3.0` extreme. Severity banding only. | — |
| **Medcouple (`MC`)** | Robust skewness measure driving the adjusted-boxplot fences. | — |
| **MCD** | Minimum Covariance Determinant: robust location/scatter estimator behind M5. | — |
| **Mahalanobis `D²`** | `(x−μ)ᵀΣ⁻¹(x−μ)` using MCD estimates; joint-anomaly detector. | "multivariate score" |
| **Joint-only anomaly** | A part whose every univariate margin is normal but whose parameter *combination* is off-manifold. | "correlated outlier" |
| **Conformal prediction** | Distribution-free procedure giving a finite-sample coverage guarantee under exchangeability. | "confidence interval", "error bar" |
| **`q̂(1−α)`** | The `⌈(n_cal+1)(1−α)⌉`-th smallest signed calibration residual. | "quantile" without qualification |
| **Mondrian conformal** | Group-conditional conformal: quantiles computed within groups. | "stratified conformal" (acceptable in prose, but the field is `mondrian_*`) |
| **Exchangeability** | The assumption that calibration and test observations are drawn from a jointly exchangeable distribution. Its violation voids the guarantee. | "i.i.d." — weaker and not what conformal requires |
| **Neyman–Pearson classification** | Threshold selection that bounds the prioritised error rate (here FNR ≤ `α`) while minimising the other. | "cost-sensitive learning" |
| **Coverage** | The measured fraction of test parts whose truth falls inside the bound. Always reported with a Clopper–Pearson interval. | "accuracy" |
| **Leave-one-out** | Excluding the part under test from its own cohort statistics. | "cross-validation" — different concept |

## C — Project-specific terms

| Term | Definition |
|---|---|
| **LATENTIS** | The system's codename (LATENT-defect Inspection & Screening). |
| **Module A** | Dynamic lot-relative outlier detection (`models/anomaly/ANOMALY_SPEC.md`). |
| **Module B** | Predictive delta-limit screening: 0 h + 24 h → 168 h (`models/drift/DRIFT_SPEC.md`). |
| **Shape–Amplitude model** | `V̂168 = v0 + (v24 − v0) · Φ_g(168)` — population shape, per-part amplitude. |
| **`Φ_g(168)`** | The single scalar per group carrying the population degradation shape to the horizon. |
| **`TracedValue`** | The carrier for every decision-bearing number: value, unit, formula, operands, parameters, versions. |
| **Provenance Ledger** | The four-level provenance system (`docs/PROVENANCE_SPEC.md`). |
| **Formula registry** | Append-only map `formula_id → (expression, callable, unit rule, source ref)`. |
| **Re-derivation rate** | Fraction of decision-bearing fields recomputable from their own payload. Target 100 %, audited by `RT-007`. |
| **Safety slope** | `(limit_high − v0)(1 − margin_fraction) / horizon_hours`, or `Δ_max / horizon_hours` where a delta limit exists. **Derived from configuration, never a universal constant.** |
| **`slope_ratio`** | `predicted_long_slope / safety_slope`. The band driver. |
| **Band** | `SAFE` / `WATCH` / `EARLY_WARNING` / `REJECT`. Computed from the conformal **bound**, not the point estimate. |
| **`EARLY_WARNING`** | Exceeds the safety slope while staying inside the absolute limit. The band that exists only because we forecast. |
| **Severity** | `NOMINAL` / `ELEVATED` / `ANOMALOUS` / `SEVERE` / `ABSOLUTE_FAIL` — Module A presentation bands. **Not a threshold** (`ANOMALY_SPEC § 5.1`). |
| **`risk_index`** | The decomposable worklist-ordering index. **Never** a probability, never rendered as a percentage. |
| **Attribution** | `PART` / `SOCKET` / `ZONE` / `TESTER` / `INDETERMINATE` — what the evidence points at. |
| **Mission Risk Posture** | The operator-facing name for `α`, exposed with its false-positive cost visible. |
| **Exchangeability guard** | The detector that declares our own conformal guarantee `DEGRADED` or `VOID`. |
| **`LER`** | Latent Escape Recall: recall on the Escape Set. The headline metric, always reported beside FPR and flag rate. |
| **Stratum** | `S0`–`S5` difficulty class (`DATASET_SPEC § 7`). |
| **Decoy** | `S3`/`S4`/`S5` — parts or lots that must **not** be flagged. |
| **Guard** | A named degenerate-case handler with defined behaviour (`reduced_power`, `zero_iqr`, `NO_VARIATION`, `censored`, `amplitude_clipped`). |

## D — Three distinctions that must never blur

**1. Severity ≠ threshold ≠ risk index.**
*Severity* is a presentation band from the robust distance. The *operating threshold* `τ` is calibrated
by Neyman–Pearson and decides `flagged`. The *risk index* orders the worklist. Three quantities, three
names, three fields. Merging any two would hide a hard-coded threshold, which INV-1 forbids.

**2. Anomalous ≠ defective.**
The system detects *statistical abnormality relative to a stated reference population*. It does not
observe a defect mechanism. Permitted: *"is a lot-relative outlier at 17.4 robust σ"*. Forbidden:
*"is defective"*, *"has an oxide defect"* (INV-9).

**3. Predicted ≠ measured.**
`V̂168` and `Û168` are forecasts from two observations. `value_168h` in `truth.parquet` is a withheld
measurement, visible **only** to the evaluation harness. Any UI element mixing the two outside
evaluation mode is a leak (INV-4), including in a screenshot.

## E — Banned words

| Banned | Use instead | Why |
|---|---|---|
| "may be defective" | the measured statement, e.g. "sits 17.4 robust σ above its lot median" | Hedge that hides a missing number (`EXPLAINABILITY_SPEC § 6`) |
| "AI-powered" | the actual method name | Says nothing, invites distrust |
| "confidence: N %" (uncalibrated) | "measured coverage: N % (95 % CI …)" | A calibration claim we must have measured |
| "accuracy" (for the screening task) | AUPRC / LER / FPR | Meaningless at 3 % prevalence |
| "real-time" | the measured latency | Unbounded claim |
| "predicts failure" | "predicts the 168 h parametric value" | We forecast a measurement, not an event |
| "ISRO data" | "synthetic data modelled on published standards" | INV-3, and it is the one error that would disqualify us |
| "validated" (of the physics model) | "grounded in", "consistent with" | We have not validated against real devices |
| "guaranteed" (unqualified) | "guaranteed under exchangeability; guard reports when void" | The assumption is part of the claim |
