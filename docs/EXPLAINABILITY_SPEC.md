# EXPLAINABILITY_SPEC.md — Explanation as a Computed Artifact

**Owner:** Data + ML Engineer + Backend Engineer · Implements XR-01..XR-08, FR-408..FR-410
**Grounded in D-I-01, D-I-02 · Enforced by INV-5 and `RT-007`**

## 1. The standard we hold ourselves to

The SIH criterion is: *the system must justify its classification to a QA inspector.* We translate
that into one falsifiable test, and then we build backwards from it.

> **The re-derivation test.** Take the API payload for any flagged part. Using **only** the numbers
> and formula expressions inside that payload, an independent script recomputes every displayed
> quantity and reproduces the verdict. Target: **100 % of decision-bearing fields**. Machine-checked
> by `RT-007` on every release tag; the measured rate is published in `reports/METRICS_<tag>.json`.

This is a stronger and much less common claim than "we use SHAP". SHAP tells you which feature
mattered. Re-derivation proves the *number itself* was computed and not composed. It also makes INV-1
mechanically enforceable: a fabricated value has no formula and no operands, so it fails the audit
immediately rather than surviving in a chart.

## 2. The four layers, in the order an inspector uses them

| Layer | Question it answers | Mechanism |
|---|---|---|
| **L1 — Verdict** | *What are you telling me to do?* | Band + two independent verdicts (PAT, absolute) + recommendation with its trigger text |
| **L2 — Arithmetic** | *Show me the numbers.* | `TracedValue` + formula registry: expression string with operands substituted |
| **L3 — Attribution** | *Which parameter/feature drove this?* | Exact Mahalanobis contributions; Ridge coefficients; exact TreeSHAP; per-member firing table |
| **L4 — Counterfactual** | *What would change your mind?* | Solved thresholds: the value/limit/`α`/`k` at which the verdict flips |

L1 and L2 are **P0** — no release without them. L3 is P0 for the members actually shipped. L4 is P1
but it is the layer that wins the demo, because it is the only one that answers a question the
inspector was going to ask anyway.

## 3. L2 — the formula registry (the mechanism that makes this work)

`backend/core/explain/formulas.py` holds an **append-only** registry:

```python
FormulaSpec(
    formula_id   = "dpat.limit_high",
    expression   = "median + k * (IQR / 1.35)",
    description  = "AEC-Q001 Dynamic PAT upper limit from robust lot statistics",
    operands     = ("median", "k", "IQR"),
    parameters   = ("divisor",),
    unit_rule    = "same_as:median",
    source_ref   = "D-CD-02",
    fn           = lambda median, k, IQR, divisor=1.35: median + k * (IQR / divisor),
)
```

One entry serves three consumers, which is the whole point:

1. the numeric core **computes** with `fn`;
2. the API **ships** `expression`, `operands`, and their values inside the `TracedValue`;
3. the UI's *"Show the arithmetic"* panel **renders** `expression` with operands substituted —
   it never contains a formula of its own.

Consequences that follow structurally rather than by discipline:

- The frontend performs **no arithmetic on decision values** (`ARCHITECTURE § 1`). A `*` or `+` on a
  decision quantity in `frontend/src` is a lint failure (`QG-FE-03`).
- Changing a formula means a **new `formula_id`** (`ARCHITECTURE § 7.2`), because a disposition
  recorded three years ago must still re-derive with the formula that produced it.
- `source_ref` ties each formula to a research finding, so *"why divide by 1.35?"* has a citation, not
  an opinion. (`1.35 ≈ 2·Φ⁻¹(0.75) = 1.349`, from D-CD-02.)
- `RT-007` walks every `TracedValue` in a response, evaluates `expression` against `inputs` and
  `parameters` using a restricted evaluator, and asserts equality with `value` to `1e-9`.

### 3.1 Registry coverage requirement

Every decision-bearing quantity has an entry. The initial set (each with a unit rule and a source
reference): cohort statistics (`median`, `q1`, `q3`, `iqr`, `robust_sigma`, `mad`, `sigma_mad`), DPAT
limits and z, Tukey and adjusted-boxplot fences, Mahalanobis `D²` and its contributions, the shape
prediction `V̂168`, the linear baseline, the conformal bound, all three slopes, `usable_margin`,
`predicted_margin`, `slope_ratio`, the Arrhenius AF and equivalent field hours, each risk component,
`risk_total`, and `pda_pct`. `TEST-EXPL-002` asserts that no response contains a `formula_id` absent
from the registry, and no registry entry is unreachable from any response.

## 4. L3 — attribution, and what we refuse to use

| Method | Where | Why it, and not the alternative |
|---|---|---|
| Exact Mahalanobis contribution decomposition | M5, multivariate anomaly | `(x−μ)_q · [Σ⁻¹(x−μ)]_q` is **exact and sums to `D²`**. KernelSHAP would *approximate* a quantity we can decompose in closed form — strictly worse and slower |
| Ridge coefficients × standardised feature values | Drift residual model (primary) | Linear and additive: the contribution *is* the coefficient times the input. Nothing to approximate |
| Exact TreeSHAP | Drift residual model, only if GBT is adopted | Polynomial-time exact Shapley values for tree ensembles; the only sampling-free option for GBT |
| Per-member firing table (`members_fired / members_total`) | Module A aggregate | Max-severity aggregation is not additive, so a *decomposition* would be a fiction. The honest explanation is which members fired and which stayed silent |
| **Rejected: LIME** | — | Local surrogate with sampling noise; two runs can disagree, which is fatal for an auditable record |
| **Rejected: pipeline-wide KernelSHAP** | — | Approximate, slow, and unnecessary where exact decompositions exist |
| **Rejected: attention/saliency** | — | No neural model in the system, deliberately |

Standing rule: **where an exact decomposition exists, an approximate one is a defect.**

## 5. L4 — counterfactual thresholds (FR-410)

Counterfactuals are computed by **inverting the shipped formula**, analytically where the formula is
invertible and by bisection on the real decision function where it is not — never by a heuristic
sentence.

| Counterfactual | Question | Method |
|---|---|---|
| Value-to-nominal | *How much lower would `v24` have to be for this part to pass PAT?* | Invert `z = (x − med)/rσ` at the operating threshold |
| Limit-sensitivity | *At what absolute limit would this part have been rejected by static screening?* | Solve `limit = max value over read-points` |
| `k`-sensitivity | *At what `k` does the PAT verdict flip?* | `k* = |z_dpat|`; reported directly |
| `α`-sensitivity | *At what Mission Risk Posture does the band change?* | Bisection over the conformal quantile ladder |
| Margin-sensitivity | *At what `margin_fraction` does this part leave `EARLY_WARNING`?* | Invert `slope_ratio = 1` |
| Cohort-sensitivity | *Would this part still flag in a different lot?* | Recompute against the type-level cohort; report both |

Each returns a `TracedValue` plus a sentence built from it, e.g.:

> *"This part flags at any `k` below 17.4. The configured `k` is 6, and the AEC-Q001 default is 6, so
> the verdict is not sensitive to that choice."*

That last clause matters: the counterfactual is what lets us say the verdict is **robust to the
configuration**, which is the most common line of attack on a threshold-based system.

## 6. Narrative generation — templates for *language*, values from *computation*

Narratives are assembled from fragments whose slots accept **only** `TracedValue` references. The
generator is a pure function of the payload; there is no free-text field anywhere in the pipeline.

```
"{component_id} reads {observed} {unit} for {parameter} at {read_point} h. Its lot cohort
 ({cohort_n} sibling parts, self excluded) has median {median} {unit} and robust sigma
 {robust_sigma} {unit}, so this part sits {z} robust sigma above its lot — while the absolute
 limit of {absolute_limit} {unit} is not violated ({margin_pct} % margin remains).
 {attribution_clause} {drift_clause} {recommendation_clause}"
```

Hard constraints, each with a test:

1. **No numeric literal in any template.** `TEST-EXPL-001` regex-scans templates for digits outside
   slot names and fails on a match.
2. **Every slot resolves to a `TracedValue`** in the same payload that produced the verdict (INV-5).
   An unresolved slot is an error, never an empty string and never a plausible default.
3. **Uncertainty is stated, not smoothed.** `reduced_power`, `mondrian_level > 0`,
   `guarantee_status != VALID`, and `censored` each inject a mandatory clause that cannot be
   suppressed by configuration.
4. **Hedge vocabulary is bound** (`docs/GLOSSARY.md`): *"is a lot-relative outlier"* (measured) vs.
   *"is predicted to exceed"* (forecast, with a bound) vs. *"may be"* — which is banned outright,
   because it is the word that hides a missing number.
5. **No causal language.** The system may say *"iddq_standby contributes 71 % of `D²`"*. It may not say
   *"caused by an oxide defect"* — we did not measure a mechanism (INV-9).

## 7. Worked example — the canonical demo part

Payload → narrative, with every number arriving from a `TracedValue` (values illustrative of the
format; the demo renders whatever the pipeline computes):

> **C-L2026-041-0137 · `iddq_standby` · 24 h — ANOMALOUS (lot-relative), PASSES absolute limit**
>
> The part reads **45.2 µA**. Its lot cohort (187 sibling parts, this part excluded) has median
> **10.4 µA** and robust sigma **2.0 µA** (`IQR/1.35`, `IQR = 2.7 µA`), giving a Dynamic PAT upper
> limit of **22.4 µA** at `k = 6` (AEC-Q001 default). The part sits **17.4 robust sigma** above its
> lot median and **fails Dynamic PAT** while **passing** the 50 µA absolute limit with 9.6 % margin.
>
> Five of five univariate members fired. Robust Mahalanobis gives `D² = 41.7` (`p = 1.2e-7`), of which
> `iddq_standby` contributes **71 %**. Its socket's median offset is **0.3 σ** and its thermal zone's
> is **0.2 σ**, so the anomaly is **not** explained by setup: attribution is **PART**.
>
> Forecast to 168 h: **32.3 µA** point, **39.8 µA** at the 90 % one-sided conformal upper bound
> (measured coverage for this group: 91.2 %, 95 % CI 87.9–93.8 %). Naïve linear extrapolation would
> have said 58.3 µA. Predicted long-term slope **0.1202 µA/h** against a safety slope of
> **0.1804 µA/h** → `slope_ratio = 0.67` → band **WATCH**.
>
> **This part flags at any `k` below 17.4.** Static screening at the 50 µA limit would have passed it
> at every read-point.
>
> Recommendation: **INVESTIGATE**. Basis: `SEVERE` lot-relative anomaly with band `WATCH` — the two
> modules disagree, and the disagreement is reported rather than averaged.

Every bold quantity in that paragraph is a `TracedValue` with a `formula_id`, and `RT-007` recomputes
all of them from the payload alone.

## 8. Anti-patterns, banned explicitly

| Anti-pattern | Why it is banned |
|---|---|
| "AI-powered analysis suggests…" | Says nothing; hides the method |
| "Confidence: 94 %" with no calibration measurement | A fabricated calibration claim (INV-1, INV-9) |
| A feature-importance bar chart as the *whole* explanation | Global importance does not explain *this part* |
| A narrative written before the numbers exist | INV-5; and it is how fabricated demos are built |
| Rounding differently in UI and report | Same `display_precision` from the same `TracedValue`, or `RT-007` fails |
| Suppressing a guard warning to keep the UI clean | The warning *is* the explanation in that case |
| Explaining Isolation Forest's score as a reason | It is a cross-check, never a verdict (`ANOMALY_SPEC § 4.6`) |

## 9. Verification obligations

| Test | Asserts |
|---|---|
| `RT-007` | Re-derivation rate over every decision-bearing field; **target 100 %** |
| `TEST-EXPL-001` | No numeric literal in any narrative template |
| `TEST-EXPL-002` | Registry coverage both ways: no unknown `formula_id`, no unreachable entry |
| `TEST-EXPL-003` | Counterfactual round-trip: applying the returned counterfactual value flips the verdict as promised |
| `TEST-EXPL-004` | Guard clauses present whenever the corresponding guard flag is set |
| `RT-004` | ID-permutation invariance — shuffling `component_id`s changes no verdict and no explanation |
| `RT-012` | UI ↔ API ↔ PDF agreement on every displayed number for a sampled part (Playwright + payload diff) |

`RT-012` is the one that closes the loop end to end: the same part, three surfaces, byte-identical
numbers. It is also the test most likely to catch a well-intentioned frontend developer formatting a
value into a different rounding — which is a real bug, because a report that disagrees with the screen
destroys the audit trail the whole design exists to provide.
