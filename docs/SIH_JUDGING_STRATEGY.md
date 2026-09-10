# SIH_JUDGING_STRATEGY.md — Mapping the Build to the Evaluation

**Owner:** Lead Orchestrator · Internal document · Implements JR-01..JR-07

## 1. The stated criteria, and what actually moves each one

| SIH criterion | What a weak submission does | What we do | Where it is evidenced |
|---|---|---|---|
| **Anomaly Detection Score** (FN catastrophic) | Reports accuracy or AUROC on a balanced set | **LER on the Escape Set**, always beside FPR and flag rate; threshold set by a Neyman–Pearson rule that *bounds* FNR at a chosen `α` | `reports/METRICS_<tag>.json`, `ABLATION_<tag>.md` |
| **Drift Prediction Accuracy** (MAE vs. hidden truth) | Fits a curve per part and reports overall MAE | MAE/RMSE/MedAE per parameter in physical units, **Tail MAE** on the top drift decile, per-stratum with `S2` broken out, **plus** the naïve-linear baseline in every table | `reports/METRICS_<tag>.json` |
| **Explainability** (justify to a QA inspector) | Adds a SHAP bar chart | **Re-derivation rate**: every displayed number recomputable from its own payload, machine-checked at 100 % target; four explanation layers ending in counterfactuals | `RT-007` output in `reports/METRICS_<tag>.json` |

The pattern is the same in all three rows: convert a subjective criterion into a **number we measure and
publish**, and hand the judge the artifact. A judge who can verify a claim scores it higher than one who
must trust it.

## 2. Where marks are actually won and lost

Scoring rubrics vary, but the failure modes are consistent across every hackathon of this type:

| Common failure | Our structural defence |
|---|---|
| Demo runs on fixtures | No mock path exists in the production build (`UX_SPEC § 7`); import-graph enforced |
| Metrics in the slides are aspirational | INV-1 + `RT-008` scan: a number presented as a result must resolve to a committed `reports/` artifact |
| Cannot answer "why this part?" | Ledger drawer to the source file row |
| Cannot answer "why this threshold?" | AEC-Q001 anchor + `k`-sensitivity counterfactual + NP calibration |
| Synthetic data presented as real | INV-3, single-member enum, banner on every surface and every PDF page |
| Breaks when a judge clicks something unexpected | `RT-009` degenerate-case suite; four designed states per surface |
| Team cannot explain its own model | The whole model is one number per group, `Φ_g(168)`, published as a curve |
| Nothing distinguishes it from other submissions | § 3 |

## 3. The four differentiators to say out loud

Ten are listed in `README.md`. In a judging conversation, only these four survive compression:

1. **It is an implementation of existing normative practice, plus a measured extension.** AEC-Q001 DPAT
   and MIL-PRF-38535 delta limits are real, cited, and named. Most submissions invent a heuristic; we
   implement a standard and then extend it, which is the difference between "clever" and "credible".

2. **Rejection decisions use a conformal upper bound, not a point estimate.** Distribution-free,
   finite-sample, one-sided — and we *measure* the coverage per group and publish it with binomial
   intervals. This is the strongest available answer to "false negatives are catastrophic", because it is
   a stated guarantee with a stated assumption rather than a good recall number.

3. **The system declares when its own guarantee is void.** The exchangeability guard fires on lot shift,
   tester novelty, temperature excursion, or unseen group, sets `guarantee_status: VOID`, widens the
   bound, and banners it into the exported PDF. Almost nothing in this space does this, and it is the
   single most persuasive honesty signal we have.

4. **Every number is re-derivable from its own payload, and that rate is a published metric.** Not "we
   have explainability" — a measured 100 % re-derivation rate audited by a test. It also makes fabrication
   structurally impossible, which is the claim that matters most in a domain like this one.

If asked for one sentence: *"We implement the aerospace/automotive standard for lot-relative screening,
make its delta-limit criterion predictive with a distribution-free bound, and prove every number on
screen is computed rather than composed."*

## 4. Adversarial questions, prepared

| Question | Answer |
|---|---|
| "Your data is synthetic, so your metrics are meaningless." | The metrics measure whether the *method* recovers structure we injected and documented — sub-linear degradation, lot-relative outliers inside limits, thermal confounds, joint-only anomalies. The generator was written against a frozen spec **before** the detector (visible in git history), every parameter carries a provenance tag, and `Φ` is deliberately sub-linear, which makes the data *harder* for our own method than a linear alternative would. We also publish the decoy strata that must **not** be flagged. |
| "You tuned the generator to make your model look good." | The generator cannot import the model (`TEST-ARCH-001`), labels are derived from rendered values rather than intent, and `reports/SENSITIVITY.md` reports our metrics across a sweep of the per-part shape spread — including the region where we degrade. |
| "`k = 6` is arbitrary." | It is AEC-Q001's default, cited. And the counterfactual shows this part flags at any `k < 17.4`, so the verdict does not depend on the choice. Separately, the *operating* threshold is not `k` at all — it is calibrated by Neyman–Pearson on `calib` only. |
| "Two points cannot determine a curve." | Correct, and that is the design. Two points give one baseline and one amplitude. The shape is fitted on the *population* and published as a curve. We never claim per-part curvature, and the model contains the linear baseline as a special case at `Φ(168) = 7`. |
| "Conformal prediction assumes exchangeability, which burn-in data violates." | Agreed — which is why we implemented a guard that detects shift and declares the guarantee void. Here it is firing on an injected lot shift. |
| "Where is the deep learning?" | Deliberately absent. 40 lots, 3 % prevalence, and a requirement that an inspector re-derive the arithmetic. A neural model would be less accurate here *and* unauditable. The rejection is documented with reasons in `research/ML_METHOD_RESEARCH.md`. |
| "Would this work on real ISRO data?" | Unknown, and we will not claim otherwise. What transfers is the method, the profile abstraction (limits/`k`/`α`/`Ea` are configuration, not code), and the evaluation protocol. What would be required is re-fitting `Φ_g` and re-calibrating conformal quantiles on real lots — and the model card names exactly that. |
| "Your false-positive rate must be terrible." | Here is the number, beside LER, at the configured `α`, plus the NP-ROC. And here is the false positive the *baseline* would have produced on this very part — 58.3 µA by linear extrapolation against a 50 µA limit — that our fitted shape avoids. |
| "What happens with a 3-part lot?" | `reduced_power` path with the MAD estimator and a finite-sample correction; below 3 parts we return `INSUFFICIENT_COHORT` and defer to absolute limits. It is in the degenerate-case suite, `RT-009`, which is a table of required behaviours rather than a hope. |
| "Can I try to break it?" | Yes. Upload anything. The validation report itemises findings by row with the action taken, and every `5xx` in a test run is a P1 defect for us. |

## 5. Submission artifacts

| Artifact | Content rule |
|---|---|
| Presentation (10–12 slides) | `presentation/PRESENTATION_SPEC.md`. **Every number carries its source artifact path.** No number without one |
| Live demo | `docs/DEMO_SCENARIO.md`, offline, from a clean checkout |
| Repository | Public-ready: README, specs, tests, reports; no secrets, no real data |
| `reports/` | `METRICS_<tag>.json`, `ABLATION_<tag>.md`, `COVERAGE_<tag>.md`, `DATASET_PROFILE.md`, `SENSITIVITY.md`, `PERFORMANCE.md`, `RED_TEAM_<tag>.md` |
| `FINAL_STATUS.md` | What is `Verified`, what is `Implemented`, what is `Specified` only, and every known limitation with a measured number |
| Recording | Backup for the demo, and evidence if the venue's machine fails |

## 6. What we will not do to score better

Stated here so that under deadline pressure the decision is already made:

- Not report a metric we did not measure, or a metric measured on the training or calibration split.
- Not re-score the test split after seeing a disappointing result and report the second number (AG-5).
- Not remove the decoy strata (`S3`–`S5`) to lift LER — they are the false-positive pressure and their
  removal would be a rigged benchmark.
- Not delete the `intermittent` class because we handle it poorly. We publish the number.
- Not present synthetic data as operational data, in any wording, on any slide (INV-3).
- Not hide the false-positive rate behind the recall figure.
- Not weaken a test to reach a green build (INV-6).
- Not claim a capability that is `Specified` or `Implemented` as though it were `Verified` (INV-9, and the
  vocabulary in `CLAUDE.md § 4` exists precisely to make this hard to do by accident).

A submission that reports a modest LER with a credible protocol, published baselines, named limitations
and a live re-derivation audit beats one reporting 0.99 that nobody can check. Under expert judging it is
not close.
