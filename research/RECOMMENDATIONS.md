# RECOMMENDATIONS.md — Consolidated Research Conclusions

**Owner:** Research Scientist → handed to Lead Orchestrator
**Status:** Approved as the basis for `PROJECT_MASTER_SPEC.md`.

This document converts `DOMAIN_RESEARCH.md`, `ML_METHOD_RESEARCH.md`, `DATASET_RESEARCH.md` and
`EVALUATION_RESEARCH.md` into binding recommendations. Each is traceable to a finding ID and each
is either **ADOPT** (build it), **DEFER** (post-hackathon), or **REJECT** (with reason).

---

## R1 — ADOPT: Frame the whole project as closing a gap in MIL-STD-883 Method 1015

Burn-in's stated purpose *is* removing latent, time-and-stress-dependent defects (D-A-01), yet it
is conventionally adjudicated with absolute limits. LATENTIS implements the mechanism the purpose
implies. **Effect:** the project stops sounding like an ML demo and starts sounding like process
engineering. Use this framing in slide 1, in the README, and in the first sentence of any answer
to "why does this matter?".

## R2 — ADOPT: Module A baseline is AEC-Q001 Dynamic Part Average Testing, implemented to formula

`limits = median ± 6 × (IQR / 1.35)`, computed per `(lot, component_type, parameter, read_point)`,
**leave-one-out**, with a documented `n < 20` fallback to `1.4826 × MAD` (D-CD-02, LK-5, RQ-03).
Every advanced method must beat DPAT in the ablation table or be deleted (AG-10).
**Effect:** instant credibility with reliability engineers; a defensible floor under every claim.

## R3 — ADOPT: Ensemble = DPAT + MAD-z + Tukey bands + adjusted boxplot + robust Mahalanobis (MCD),
with Isolation Forest as a labelled **cross-check only**. Aggregate by **max severity with
unanimity reporting**, never by averaging (D-CD-03, § 1.2 of ML research).
**REJECT:** LOF, One-Class SVM, autoencoders, LSTM/Transformer — all fail on `n`, explainability,
or both, and using a sequence model on four read-points would signal inexperience to expert judges.

## R4 — ADOPT: Zonal DPAT + part/socket/zone attribution

Compute limits per thermal zone where counts allow, and run a Good-Part-in-Bad-Socket check so the
system can say *"this is probably a tester artefact — retest before disposition"* (D-CD-04, D-I-03).
Label it clearly as **our extension** of wafer-space GDBN into oven space, not a cited standard.
**Effect:** the single most "we've actually thought about the test floor" feature in the project.

## R5 — ADOPT: Module B = Shape–Amplitude decomposition, not per-part curve fitting

Two input points identify a baseline and an amplitude, and nothing more. Learn the **population
shape** `Φ_g(t)` on training lots; extrapolate the **per-part amplitude**:
`V̂₁₆₈ = V₀ + (V₂₄ − V₀) · Φ_g(168)`. Add a ridge/GBT residual correction on lot-context features.
Report naïve linear extrapolation as a measured baseline (D-B-03, § 2 of ML research).
**Effect:** survives the sharpest possible question — "how do you fit a curve to two points?" —
because the answer is "we don't, and here is exactly what we do instead."

## R6 — ADOPT: Reject on a one-sided conformal upper bound, not on a point forecast

`Û₁₆₈(1−α)` via split conformal / CQR, **Mondrian-conditioned on `component_type`**, with
measured coverage, interval width, Winkler score, and per-group coverage all reported (D-H-02).
Ship an **exchangeability guard** that voids the guarantee and degrades conservatively when the
incoming lot is incompatible with the calibration distribution.
**Effect:** the FN-sensitivity requirement is met by construction and the claim is falsifiable.
This is the project's strongest technical differentiator.

## R7 — ADOPT: Neyman–Pearson threshold selection, exposed as "Mission Risk Posture"

Choose the operating threshold by an order-statistic rule on `calib` so FNR ≤ α with high
probability; plot the NP-ROC so the false-positive cost of each posture is visible (D-H-01).
**Effect:** replaces "we tuned the threshold until recall looked good" with a stated bound.

## R8 — ADOPT: Explainability is a Provenance Ledger, and it is machine-audited

Every displayed quantity carries `{inputs, formula_id, parameters, model_version, dataset_hash}`
and the UI re-derives it on demand. The **re-derivation rate** is a reported metric with a 100 %
target (D-I-01, § 1 of evaluation research). Explanations are **deterministic**.
**REJECT:** LIME (unstable across runs — indefensible in an audit) and pipeline-wide KernelSHAP
(approximate where an exact decomposition exists). Use exact Mahalanobis contributions and TreeSHAP.
**Effect:** converts "explainability" from a claim into a test, and pre-defeats the entire
"is this fabricated?" line of attack.

## R9 — ADOPT: Add counterfactual threshold explanations

For each flagged part, state the smallest change in an inspector-observable input that would flip
the verdict: *"this part would have passed if its 24 h leakage were ≤ 18.4 µA."* Pure arithmetic
(invert the decision rule); no surrogate model.
**Effect:** explanations become actionable, which is what an inspector actually needs.

## R10 — ADOPT: Emit a lot-level disposition tied to PDA, not only part verdicts

If the flagged fraction exceeds the configured PDA (5 % default, per D-A-03), escalate the lot.
**Effect:** matches the real Method 5004 workflow; almost no competing submission will do this.

## R11 — ADOPT: Three physically separate dataset artifacts

`dataset_screening` (0 h, 24 h + metadata — all the system may see), `dataset_truth` (96 h, 168 h,
labels — evaluator only), `dataset_full` (generator tests only). Structural, not procedural,
leakage prevention (LK-1, § 2 of dataset research).

## R12 — ADOPT: Difficulty strata `S0..S5` with per-stratum reporting

`S1` (escape-anomaly) and `S2` (escape-drift) are the flagship targets; `S3`–`S5` are decoys that
must **not** be rejected. `S5` (lot shift) is the case most teams will fail loudly.
**Effect:** makes the flagship claim measurable and proves we did not build an easy dataset.

## R13 — ADOPT: Every generator parameter carries a provenance tag

`cited` / `derived` / `assumed` + rationale; the generator refuses to run if any tag is missing.
**Effect:** an unusual, high-trust feature that directly answers "did you tune the data?"

## R14 — ADOPT: Latent Escape Recall as the headline metric, always beside FPR and flag rate

Static screening scores **LER = 0 on S1/S2 by construction** — the cleanest possible demonstration
of the problem. Report LER for static / DPAT-only / full system, mean ± std over 5 seeds.

## R15 — ADOPT: Lot-disjoint splits primary, temporal splits secondary, single-scored test set

Owned by a different agent than the model author (§ 5 of evaluation research). Random row splits
are **forbidden**.

## R16 — ADOPT: Mandatory ablation table with a deletion commitment

Any component that does not improve the metric it exists to improve is **removed** before release
(AG-10). Written into the quality gates.

## R17 — DEFER (post-hackathon, documented in Future Scope)

Bayesian hierarchical drift model with full posterior per part; survival/time-to-failure modelling
and Weibull β estimation for early-life failure rate; online/incremental DPAT limit updating during
a running burn-in; MES/tester-integration adapters (STDF ingest); active learning on inspector
overrides; multi-parameter joint conformal (region rather than per-parameter bounds); federated
learning across fabrication sites.
Each is listed with *why it is not in scope now*, which is a stronger answer than pretending it is.

## R18 — REJECT: A "single AI risk score" as the primary UI object

A scalar with no decomposition is exactly what the problem statement warns against. Risk is
displayed as a **decomposed, additively-attributed** figure whose components are all independently
checkable (`models/RISK_SCORING_SPEC.md`), and the *verdict* is driven by the two engine rules —
the score orders the inspector's work queue; it does not make the decision.

---

## Recommended build order

Dataset generator → Module A (DPAT first, then ensemble) → evaluation harness → Module B
(Shape–Amplitude, then residual, then conformal) → risk + explanation layer → API → frontend →
Playwright → red team → ablations → presentation. **Evaluation harness before the second model** is
deliberate: without it, every subsequent choice is guesswork.

## Non-negotiables handed to the Lead Orchestrator

1. DPAT is the baseline and it is measured, not assumed.
2. Rejection uses the conformal **bound**, never the point estimate.
3. Nothing is displayed that cannot be re-derived from its provenance payload.
4. Every metric ships with its spread, its baseline, and its prevalence.
5. Components that fail their ablation are deleted.
