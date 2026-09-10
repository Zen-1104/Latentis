# EVALUATION_RESEARCH.md — Metrics, Protocol & Anti-Gaming

**Owner:** Data + ML Engineer + Red Team Auditor
**Purpose:** Define how LATENTIS proves it works, in a way that cannot be gamed and that maps
directly onto the three SIH judging criteria.

## 1. Mapping SIH criteria to measurable quantities

| SIH criterion | Primary metric | Guard against gaming |
|---|---|---|
| **Anomaly Detection Score** — "a false negative is catastrophic" | **Latent Escape Recall (LER)** — recall restricted to strata `S1`+`S2` (defects that pass absolute limits), at a **capped false-positive budget** | Recall alone is trivially gamed by flagging everything. LER is *only ever* reported jointly with FPR and with the flag-rate; a submission that flags 100 % scores LER = 1.0 and is immediately disqualified by the FPR cap. |
| **Drift Prediction Accuracy** — MAE vs. hidden 168 h truth | **MAE / RMSE on held-out lots**, plus **conformal coverage** and **mean interval width** | MAE alone rewards a model that predicts the mean and is useless for rejection. Coverage + width force honest uncertainty: you cannot fake a coverage guarantee. |
| **Explainability** | **Re-derivation rate**: fraction of displayed numbers an automated auditor can recompute from the payload's provenance to within float tolerance. **Target: 100 %.** | Novel, and it is a *machine-checkable* explainability metric rather than a subjective claim. `RT-007` is the auditor. |

**LER is the headline number of this project.** It is the metric that corresponds to what ISRO
actually fears: a defective part that the existing screen passes.

## 2. Anomaly metrics — full set

Because the detector is unsupervised and the labels are used only for evaluation:

- **Threshold-free:** AUROC, **AUPRC** (primary — prevalence is 1–5 %, so AUROC is optimistic and
  AUPRC is the informative curve), and **partial AUROC restricted to FPR ≤ 0.1** (the only operating
  region a test floor would tolerate).
- **At the operating point:** recall (= 1 − FNR), precision, F1, **F2** (weights recall 4× —
  the correct summary statistic when misses dominate), FNR, FPR, and **flag rate** (operational
  cost).
- **Stratified:** every metric reported per stratum `S0..S5` and per `degradation_mode`. A single
  aggregate number hides exactly the failure we care about.
- **Escape-conditional:** `P(flagged | defective AND passes absolute limits)` — the literal
  quantification of the problem statement.
- **Baseline deltas, mandatory:** `LER(static limits only)` — which is **0 by construction on S1/S2**,
  the cleanest possible demonstration — and `LER(DPAT only)`, `LER(full system)`. Improvement over
  DPAT is the real scientific claim; improvement over static limits is the *product* claim.

### 2.1 Prevalence honesty

AUPRC depends on prevalence, so **every AUPRC is reported with the prevalence of the evaluated
set**, and the no-skill baseline (= prevalence) is drawn on every PR curve. Omitting this is the
most common way ML results mislead. `RT-012` checks for it.

## 3. Drift metrics — full set

| Metric | Why |
|---|---|
| MAE, RMSE (per parameter, in physical units) | The stated SIH metric. Reported in µA/ns, never normalised-only. |
| MedAE | Robust to the few extreme drifters that would dominate MAE |
| **MAPE / sMAPE with care** | Reported only where the denominator is bounded away from zero; otherwise explicitly omitted with a reason |
| R² | Reported, but flagged as *low-information here* — a strong R² can coexist with catastrophic tail behaviour, and the tail is the whole point |
| **Empirical coverage of `Û(1−α)`** | Must land inside the binomial confidence band for the nominal level. The falsifiable test of our central claim. |
| **Mean / median interval width** | Sharpness. A trivially wide interval achieves coverage and is useless; width is the honesty check on coverage. |
| **Winkler / interval score** | Single proper scoring rule combining coverage and width — cite it so we cannot be accused of choosing whichever of the two flatters us |
| **Per-group coverage** (Mondrian) | Guards the documented split-conformal failure mode (D-H-02) |
| **Calibration curve of the point model** | Reveals systematic over/under-prediction; the naïve-linear baseline should visibly over-predict, confirming D-B-03 |
| **Tail MAE** — MAE restricted to the top decile of true drift | Where escapes live. Average MAE is nearly irrelevant to the mission. |

## 4. Operational metrics

Latency (p50/p95/p99 per endpoint), throughput (parts/s), **robustness to missing values**
(measured by ablating 1 %/5 %/10 % of read-points and reporting metric degradation, not by
asserting it works), **robustness to measurement noise** (inject calibrated noise at
1×/2×/5× nominal and plot degradation), cold-start time, memory ceiling, and **behaviour on
malformed input** (must be a typed 4xx, never a 500 or a silent default).

## 5. Protocol

1. Generate `N_seeds = 5` independent dataset instances from distinct seeds.
2. For each: lot-disjoint `GroupKFold` (k = 5) for model selection; a **held-out lot block** never
   touched during development is the reported test set.
3. All thresholds, `α`, and `k` fixed on `calib` **before** the test set is opened.
4. Test set scored **once per release tag**, by the Integration + Release agent, output committed
   to `reports/METRICS_<tag>.json` with the dataset manifest hash.
5. Report **mean ± std across seeds** for every number. A single-run number is not a result.
6. Any change to the model after the test set is opened invalidates the metric and requires a new
   seed set. This is recorded in `DECISIONS.md` if it ever happens.

### 5.1 Why point 4 matters

A test set scored repeatedly during development *is* a validation set, and the reported number is
optimistically biased. Enforcing single-scoring by giving the privilege to a different agent is a
process control, not a promise. `RT-013` audits the git history for repeated test-set scoring.

## 6. Anti-gaming register — how a reviewer should try to break our numbers

| ID | Attack | Our pre-built defence |
|----|--------|----------------------|
| AG-1 | "Your recall is high because you flag everything." | FPR cap + flag rate reported beside every recall; NP-ROC curve shown |
| AG-2 | "Your MAE is low because most parts barely drift." | Tail MAE + per-stratum MAE + MAE on `S2` only |
| AG-3 | "Your test set leaked." | Lot-disjoint splits, import-graph test, three physical dataset files, `TEST-DL-*` |
| AG-4 | "You tuned on the test set." | Single-scoring protocol, different owner, committed artifacts, git audit `RT-013` |
| AG-5 | "Your synthetic data was tuned to be easy." | Difficulty strata, `S3`–`S5` decoys, parameter provenance tags, generator authored against a frozen spec before the model existed |
| AG-6 | "Your explanations are templated prose." | Machine-checked re-derivation rate; `RT-007` recomputes every number from the payload |
| AG-7 | "Your conformal guarantee is vacuous." | Measured coverage + width + Winkler score + per-group coverage; exchangeability guard declares its own invalidity |
| AG-8 | "Your improvement is within noise." | mean ± std over 5 seeds; paired comparison on identical splits; report the paired difference and its spread |
| AG-9 | "The UI number and the model number differ." | Provenance ledger; `RT-005` diffs API payload against rendered DOM text |
| AG-10 | "Remove the ML and the results are the same." | Mandatory ablation table — if an ablation shows a component adds nothing, we **delete the component**, not the ablation |

**AG-10 is a commitment, not a slogan.** Any component that does not earn its place in the
ablation table is removed before release. That is the difference between an engineered system and
a feature pile.

## 7. Reporting artifacts (all machine-generated)

`reports/METRICS_<tag>.json` · `reports/ABLATION_<tag>.md` · `reports/COVERAGE_<tag>.md` ·
`reports/DATASET_PROFILE.md` · `reports/PERFORMANCE.md` · `reports/RED_TEAM_<tag>.md`.

No number appears in a slide unless it appears in one of these files first.
