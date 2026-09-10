# ML_METHOD_RESEARCH.md — Method Selection & Justification

**Owner:** Data + ML Engineer agent (with Research Scientist)
**Purpose:** Choose methods on evidence, and record *why the fancier option was rejected*.

## Selection principles (in priority order)

1. **Bounded false negatives beat higher average accuracy.** A method that gives a guarantee we
   can state and test wins over one that gives a better mean score we cannot bound.
2. **Explainable to a QA inspector.** If a method's output cannot be re-derived on paper by a
   reliability engineer, it may only ever be a *cross-check*, never a primary verdict.
3. **Standards-anchored where a standard exists.** Prior art (D-CD-01) is a feature.
4. **Small-`n` honest.** A lot may hold 30–500 parts, not 10⁶. Methods needing large `n` are out.
5. **Deterministic and cheap.** A screening decision must be reproducible byte-for-byte and must
   compute in milliseconds on a test-floor workstation. No GPU. No wall-clock dependence.
6. **Simplicity is a safety property.** Every added parameter is another thing that can be
   mis-tuned by a hurried operator at 2 a.m.

---

## 1. Module A — dynamic (lot-relative) outlier detection

### 1.1 Candidate evaluation

Scores: ✅ good · ⚠️ conditional · ❌ disqualifying.

| Method | Explain­ability | Small-`n` | Skew-robust | Multivariate | Determin­istic | Verdict |
|---|---|---|---|---|---|---|
| **DPAT** `median ± 6·IQR/1.35` | ✅ paper-checkable, standard | ⚠️ needs `n ≥ 20` guard | ⚠️ symmetric limits | ❌ per-parameter | ✅ | **PRIMARY** |
| Classical z-score `mean ± kσ` | ✅ | ⚠️ | ❌ mean/σ break down | ❌ | ✅ | **REJECTED** — outliers corrupt the very statistics used to detect them (masking). Kept only as a *negative baseline* to demonstrate the failure. |
| **Robust MAD-z** `0.6745(x−med)/MAD` | ✅ | ✅ best at small `n` | ⚠️ symmetric | ❌ | ✅ | **ENSEMBLE** — primary when `n < 20` |
| Tukey fences `k·IQR` | ✅ | ✅ | ⚠️ | ❌ | ✅ | **ENSEMBLE** (severity banding: 1.5 mild / 3.0 extreme) |
| **Adjusted boxplot** (medcouple) | ⚠️ needs explaining | ⚠️ | ✅ built for skew | ❌ | ✅ | **ENSEMBLE** — IDDQ is strongly right-skewed |
| **Robust Mahalanobis (MCD)** | ⚠️ with a contribution decomposition, yes | ⚠️ needs `n > p` comfortably | ⚠️ elliptical assumption | ✅ | ✅ | **ENSEMBLE** — the only member that sees *joint* anomalies |
| Isolation Forest | ❌ score has no physical meaning | ⚠️ | ✅ | ✅ | ⚠️ seedable | **CROSS-CHECK ONLY** — never the primary verdict |
| Local Outlier Factor | ❌ | ❌ needs dense neighbourhoods | ✅ | ✅ | ✅ | **REJECTED** — `k`-sensitivity + weak explanation for lot sizes we expect |
| One-Class SVM | ❌ | ❌ kernel/ν tuning on tiny data | ⚠️ | ✅ | ⚠️ | **REJECTED** — tuning burden, no interpretability, no guarantee |
| Autoencoder / deep AE | ❌ black box | ❌ hopeless at `n≈100` | — | ✅ | ❌ | **REJECTED** — would be a red-team gift |
| LSTM / Transformer on the series | ❌ | ❌ 4 time points | — | ✅ | ❌ | **REJECTED** — 4 read points is not a sequence-modelling problem. Using one would be a *negative* signal to expert judges. |

### 1.2 Decision

**A DPAT-anchored, five-member robust ensemble with an Isolation-Forest cross-check.**

Aggregation is a **max-severity rule with unanimity reporting**, not an averaged score:
because false negatives dominate, *any* member firing raises severity, and the UI shows which
members fired and which did not. Averaging would let four quiet members bury one loud one — the
exact failure mode the problem statement calls catastrophic.

### 1.3 Why not simply "train a classifier on labelled defects"

Three reasons, all worth saying aloud to judges: (1) real latent-defect labels are extremely rare
and arrive years later via field returns — a supervised screen cannot be trained in practice;
(2) a supervised model trained on *our own synthetic labels* would be circular, and we would be
measuring our generator rather than our detector; (3) unsupervised lot-relative screening
generalises to a lot whose defect mode has never been seen. We therefore keep supervised learning
out of the *detector* and use labels **only for evaluation**, where they belong.

---

## 2. Module B — drift prediction from `Value_0h`, `Value_24h` → `Value_168h`

### 2.1 The binding constraint nobody else will notice

Two input observations give **two degrees of freedom per part**. Therefore:

- You **can** identify a per-part intercept and one per-part amplitude.
- You **cannot** identify a per-part curvature, time-constant, or exponent. Any model that
  appears to do so is really borrowing its shape from *elsewhere* — and it should say where from.

This is the central honest insight of Module B, and it dictates the architecture. A team that
fits `a·t² + b·t + c` per part from two points is fitting noise and will not survive one sharp
question.

### 2.2 Candidate evaluation

| Approach | Identifiable from 2 pts? | Bias | Explain­ability | Verdict |
|---|---|---|---|---|
| Naïve linear extrapolation to 168 h | ✅ | **over-predicts** (real drift is sub-linear, D-B-03) | ✅ trivial | **BASELINE** — must be reported, not used as the answer |
| Per-part polynomial (deg ≥ 2) | ❌ under-determined | unstable | ⚠️ | **REJECTED** — statistically invalid here |
| Per-part exponential / saturating fit | ❌ 3 free params | unstable | ⚠️ | **REJECTED** at 2 points; revisit only if a 3rd early read (e.g. 8 h) is available |
| **Shape–Amplitude decomposition** (population shape × per-part amplitude) | ✅ | low, and *measurable* | ✅ shape is a plotted, inspectable curve | **PRIMARY** |
| Ridge / robust linear regression on engineered features | ✅ | low | ✅ signed coefficients | **PRIMARY ensemble member** |
| Gradient-boosted trees (e.g. `HistGradientBoosting`) | ✅ | low | ⚠️ needs attribution | **ENSEMBLE member** — captures interactions; gated on beating the linear model out-of-sample |
| Quantile regression (α-quantile of 168 h) | ✅ | — | ✅ | **ADOPTED** as the conformal base for a sharper, adaptive bound (CQR) |
| ARIMA / state-space / Prophet | ❌ | — | ⚠️ | **REJECTED** — 4 read points, and 2 of them are unavailable at decision time |
| RNN/LSTM/Transformer | ❌ | — | ❌ | **REJECTED** — see § 1.1 |
| Gaussian Process | ✅ | low | ⚠️ | **REJECTED** for the primary path: cost and hyperparameter fragility for a benefit (uncertainty) that conformal delivers with a *stronger* guarantee |

### 2.3 Decision — the Shape–Amplitude model

Partially-pooled ("hierarchical-lite") formulation. For part `i` at elapsed time `t`:

```
value_i(t) = baseline_i + amplitude_i · Φ_g(t) + ε
```

- `Φ_g(t)` — the **normalised population degradation shape** for group `g`
  (`component_type × parameter`), learned from *training lots only*, normalised so `Φ_g(24) = 1`.
  Candidate parametric families, selected by out-of-sample score and reported openly:
  `Φ(t) = (t/24)^n` (power law, NBTI-like), `Φ(t) = log(1+t/τ)/log(1+24/τ)` (log-time),
  `Φ(t) = (1−e^(−t/τ))/(1−e^(−24/τ))` (saturating).
- `baseline_i = Value_0h`; `amplitude_i = Value_24h − Value_0h` — both from *permitted* inputs only.
- Prediction: `V̂₁₆₈ = Value_0h + (Value_24h − Value_0h) · Φ_g(168)`.

Why this is the right answer: it is **identifiable** from two points; the *only* thing borrowed
across parts is the shape, which is exactly the thing physics says is shared; it degrades
gracefully to the linear baseline when `Φ_g(168) = 7`; and `Φ_g` is a single curve an engineer can
look at and challenge. A residual model (ridge or GBT) then corrects it using lot context, and the
whole stack is wrapped in conformal calibration.

### 2.4 Uncertainty — the flagship

Rejection uses a **one-sided upper conformal bound**, not the point estimate (D-H-02):

```
Û₁₆₈(1−α) = V̂₁₆₈ + q̂(1−α)          # split conformal, one-sided
q̂(1−α) = the ⌈(n_cal+1)(1−α)⌉-th smallest signed residual (y − ŷ) on calibration data
```

with **Conformalised Quantile Regression** as the sharper variant (`q̂` applied to the
quantile-regression residual, giving heteroscedastic-adaptive widths), and **Mondrian
conditioning** on `component_type` so that no group's coverage collapses behind good marginal
coverage. `Û` is what the safety comparison uses. This is the single most defensible thing in the
project: the guarantee is *stated*, *cited*, and *empirically falsifiable* by `TEST-CP-001`.

---

## 3. Leakage prevention — the risks specific to this problem

| ID | Leakage risk | Why it is tempting | Control |
|----|--------------|--------------------|---------|
| LK-1 | Using 96 h or 168 h values (or anything derived from them) as Module B features | They are sitting in the same dataframe | **Feature allow-list** enforced in code: Module B may read only columns tagged `available_at_h ≤ 24`. Test `TEST-DL-001` asserts the model's fitted input schema contains nothing else. |
| LK-2 | Fitting the population shape `Φ_g` on lots that appear in the test set | Shapes look "better" with more data | Split **by lot** first, then anything else. `Φ_g` is fitted on training lots only. `TEST-DL-002`. |
| LK-3 | Calibrating conformal quantiles on data later used for reported coverage | Calibration set is convenient | Three disjoint splits: `train / calib / test`, lot-disjoint. `TEST-DL-003`. |
| LK-4 | Fitting the variance-stabilising transform or scaler on the full dataset | `sklearn` makes it a one-liner | Transform parameters fitted inside the training fold; wrapped in a `Pipeline`. `TEST-DL-004`. |
| LK-5 | Computing DPAT limits for a lot from a pool that includes the part being judged | It is the same lot, so it feels correct | **Leave-one-out limits**: the part under test is excluded from its own median/IQR. Materially changes the answer for tiny lots. `TEST-DL-005`. |
| LK-6 | Threshold selection tuned on the test set | Everyone does it | `α`, `k`, and every threshold are chosen on `calib`. The test set is scored **once per release**, by the Integration agent, with the result committed. `TEST-DL-006`. |
| LK-7 | Generator parameters leaking into the model as priors | We wrote both | Model code may not import the generator module. Enforced by an import-graph test, `TEST-DL-007`. |
| LK-8 | Ground-truth labels reachable at inference | Same table | The inference DTO physically excludes label columns; the API schema has no field for them. `TEST-DL-008`. |

**LK-5 and LK-7 are the ones a strong red team will actually try.** They are both closed by design,
not by discipline.

## 4. Validation strategy

- **Primary split: lot-disjoint (`GroupKFold` on `lot_id`).** A part must never be scored by a
  model that has seen its lot-mates, because lot-level correlation is the dominant structure here.
  Random row splits would inflate every metric and are forbidden.
- **Secondary: temporal (forward-chaining) split.** Lots are ordered by `lot_start_date`; train on
  earlier lots, test on later ones. This is the honest simulation of deployment and it exposes
  drift-of-the-process.
- **Stratification** by `degradation_mode` and by Escape-Set membership, so rare classes appear in
  every fold and per-class metrics are computable.
- **Nested selection.** Hyperparameters chosen inside the training folds only.
- **Repeated evaluation** across `N_seeds` generator seeds; report **mean ± std**, never a single
  favourable run. A metric quoted without a spread is treated as a defect (`RT-011`).
- **Ablations are mandatory deliverables**, because they are the evidence that each component earns
  its place: DPAT-only · +ensemble · +Zonal · linear-baseline drift · +Shape–Amplitude ·
  +residual model · +conformal · full system.

## 5. Explainability method selection

| Need | Method | Why |
|------|--------|-----|
| Why flagged (univariate) | Robust σ distance + percentile rank + the actual limit arithmetic | Directly checkable by hand |
| Why flagged (multivariate) | Mahalanobis **per-parameter contribution decomposition** | Exact, additive, no sampling — unlike KernelSHAP |
| Which feature drove the forecast | Signed coefficient × standardised value for the linear part; exact **TreeSHAP** for the GBT residual | TreeSHAP is exact and fast for trees; no approximation to defend |
| What would have changed the verdict | **Counterfactual threshold**: invert the decision rule for the one input the inspector can act on | Actionable, and it is arithmetic, not attribution |
| How confident | Conformal interval width + coverage report + exchangeability-guard state | An honest, testable confidence statement |

**Rejected:** LIME (unstable, sampling-based — two runs give two explanations, which is
indefensible in an audit) and KernelSHAP on the whole pipeline (approximate and slow when an exact
decomposition exists). Chosen methods are all **deterministic**: the same part always yields the
same explanation, byte-for-byte. `TEST-XAI-003` asserts it.

## 6. Cost/latency budget (targets, to be measured)

| Operation | Target |
|-----------|--------|
| DPAT limits for a 500-part lot | < 10 ms |
| Full Module A ensemble, 500 parts × 6 parameters | < 300 ms |
| Module B inference + conformal bound, 500 parts | < 150 ms |
| Explanation payload for one part | < 20 ms |
| Cold model load | < 2 s |

All are **targets**, not measured results, until `reports/PERFORMANCE.md` exists.


