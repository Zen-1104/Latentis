# FINAL_STATUS.md — What Is Actually True

This is the file that decides what the README, the deck and the demo are allowed to claim. If a slide and this
file disagree, **this file wins** and the slide is wrong (`docs-ppt-engineer` non-negotiable 3).

Owned by `lead-orchestrator`. Capability statuses are reconciled against the `INTEGRATION_STATUS.md` gate table
at every phase boundary and before any tag (`T-706`).

## Vocabulary (`CLAUDE.md § 4`), applied without slack

| Status | Means | Allowed on a slide as |
|---|---|---|
| **Specified** | Written in a spec. No code. | "designed", "specified" |
| **Implemented** | Code exists and runs. Correctness unproven. | "implemented" |
| **Verified** | Implemented + a passing *meaningful* test, named. | "verified by `<test-id>`" |
| **Measured** | A number from a real pipeline run, reproducible, artifact committed. | the number + its artifact path |
| **Target** | A goal not yet met. | "target", never as a result |

**Snapshot date:** 2026-09-05 · **Phase:** 0 · **Tag:** none

---

## § Capability status

Everything is `Specified`. That is the honest total after Phase 0, and stating it plainly now is what makes the
later upgrades believable.

| # | Capability | Status | Evidence required to advance |
|---|---|---|---|
| C-01 | Lot-relative dynamic outlier detection (AEC-Q001 DPAT) | Specified | `T-303` + `TEST-STAT-004..006` |
| C-02 | Multivariate anomaly with exact additive contribution decomposition | Specified | `T-304` + `TEST-STAT-007..009` |
| C-03 | Part / socket / zone / tester attribution | Specified | `T-305` + `TEST-ATTR-001..005`, `RT-006` |
| C-04 | Two-point 168 h forecast via Shape–Amplitude decomposition | Specified | `T-306`, `T-307` + `TEST-DRIFT-001..006` |
| C-05 | Distribution-free upper bound `Û168` (split conformal, signed) | Specified | `T-308` + `TEST-CONF-001..003`, empirical coverage |
| C-06 | Mondrian group-conditional calibration with a visible fallback level | Specified | `T-308` + `TEST-CONF-004`, `E2E-S4-001` |
| C-07 | Exchangeability guard (six signals, `PASS`/`WARN`/`VOID`) | Specified | `T-309` + `RT-011` |
| C-08 | Safety-slope criterion and the four bands | Specified | `T-310` + `TEST-SAFE-001..004` |
| C-09 | `EARLY_WARNING` — rejection 144 h before the standard's criterion is measurable | Specified | `T-310`, `T-406` |
| C-10 | Decomposed `risk_index` with `sum_check`, unable to cross a band boundary | Specified | `T-311` + `TEST-RISK-001..005`, `RT-010` |
| C-11 | Neyman–Pearson operating point under an explicit FNR ceiling | Specified | `T-402` + `TEST-NP-001..002` |
| C-12 | Full provenance on every decision-bearing value (`TracedValue`) | Specified | `T-314`, `T-506` + `QG-API-02` |
| C-13 | Independent re-derivation of every displayed number | Specified | `T-701` + `RT-007` (publishes the rate) |
| C-14 | Four-layer explanation generated from the deciding values | Specified | `T-313` + `TEST-EXPL-001..004`, `RT-007` |
| C-15 | Synthetic corpus with strata `S0`–`S5`, decoys, and a non-empty Escape Set | Specified | `T-206`, `T-209` (**release blocker**) |
| C-16 | Reproducibility: same seed ⇒ byte-identical dataset and identical metrics | Specified | `T-705` + `QG-REL-03` |
| C-17 | Eight UI surfaces, four states each, no browser-side arithmetic | Specified | `T-602`..`T-604` + `RT-003`, `QG-FE-03` |
| C-18 | Offline operation: fresh clone, no network, ending in a rendered PDF | Specified | `T-704` + `QG-REL-05`, `TEST-OFFLINE-001` |
| C-19 | UI / API / PDF agreement on every sampled value | Specified | `T-701` + `RT-012` |
| C-20 | Model cards, machine-validated, for both modules | Specified | `T-405` + `QG-MODEL-01` |

**Measured numbers:** none. `reports/METRICS_<tag>.json` does not exist. Any number currently appearing in a
worked example anywhere in this repository is **illustrative** and is tracked for reconciliation by `BL-002`.

---

## § Known Limitations

These are known **now**, before any code exists, from the design itself. Each one is stated here so it can be
volunteered in the presentation rather than discovered by a judge — which costs about twenty seconds and is the
highest-leverage credibility move available to us.

Numbers are marked `PENDING` where the limitation has a magnitude we have not measured. A `PENDING` that is still
`PENDING` at tag time is reported as `PENDING`, not omitted and not estimated.

| # | Limitation | Consequence | Magnitude |
|---|---|---|---|
| L-01 | **All data is synthetic.** No ISRO or vendor operational data is used, present, or implied. | Every metric describes our generator, not a fab. Generalisation to real silicon is **unknown**, not "expected to hold". | n/a — structural |
| L-02 | The generator's drift model is constructed from published mechanism models and has **not** been validated against physical measurements. | If the real `Φ(t)` differs in shape, the Shape–Amplitude advantage over linear extrapolation changes in an unknown direction. | `HUMAN-005` |
| L-03 | The AEC-Q001 DPAT formula is cited at **MEDIUM** confidence from a secondary source. | If `k` or the `1.35` divisor is not as we read it, `D-001`/`D-003` are revised. | `BL-001` / `HUMAN-002` |
| L-04 | Conformal coverage holds **under exchangeability**, which a drifting test floor violates. | Our answer is the guard (`C-07`), which detects the violation and widens the bound — it does not restore the guarantee. | coverage under shift: PENDING `T-402` |
| L-05 | Two observations cannot identify a per-part curve shape. | Group misassignment degrades the forecast, and a genuinely atypical part gets a group-typical shape. | PENDING `T-403` |
| L-06 | Only `Φ_g(168)` is calibrated; intermediate-hour forecasts are interpolation, not validated predictions. | We do not claim a 96 h forecast even though the arithmetic would produce one. | n/a — scope |
| L-07 | Lot sizes below the DPAT robustness floor fall through a documented ladder to weaker estimators. | Small-lot verdicts carry `--evidence-weak` and are labelled as such on screen. | floor value: `T-303` |
| L-08 | The five risk weights are `assumed`, not derived. | Mitigated structurally: `RT-010` proves no weight vector moves a part across a band boundary. Not mitigated by claiming the weights are optimal. | `RT-010` result PENDING |
| L-09 | Isolation Forest is advisory and provably cannot change a verdict. | Interaction-shaped anomalies it alone catches are surfaced as review prompts, not rejections. | disagreement rate PENDING `T-403` |
| L-10 | DuckDB embedded: no concurrent writers, single-process ingest. | Not a multi-user production system. Fine for a test cell; stated rather than implied. | n/a — architectural |
| L-11 | E2E is **Chromium-only** at two viewports. | Cross-browser behaviour is **untested**, not verified. | `D-032` |
| L-12 | No authentication or authorisation on the API. | It binds to localhost for the demo. Exposing it on a network would expose every endpoint to anyone who can reach the port — a real deployment needs an auth layer we have not built. | n/a — see below |
| L-13 | Latent Escape Recall has a small denominator (the Escape Set only). | Always reported with a Clopper–Pearson interval, never as a bare point estimate. | interval width PENDING `T-406` |
| L-14 | The 20 % `margin_fraction` and the 168 h horizon are configuration defaults, not derived optima. | Both are swept in `reports/SENSITIVITY.md` so the reader can see how much they matter. | PENDING `T-404` |
| L-15 | No accelerated-life model links our synthetic hours to field hours. | We never convert 168 h into a field-life claim. | n/a — scope |
| L-16 | Lot-level runs are slow on small hardware (Phase 5 coder-measured: 116 parts in 30.3 s, ~0.26 s/part; single-part investigation ~0.2 s is within target). | NFR-02 / API_CONTRACT § 10 lot-analysis targets are **not met** and not claimed. Per-part answers stay interactive; full-lot runs are batch operations until profiled optimisation lands. | measured `5d5d8b7` (D-047) |

**On L-12:** the API has no authentication because the demo is a single-user localhost application, and adding a
half-built auth layer would be worse than none. It is listed as a limitation rather than a non-goal because
anyone taking this beyond a demo must add one first — and it is the kind of thing that quietly never gets added
if nobody writes it down.

---

## § Open Decisions

Things we do not yet know, as distinct from choices we have not made. Choices live in `DECISIONS.md`.

| # | Question | Resolves at | If it resolves badly |
|---|---|---|---|
| O-01 | Does the corpus contain a part with `V̂168 < limit_high ≤ Û168`? | `T-206` | `RT-005` reports `NOT_RUN`; a stratum is added (`BL-004`) |
| O-02 | What `k` gives the NP-constrained optimum on `calib`? | `T-402` | Nothing — this is what calibration is for |
| O-03 | Is Mondrian level 0 attainable for every group at `α = 0.10`? | `T-402` | Level 1–3 fallbacks render, visibly (`C-06`) |
| O-04 | Does the sub-linear `Φ` leave the linear baseline competitive? | `T-403` | We publish that it does. `D-006` accepted this risk deliberately |
| O-05 | Is the re-derivation rate exactly 1.0? | `T-702` | Anything below 1.0 is a release-blocking defect, not a metric to report |
| O-06 | Can the eight-minute demo script fit five acts? | `HUMAN-009` | Acts are cut in the order below, not rushed |
| O-07 | Does the offline bootstrap complete on a clean machine? | `T-704` | `QG-REL-05` fails; `C-18` downgrades to `Implemented` |

---

## § Cut order

The order in which scope is surrendered if time runs out. Decided now, while nothing is at stake, because the
same decision made at 2 a.m. on 29 September will be made badly. Referenced by `.claude/agents/lead-orchestrator.md`.

**Cut from the bottom up. Never out of order, and never silently — a cut updates this file and the deck.**

| Order | Cut | Why it is safe to lose | Cost |
|---|---|---|---|
| 1 | S8 Export polish (keep the PDF; drop styling refinement) | The PDF's *content* is what `RT-012` needs; its typography is not | cosmetic |
| 2 | S7 Model Card surface (the card still exists as a validated file) | A judge can read the file; `QG-MODEL-01` is unaffected | one surface |
| 3 | `E2E-PERF-001..003` | Performance is a claim we can simply not make | one claim, honestly dropped |
| 4 | S5 Posture dial (fix `α = 0.10`, expose it in config) | The mechanism stays; only the interactive control goes | the best live-demo moment |
| 5 | CQR (keep plain split conformal) | Coverage guarantee is unchanged; only adaptive width is lost | wider bounds |
| 6 | Isolation Forest cross-check | Advisory by construction (`D-020`); nothing depends on it | one review prompt |
| 7 | Zonal / GDBN attribution (keep part / socket / tester) | Three of four attribution classes still work | `RT-006` row 4 becomes `NOT_RUN` |
| 8 | Journeys J3 and J5 (keep J1, J2, J4) | J1 is the escape story, J2 the forecast, J4 the failure path | `QG-REL-02` partial |

**Never cut, in any circumstance:** `TracedValue` provenance (`C-12`), the re-derivation audit (`C-13`), the
Escape Set non-emptiness check (`C-15` / `T-209`), reproducibility (`C-16`), the offline path (`C-18`), the
`SYNTHETIC` labelling (INV-3), or any red-team suite. Those seven *are* the submission. A version of this project
with fewer features and all seven intact is strictly stronger than a feature-complete one missing any of them —
because the first can be checked and the second cannot.

---

## § Reconciliation log

| Date | Phase | Capabilities `Verified` | Capabilities `Measured` | Gates passed | Reconciled by |
|---|---|---|---|---|---|
| 2026-09-05 | 0 | 0 of 20 | 0 of 20 | 0 of 18 (none applicable) | lead-orchestrator |


