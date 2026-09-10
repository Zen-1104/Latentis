# DOMAIN_RESEARCH.md — Burn-In, Screening & High-Reliability QA

**Owner:** Research Scientist agent · **Status:** Baseline complete, extendable
**Purpose:** Establish the factual and normative ground on which LATENTIS is built, so that
every engineering choice downstream can be traced to either a cited standard/paper or an
explicitly labelled assumption.

## How to read this document

Each entry uses a fixed schema:

- **Finding** — the claim.
- **Source** — where it came from.
- **Relevance** — why it matters to burn-in screening.
- **Implication for SIH26170** — the concrete design consequence.
- **Confidence** — `HIGH` (primary/normative source or directly quoted), `MEDIUM` (secondary
  source, consistent with multiple references), `LOW` (plausible, unverified — treat as
  assumption), `ASSUMPTION` (our engineering choice, not a fact).

> **Standing caveat.** Controlled documents (MIL-STD-883, MIL-PRF-38535, AEC-Q001,
> ECSS-Q-ST-60-05) were consulted through publicly reachable summaries and mirrors, not through
> paid/controlled distribution. Anything marked `MEDIUM` must be re-verified against the
> controlled document before it appears in the final presentation as a normative claim.
> See `HUMAN-002` in `HUMAN_ACTIONS.md`.

---

## A. Environmental Stress Screening / Burn-In

### D-A-01 — Burn-in exists specifically to remove latent, time-and-stress-dependent defects

- **Finding:** MIL-STD-883 Method 1015 (Burn-In) is performed "for the purpose of screening or
  eliminating marginal devices, those with inherent defects or defects resulting from
  manufacturing aberrations" that "cause time and stress dependent failures".
- **Source:** [US FDA — Screening Electronic Components (inspection guide), citing MIL-STD-883 Method 1015](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/inspection-guides/screening-electronic-components); [Tekmos — MIL-STD-883 Standard summary](https://tekmos.com/support/mil-std-883-standard); primary: [MIL-STD-883 (DLA Land & Maritime)](https://landandmaritimeapps.dla.mil/Downloads/MilSpec/Docs/MIL-STD-883/std883.pdf).
- **Relevance:** The stated *purpose* of the process is latent-defect removal. A screen that
  only applies absolute limits therefore under-delivers against its own charter.
- **Implication:** LATENTIS is not inventing a new goal; it is closing the gap between the
  stated purpose of Method 1015 and the pass/fail mechanism conventionally used to implement it.
  This framing should open the SIH presentation — it is the strongest possible justification.
- **Confidence:** HIGH.

### D-A-02 — Canonical burn-in condition: 125 °C minimum, ~160 h, within a 48–168 h band

- **Finding:** The Method 5004 screening flow lists "Burn-In Method 1015 160 Hrs. 125 °C Min".
  Burn-in is described as exercising the part at an extreme of operating condition "typically
  over a time period of 48–168 hours".
- **Source:** [Tekmos — MIL-STD-883 Standard summary](https://tekmos.com/support/mil-std-883-standard).
- **Relevance:** Validates the problem statement's `0 h / 24 h / 96 h / 168 h` sampling grid and
  its 125 °C figure as realistic rather than arbitrary.
- **Implication:** The synthetic generator uses **125 °C nominal stress temperature** and the
  **0/24/96/168 h** read-point grid as its primary configuration, with 160 h available as an
  alternate profile. The 168 h endpoint is the upper edge of the cited industry band, so it is
  defensible as a "full-duration" screen.
- **Confidence:** MEDIUM (secondary source; duration and temperature vary by device class and
  by Source Control Drawing).
### D-A-03 — Interim electrical measurements and PDA are already part of the standard flow

- **Finding:** "Interim Electrical Testing is performed when specified, to remove defective
  devices prior to further testing", or "to provide a basis for application of percent defective
  allowable (PDA) criteria when a PDA is specified". The Method 5004 example sets PDA at **5 %**,
  based on Group A Subgroup 1 tests after cooldown as the final electrical test.
- **Source:** [Tekmos — MIL-STD-883 Standard summary](https://tekmos.com/support/mil-std-883-standard); PDA of 5 % corroborated by [NASA KSC Preferred Practice 1401](https://extapps.ksc.nasa.gov/Reliability/Documents/Preferred_Practices/1401.pdf) ("Typical PDA criterion is 5%").
- **Relevance:** Two things follow. (1) Multi-read-point burn-in data *already exists* in
  qualified flows — LATENTIS consumes an artifact the process already produces, so adoption cost
  is near-zero. (2) There is an existing **lot-level** disposition rule, not only a part-level one.
- **Implication:** LATENTIS emits **both** a part verdict and a **lot disposition**. If the
  flagged fraction of a lot exceeds the configured PDA, the lot itself is escalated. This is a
  differentiating feature: most anomaly-detection projects stop at the part.
- **Confidence:** MEDIUM for the exact 5 % figure being applicable to a given ISRO SCD; HIGH for
  "a PDA mechanism exists and is lot-level".

### D-A-04 — "Delta limits" — drift between pre- and post-burn-in reads — are a normative concept

- **Finding:** Military drawings and MIL-PRF-38535 revision histories reference dedicated tables
  of **delta limits** for burn-in and operating life test — e.g. "Burn-in and operating life test
  delta limits parameters on table IIB", "Add TABLE IIB for delta limits", "Add delta limits,
  table III".
- **Source:** [DLA SMD 97626](https://landandmaritimeapps.dla.mil/Downloads/MilSpec/Smd/97626.pdf); [MIL-PRF-38535 (NASA NEPP mirror)](https://nepp.nasa.gov/DocUploads/668C05F1-46E9-415A-8360C8B9F66A4344/MIL-PRF-38535.pdf); [TI — Upscreening of Class B Microcircuits for Space Applications](https://www.ti.com/pdfs/hirel/mltry/btospace.pdf).
- **Relevance:** This is the single most important normative finding for **Module B**. The
  industry *already accepts* that change-over-time (Δ) is a legitimate rejection criterion
  independent of absolute limits. Our contribution is to make the Δ criterion **predictive**
  (forecast the 168 h Δ from the 0→24 h Δ) rather than retrospective.
- **Implication:** Module B is positioned as **"predictive delta-limit screening"**. This is
  precise, standards-anchored language that a reliability engineer will immediately recognise,
  and it pre-empts the objection "you invented a new rejection rule".
- **Confidence:** HIGH that delta limits are normative; MEDIUM on their specific numeric values
  (device- and drawing-specific — LATENTIS therefore treats them as **configuration**, never as
  a built-in constant).

### D-A-05 — European/ESA space practice defines EEE component screening equivalently

- **Finding:** ECSS-Q-ST-60C (and its -05 sub-standard family) governs selection, control,
  procurement and use of EEE components in space projects, with screening and lot validation
  requirements analogous to the US QML system.
- **Source:** [ECSS-Q-ST-60C Rev.4](https://ecss.nl/wp-content/uploads/2024/11/ECSS-Q-ST-60C-Rev.4-DIR1(5November2024).pdf); [ECSS-Q-ST-60C Rev.3](https://ecss.nl/wp-content/uploads/2022/05/ECSS-Q-ST-60C-Rev.3(12May2022).pdf); [ECSS Q60 training material](https://ecss.nl/wp-content/uploads/2021/10/ECSS-Q60-2021-part-2.pdf).
- **Relevance:** Demonstrates the approach is not US-standard-specific; the concept of
  lot-relative acceptance and screening generalises.
- **Implication:** The `ScreeningProfile` configuration object is standard-agnostic: a profile
  names the read-point grid, stress condition, absolute limits, delta limits and PDA. Shipping
  profiles for both a MIL-STD-883-like and an ECSS-like flow costs nothing and shows breadth.
- **Confidence:** MEDIUM (standard existence and scope: HIGH; the specific screening clauses were
  not read in full).

---

## B. Electronic component degradation and drift behaviour

### D-B-01 — Thermal acceleration follows Arrhenius; AF = exp[(Ea/k)(1/T_use − 1/T_stress)]

- **Finding:** The acceleration factor for a thermally activated failure mechanism is
  `AF = exp( (Ea / k_B) · (1/T_use − 1/T_stress) )` with temperatures in Kelvin,
  `k_B = 8.617333262 × 10⁻⁵ eV/K`. Typical activation energies for electronics are quoted as
  **0.3–0.7 eV**, with 0.7 eV a common default; chemical-degradation mechanisms run 0.7–1.0 eV.
  Worked example: `Ea = 0.7 eV`, `T_stress = 150 °C`, `T_use = 90 °C` ⇒ `AF ≈ 23.85`.
- **Source:** [MetricGate — Arrhenius life-stress acceleration](https://metricgate.com/docs/arrhenius-life-stress-acceleration/); [ReliaSoft HotWire 144](https://help.reliasoft.com/articles/content/hotwire/issue144/hottopics144.htm); [Renesas AN1104](https://www.renesas.com/en/document/apn/an1104-elantec-reliability-reliability-and-electronic-engineer); [Analog Devices process reliability report](https://www.analog.com/media/en/technical-documentation/reliability-data/ds1819.pdf).
- **Relevance:** Gives a *physical* basis for (a) why 168 h at 125 °C is meaningful, and (b) how
  to inject temperature effects into the synthetic generator without hand-waving.
- **Implication:** Two concrete uses. (1) The generator modulates each part's degradation rate by
  the Arrhenius AF computed from its **actual recorded chamber/zone temperature**, so
  temperature-slot effects are physically consistent rather than random noise. (2) The UI can
  express margin in **equivalent field hours**, which is the unit a mission-assurance engineer
  actually thinks in. `Ea` is a per-`degradation_mode` configuration value, never a hidden constant.
- **Confidence:** HIGH for the formula; MEDIUM for any specific `Ea` value (mechanism- and
  technology-dependent — we therefore expose it and sweep it in sensitivity analysis).

### D-B-02 — Sub-limit parametric drift is the observable signature of latent defects

- **Finding:** Burn-in is credited with "detecting early failures" by exercising parts at
  operating extremes; the mechanisms it targets are by construction *time-and-stress dependent*
  (D-A-01), i.e. they express as a **trajectory**, not as a single out-of-limit reading.
- **Source:** Inference from D-A-01, D-A-04 (the existence of delta limits is itself evidence that
  industry observes and screens on drift), and D-B-01.
- **Relevance:** This is the logical core of the problem statement. If defects express as
  trajectories and the screen reads only the final absolute value, escapes are structural.
- **Implication:** The dataset generator's *defect model* is trajectory-first: a latent defect is
  defined by an anomalous **rate and curvature**, and its absolute values are then *deliberately
  kept inside* the absolute limit for a designated subset of parts (the **Escape Set**,
  `data/DATASET_SPEC.md § 7`). Those parts are the evaluation target.
- **Confidence:** MEDIUM as a synthesis; the individual premises are HIGH/MEDIUM.

### D-B-03 — Named degradation mechanisms give the simulator physically-motivated shapes

- **Finding:** Standard wear-out/latent mechanisms in silicon include time-dependent dielectric
  breakdown (TDDB), negative-bias temperature instability (NBTI), hot-carrier injection (HCI),
  electromigration, ionic contamination and package/interconnect effects. NBTI degradation is
  conventionally modelled with a power law in time (`Δ ∝ t^n`, small `n`) or a log-time form;
  electromigration/TDDB with Arrhenius-plus-stress-exponent models.
- **Source:** General reliability-physics literature; Arrhenius/stress-model framing from
  [MetricGate — combined temperature & voltage acceleration models](https://metricgate.com/docs/temperature-voltage-acceleration-models/) and [Renesas AN1104](https://www.renesas.com/en/document/apn/an1104-elantec-reliability-reliability-and-electronic-engineer).
- **Relevance:** Determines the *functional form* of drift, which determines what a 2-point
  forecaster can and cannot do.
- **Implication:** **Critical design consequence.** Because real degradation is typically
  **sub-linear in time** (power law with `n < 1`, or logarithmic), a naïve linear extrapolation
  from 0→24 h **systematically over-predicts** 168 h values. That over-prediction is *safe*
  (conservative, fewer escapes) but inflates false positives. LATENTIS therefore fits the
  **population shape** and extrapolates only the amplitude (see `models/drift/DRIFT_SPEC.md § 4`,
  Shape–Amplitude decomposition), and reports the naïve linear extrapolation as a **baseline** so
  the improvement is measurable.
- **Confidence:** MEDIUM on the specific exponents (technology-dependent); HIGH on
  "sub-linear, saturating behaviour dominates and linear extrapolation is biased high".

### D-B-04 — IDDQ / standby current is a recognised sensitive detector of parametric defects

- **Finding:** Outlier screening on parametric tests — with IDDQ prominent among them — is an
  established approach in automotive product lines for screening parametric defects; multiple
  outlier methods have been proposed in the test literature.
- **Source:** [Test-research paper on outlier screening (UCSB MTV group, ITC 2017)](http://mtv.ece.ucsb.edu/licwang/PDF/ITC2017.pdf).
- **Relevance:** Confirms the problem statement's choice of Iddq/leakage as the headline
  parameter, and confirms that **outlier screening on parametrics is prior art we should build on
  rather than re-derive**.
- **Implication:** IDDQ/leakage is the primary demo parameter. Because IDDQ distributions are
  strongly right-skewed and heteroscedastic, LATENTIS applies a documented variance-stabilising
  transform (log or Box–Cox, selected by a fitted, reported criterion) before Gaussian-style
  statistics, and prefers rank/robust methods that do not assume normality. See
  `models/anomaly/ANOMALY_SPEC.md § 3.2`.
- **Confidence:** HIGH.

---

## C. Statistical process control & D. Lot-relative anomaly detection

### D-CD-01 — Part Average Testing (PAT) is the industry-standard lot-relative screen

- **Finding:** PAT is "a method based on statistical analysis to identify and fail parts that have
  characteristics significantly outside the normal distribution of other parts in the same lot".
  PAT limits "are used to separate parts that are different than what is 'normally' being
  produced… they screen out the outliers". PAT is normatively defined by **AEC-Q001**.
- **Source:** [AEC-Q001 Rev D (AEC Council)](http://www.aecouncil.com/Documents/AEC_Q001_Rev_D.pdf); [NI TestStand Semiconductor Module — Part Average Testing](https://www.ni.com/docs/gd-GB/bundle/teststand-semiconductor-module/page/part-average-testing.html); [TriQuint/CS MANTECH — Real Time Dynamic Application of PAT at Final Test](https://csmantech.org/wp-content/acfrcwduploads/field_5e8cddf5ddd10/post_2557/048.pdf).
- **Relevance:** **This is the highest-value finding in the entire research pass.** The SIH problem
  statement's Module A — "if a lot averages 10 µA, a part at 45 µA is anomalous even though the
  datasheet max is 50 µA" — is a textbook description of PAT/DPAT.
- **Implication:** Module A's baseline **is** DPAT, implemented to the standard. Every advanced
  method must then be justified as an *improvement measured against DPAT*. This converts the
  project from "a team's clever idea" into "an implementation of aerospace-grade practice, plus a
  measured extension" — a decisive advantage in technical judging and in adversarial review.
- **Confidence:** HIGH.

### D-CD-02 — The exact PAT limit formula, with robust statistics

- **Finding:** Both static and dynamic PAT compute limits identically and differ only in the
  population used:
  - `PAT limits = Robust Mean ± 6 × Robust Sigma`
  - `Robust Mean = Q2` (the median)
  - `Robust Sigma = (Q3 − Q1) / 1.35` (Q1, Q3 = 25th/75th percentiles of ranked data)
  - Sigma multiplier = **6**
  - **SPAT** pools multiple batches from a fixed test list, refreshed "every six months or after
    eight wafer lots (whichever comes first)"; **DPAT** recomputes centre and spread from the
    material actually being tested, removing lot-to-lot variation from the limit.
  - Because pooled distributions are wider, SPAT limits tend to be looser than DPAT limits.
  - The 1.35 divisor is "inexact for sample sizes less than 20".
- **Source:** [yieldWerx — Ultimate Guide to Outlier Detection Using Part Average Testing](https://yieldwerx.com/blog/ultimate-guide-to-outlier-detection-using-part-average-testing/) (states AEC-Q001 Rev D as its basis); normative source [AEC-Q001 Rev D](http://www.aecouncil.com/Documents/AEC_Q001_Rev_D.pdf).
- **Relevance:** Gives Module A a precise, citable, reproducible baseline formula and — crucially
  — an explicit small-sample caveat.
- **Implication (four concrete design rules):**
  1. `RobustSigma = IQR / 1.35` and `k = 6` are the **defaults**, stored in configuration and
     displayed in the UI next to every DPAT verdict. `1.35` ≈ `2 × Φ⁻¹(0.75) = 1.349`, so this is
     a consistent estimator of σ for Gaussian data — we will state that derivation, not just the
     constant.
  2. **Small-lot guard.** For `n < 20` LATENTIS must not silently apply the 1.35 divisor. It
     switches to `MAD × 1.4826` and/or applies a finite-sample correction factor, **and flags
     reduced statistical power in the UI**. This is a genuine engineering safeguard that also
     defends against a red-team small-lot attack.
  3. The worked example in the problem statement is checkable: for a lot with median 10 µA and
     `IQR ≈ 2.7 µA` ⇒ `RobustSigma ≈ 2.0 µA` ⇒ upper PAT limit ≈ `10 + 12 = 22 µA`. A part at
     45 µA is ~17.5 robust σ out — an extreme, unambiguous DPAT failure while passing the 50 µA
     absolute limit. **This arithmetic is the spine of the live demo.**
  4. Because DPAT's 6σ is deliberately loose (it targets gross outliers at low false-reject cost),
     `k` is exposed as a **risk-appetite dial** with the FN/FP trade-off curve plotted, rather
     than being a magic number.
- **Confidence:** HIGH for the formula as reported by a source that names AEC-Q001 Rev D; MEDIUM
  that Rev D's exact wording matches (re-verify: `HUMAN-002`).

### D-CD-03 — Non-Gaussian and multivariate outlier methods used alongside PAT

- **Finding:** Reported alongside PAT for non-normal and multivariate cases:
  | Method | Bounds / form |
  |---|---|
  | IQR fences | `Q1 − k·IQR`, `Q3 + k·IQR`, `k` typically 1.5 or 2 |
  | Tukey's fences | same, `k = 1.5` (mild), `k = 3.0` (extreme) |
  | SIQR | semi-IQR = IQR / 2 (handles asymmetry) |
  | Adjusted boxplot | `Q1 − 1.5·e^(−3·MC)·IQR`, `Q3 + 1.5·e^(3·MC)·IQR`, `MC` = medcouple |
  | MAD | median absolute deviation from a central measure |
  | Mahalanobis | `D² = (x − m)ᵀ C⁻¹ (x − m)` |
  Medcouple `MC` is an outlier-resistant skewness measure, making the adjusted boxplot preferable
  to plain Tukey fences for strongly skewed data. Mahalanobis catches joint deviations invisible
  in per-parameter histograms.
- **Source:** [yieldWerx — PAT outlier-detection guide](https://yieldwerx.com/blog/ultimate-guide-to-outlier-detection-using-part-average-testing/).
- **Relevance:** Directly supplies the "evaluate multiple methods" requirement with an
  industry-recognised, explainable shortlist — no deep learning needed.
- **Implication:** Module A's ensemble is exactly this family: DPAT (primary), adjusted boxplot
  (skew-aware, and IDDQ *is* strongly skewed), MAD-z (robust univariate), robust Mahalanobis via
  Minimum Covariance Determinant (multivariate/joint), plus Isolation Forest strictly as a
  **non-parametric cross-check**, never as the primary verdict. See
  `models/anomaly/ANOMALY_SPEC.md § 4`. Note: one source shows an internal inconsistency between
  the "Median Absolute Deviation" heading and a mean-absolute-deviation formula — we implement the
  **median** form (`MAD = median(|x − median(x)|)`, scaled by 1.4826) and say so explicitly.
- **Confidence:** HIGH for the formula family; MEDIUM for the specific adjusted-boxplot sign
  convention (verify against Hubert & Vandervieren before use).

### D-CD-04 — Spatial/contextual outliers: GDBN and Zonal PAT

- **Finding:** Good-Die-in-Bad-Neighbourhood (GDBN) flags "a working die surrounded by a failing
  die" and removes it precautionarily. Zonal PAT partitions the wafer into user-defined regions
  and bins failures per zone, surfacing localised process drift that a whole-wafer population
  would absorb.
- **Source:** [yieldWerx — PAT outlier-detection guide](https://yieldwerx.com/blog/ultimate-guide-to-outlier-detection-using-part-average-testing/).
- **Relevance:** Establishes that **contextual/positional** anomaly detection is accepted practice
  in this domain — the anomaly is defined relative to *neighbours*, not only to the whole lot.
- **Implication:** LATENTIS carries the idea from wafer space into **burn-in oven space**. Parts
  occupy a `(board_id, socket_id, thermal_zone)` position in a burn-in chamber. We implement
  **Zonal DPAT** (limits computed per thermal zone when zone counts permit) and a
  **Good-Part-in-Bad-Socket** attribution check. This yields the *part vs. socket vs. zone*
  attribution feature (`models/anomaly/ANOMALY_SPEC.md § 7`), which a test engineer will
  immediately recognise as a real problem — testers and sockets genuinely do drift — and which
  almost no competing submission will have.
- **Confidence:** HIGH for GDBN/Zonal PAT as practice; ASSUMPTION for the oven-space analogy —
  clearly labelled as our extension, not a cited standard.

---

## H. False-negative-sensitive detection

### D-H-01 — The Neyman–Pearson classification paradigm bounds the prioritised error type

- **Finding:** The NP paradigm "seeks classifiers that achieve a minimal type II error while
  enforcing the prioritized type I error controlled under some user-specified level α". NP
  umbrella algorithms produce classifiers whose prioritised error respects the bound α "with high
  probability, without specific distributional assumptions on the features and the responses".
  NP-ROC curves are the paradigm's analogue of ROC.
- **Source:** [Tong, Feng & Zhao — *Neyman–Pearson classification: parametrics and sample size requirement* (JMLR 21(12), arXiv:1802.02557)](https://arxiv.org/abs/1802.02557); [Tong, Feng & Li — *NP classification algorithms and NP-ROC curves* (arXiv:1608.03109; Science Advances)](https://arxiv.org/abs/1608.03109v1); [JMLR 18-577](http://jmlr.org/papers/volume21/18-577/18-577.pdf).
- **Relevance:** The evaluation criteria state plainly that a false negative is catastrophic. Most
  teams will respond by "weighting the positive class" or "moving the threshold until recall looks
  good" — neither of which *bounds* anything.
- **Implication:** LATENTIS assigns *defective* = class whose misclassification is prioritised, and
  selects its decision threshold by an NP-style **order-statistic rule on a held-out calibration
  set** so that the false-negative rate respects a user-specified `α` with high probability. The
  UI exposes `α` as the **Mission Risk Posture** control and plots the NP-ROC so the FP cost of a
  tighter FN bound is visible. Result: we can state *"FNR ≤ α with ≥ 1 − δ confidence on
  exchangeable data"* instead of *"we got good recall on our test split"*. This is a
  qualitatively stronger claim and it is cheap to implement (a quantile of calibration scores).
- **Confidence:** HIGH for the paradigm and guarantee form; MEDIUM on the finite-sample constant
  we will use — the exact order statistic and its `δ` must be derived and unit-tested
  (`TEST-NP-001..004`), not assumed.

### D-H-02 — Conformal prediction gives distribution-free finite-sample coverage

- **Finding:** Conformal prediction constructs prediction sets satisfying a distribution-free
  finite-sample guarantee under an i.i.d./exchangeability assumption. Split (inductive) conformal
  prediction is the computationally cheap variant: fit on a training split, compute nonconformity
  scores on a disjoint calibration split, and take a quantile. One-sided conformal intervals
  achieving marginal validity can be constructed directly. Known limitation: for split conformal
  the guarantee is **training-conditional only in expectation** — average coverage over
  calibration draws equals the nominal level, while the realised coverage for one particular split
  fluctuates; and marginal coverage can hold while **per-group coverage collapses**.
- **Source:** [*Distribution-Free Finite-Sample Guarantees and Split Conformal Prediction* (arXiv:2210.14735)](https://arxiv.org/pdf/2210.14735v1); [*Conformal Prediction Intervals with Tail-Specific Guarantees* (arXiv:2606.18199)](https://arxiv.org/pdf/2606.18199); [*Probabilistic Conformal Coverage Guarantees in Small-Data Settings* (arXiv:2509.15349)](https://arxiv.org/html/2509.15349v1); [Angelopoulos, Bates, Fisch, Lei & Schuster — *Conformal Risk Control* (arXiv:2208.02814)](https://arxiv.org/pdf/2208.02814v4.pdf).
- **Relevance:** This is the mathematically correct answer to "how do I reject on a *forecast*
  when a missed defect is catastrophic?" You must not reject on a point estimate — you must reject
  on an upper bound with a known coverage level.
- **Implication (flagship design decision):** Module B's rejection rule uses a **one-sided upper
  conformal bound** `Û₁₆₈(1−α)` on `Value_168h`, not the point prediction. A part is rejected when
  the *bound* — not the estimate — crosses the safety boundary. Consequences:
  1. The FN-sensitivity requirement is satisfied *by construction*, with a citable guarantee.
  2. Coverage is **empirically verifiable** on held-out data (`TEST-CP-001`: measured coverage must
     fall inside the expected binomial band for the nominal level) — a real, falsifiable claim.
  3. Per the cited limitations we implement **Mondrian/group-conditional conformal**, conditioning
     on `component_type` (and on lot where `n` allows), so a group's coverage cannot silently
     collapse behind good marginal coverage. We report **per-group** coverage, not just marginal.
  4. Because validity needs exchangeability, LATENTIS ships an **exchangeability guard** that
     tests the incoming lot against the calibration distribution and, on failure, *declares the
     guarantee void* and falls back to a conservative rule. Openly stating when our guarantee does
     not apply is the strongest possible answer to an adversarial reviewer.
- **Confidence:** HIGH for the method and its guarantee; HIGH for the stated limitations (they are
  drawn from sources whose entire subject is those limitations).

---

## I. Explainable AI for industrial inspection · J. Aerospace QA workflow · O. Human-in-the-loop

### D-I-01 — In a qualified screening flow the *decision record* is the deliverable

- **Finding:** Qualified flows are built on documented, auditable steps: specified interim
  electrical tests, recorded PDA computations, delta-limit tables tied to a drawing, and final
  electrical tests against an applicable device specification. Upscreening practice likewise turns
  on documented evidence per lot.
- **Source:** [Tekmos MIL-STD-883 summary](https://tekmos.com/support/mil-std-883-standard); [MIL-PRF-38535](https://nepp.nasa.gov/DocUploads/668C05F1-46E9-415A-8360C8B9F66A4344/MIL-PRF-38535.pdf); [TI upscreening application note](https://www.ti.com/pdfs/hirel/mltry/btospace.pdf).
- **Relevance:** Determines what "explainability" must mean *here*. It is not a SHAP plot for a
  data scientist. It is an **auditable disposition record** that survives a quality audit years
  later, when the engineer who ran the screen is unavailable.
- **Implication:** Explainability in LATENTIS is specified as a **Provenance Ledger**
  (`docs/PROVENANCE_SPEC.md`): every displayed quantity carries the inputs, the formula
  identifier, the parameter values, the model version and the dataset hash used to produce it —
  and the UI can re-derive it in front of the inspector. Effects: (a) an inspector can *check* the
  system instead of trusting it; (b) the exported report is a genuine audit artifact; (c) a red
  team cannot find fabricated values because every value proves itself. **Feature-attribution
  plots are supplementary, not primary.**
- **Confidence:** HIGH for the auditability requirement; ASSUMPTION for the specific ledger
  design, which is our engineering choice.

### D-I-02 — The system must recommend, and a human must dispose

- **Finding:** Screening standards assign disposition authority to specified criteria and to the
  responsible quality organisation (PDA computations, lot acceptance/rejection, upscreening
  decisions), not to an automated scorer.
- **Source:** As D-I-01.
- **Relevance:** Defines the product's role and its liability boundary.
- **Implication:** LATENTIS is **decision support**, never an autonomous reject actuator. Every
  flag carries a mandatory inspector action: `CONCUR`, `OVERRIDE (with reason)`, or `DEFER FOR
  RETEST`. Overrides are persisted and become a labelled feedback stream — which is both an
  honest workflow and a credible answer to "how does this improve over time?" We will *not* claim
  online learning; we will claim a captured, auditable feedback loop, which is what the phase
  actually delivers.
- **Confidence:** HIGH.

### D-I-03 — Measurement-system validity is itself a domain concern

- **Finding:** Measurement System Analysis for non-normal data is an active topic in AEC's own
  workshop programme.
- **Source:** [NXP / Ippon Innovation — *Measurement System Analysis for Non-normal Data*, AEC European Workshop 2025](http://aecouncil.com/files/Workshops/2025_European_AEC_Workshop/T6_1%20AEC%202025%20EU%20Workshop%20-%20NXP-Ippon%20Innovation.pdf).
- **Relevance:** Practitioners take seriously that an apparent part anomaly may be a measurement
  anomaly. A screening tool that cannot distinguish them will generate distrust on first contact
  with a real test floor.
- **Implication:** Validates the *part vs. socket vs. zone* attribution module (D-CD-04) and the
  `sensor_noise_anomaly` class in the synthetic dataset. LATENTIS must be able to say *"this looks
  like a tester artefact, not a part defect — recommend retest before disposition"*. In a live
  demo this is a memorable moment: the system declining to condemn a good part.
- **Confidence:** MEDIUM (source is a workshop title/abstract, not read in full) — but the
  engineering point stands independently.

---

## Consolidated implications table

| ID | Drives |
|----|--------|
| D-A-01 | Presentation opening; project framing |
| D-A-02 | Read-point grid 0/24/96/168 h @ 125 °C |
| D-A-03 | Lot-level disposition + PDA escalation |
| D-A-04 | Module B framed as *predictive delta-limit screening*; limits are config |
| D-A-05 | Standard-agnostic `ScreeningProfile` |
| D-B-01 | Arrhenius temperature coupling in generator; margin in equivalent field hours |
| D-B-02 | Trajectory-first defect model; Escape Set construction |
| D-B-03 | Shape–Amplitude decomposition; linear extrapolation as measured baseline |
| D-B-04 | IDDQ as primary parameter; variance-stabilising transform |
| D-CD-01 | Module A baseline = DPAT (standards-anchored) |
| D-CD-02 | Exact formula, `k` dial, small-lot guard, demo arithmetic |
| D-CD-03 | Ensemble shortlist: DPAT, adjusted boxplot, MAD-z, robust Mahalanobis, IF cross-check |
| D-CD-04 | Zonal DPAT; Good-Part-in-Bad-Socket attribution |
| D-H-01 | NP threshold selection; Mission Risk Posture dial; NP-ROC |
| D-H-02 | Conformal upper bound as the reject rule; Mondrian conformal; exchangeability guard |
| D-I-01 | Provenance Ledger as the definition of explainability |
| D-I-02 | Human-in-the-loop disposition; override capture |
| D-I-03 | Measurement-vs-part attribution; `sensor_noise_anomaly` class |

## Open research questions

| ID | Question | Blocks | Owner |
|----|----------|--------|-------|
| RQ-01 | Exact AEC-Q001 Rev D wording for DPAT limits, minimum sample size, and disposition of PAT-fail/spec-pass parts | Normative claims in slides (not the implementation) | Research Scientist |
| RQ-02 | Do ISRO/ECSS flows publish delta-limit magnitudes we may cite as realistic ranges? | Realism of default config; nothing else | Research Scientist |
| RQ-03 | Correct finite-sample correction for `IQR/1.35` at `n < 20` | `TEST-STAT-004` | Data + ML Engineer |
| RQ-04 | Adjusted-boxplot medcouple sign convention (Hubert & Vandervieren) | `TEST-STAT-006` | Data + ML Engineer |
| RQ-05 | Exact NP order statistic and its `δ` for our calibration sizes | `TEST-NP-002` | Data + ML Engineer |
| RQ-06 | Published `Ea` ranges per named mechanism, to justify generator defaults | Generator realism narrative | Research Scientist |

**None of RQ-01..RQ-06 blocks implementation.** All defaults are configuration values with
documented provenance; refining them changes a YAML file, not the architecture.





