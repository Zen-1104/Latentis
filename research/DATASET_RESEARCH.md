# DATASET_RESEARCH.md — Data Availability & Synthetic Strategy

**Owner:** Research Scientist + Data + ML Engineer

## 1. Is a real dataset available?

**Finding.** No public dataset of space-grade burn-in parametric read-points at
0/24/96/168 h with latent-defect ground truth was located. This is expected and explainable:

- Parametric test data (per-part, per-parameter measurements) is among the most commercially
  sensitive data a semiconductor manufacturer holds — it exposes yield, process capability and
  design margin.
- Space-grade screening data is additionally export-controlled and programme-specific.
- Ground-truth *latent-defect* labels only materialise years later through field returns, and
  those records rarely link back to the original burn-in read-points.

**Confidence:** HIGH that no suitable public dataset exists in the required shape.

**Related public data that is *not* a substitute, and why:**

| Dataset | Why it does not fit |
|---|---|
| NASA PCoE bearing / battery / turbofan (C-MAPSS) prognostics sets | Right *shape* (run-to-failure degradation), wrong domain and wrong parameters; no lot structure, no absolute datasheet limits, no lot-relative screening question |
| SECOM (UCI) semiconductor manufacturing | Process/sensor features with pass-fail labels, but no per-part time-series read-points and no lot-relative screening semantics |
| Public wafer-map defect sets (e.g. WM-811K) | Spatial defect *patterns*, not parametric drift |

**Design consequence.** A **documented, seeded, physically-motivated simulator** is not a
weakness to apologise for — it is the only scientifically available option, and it is *superior
to a real dataset for evaluation purposes in one specific way*: it gives us **ground-truth latent
labels**, which no real dataset would. We must say exactly this, in these terms, and then be
scrupulous about not overclaiming.

## 2. What C-MAPSS-style prognostics practice teaches us

**Finding.** The PCoE/C-MAPSS family established the accepted pattern for degradation datasets:
multiple units, unit-to-unit variability in initial wear, an operating-condition covariate,
sensor noise, and a *hidden* health state that must be inferred. Evaluation is on a held-out set
whose true remaining life is withheld.

**Relevance.** The SIH problem statement's own evaluation design ("MAE between predicted
`Value_168h` and the actual hidden ground-truth values") is precisely this pattern.

**Implication.** The LATENTIS generator adopts the same contract explicitly:

- `dataset_full` — everything, used only by the generator's own tests and by evaluation.
- `dataset_screening` — what the *system* is allowed to see at decision time: read-points at
  0 h and 24 h, plus static metadata. **No 96 h/168 h columns exist in this artifact at all.**
- `dataset_truth` — the withheld 96 h/168 h values and the latent labels, released to the
  evaluator only.

Separating these into three physical files, not three views of one file, closes leakage risk LK-1
structurally rather than by discipline. **Confidence:** HIGH (this is established practice).

## 3. Synthetic-data credibility: what makes a simulator defensible

**Finding / synthesis.** A synthetic industrial dataset is credible when (a) each stochastic
element has a stated physical or statistical justification, (b) the marginal distributions and
correlation structure are *reported and sanity-checkable*, (c) it is reproducible from a seed, and
(d) its limitations are enumerated. It is *not* credible when it is a pile of `np.random.normal`
calls whose parameters were chosen to make the model look good.

**Implication — five hard rules for the generator:**

1. **Every parameter has a provenance tag** in the config: `cited` (with the research ID),
   `derived` (from a cited quantity), or `assumed` (with a rationale string). The generator
   refuses to run if any parameter lacks one. This is enforced by `TEST-GEN-001` and it is a
   genuinely unusual, high-credibility feature.
2. **Physics before noise.** Temperature enters through the Arrhenius AF (D-B-01), not as extra
   Gaussian jitter. Degradation shapes come from the named-mechanism families (D-B-03).
3. **The generator is adversarial to us.** It is *specified to produce cases our own method finds
   hard* — see the Escape Set and the `intermittent`/`sensor_noise` classes. A generator tuned to
   flatter the model is fabrication; `RT-002` audits for it.
4. **Distributional realism is reported, not asserted.** `reports/DATASET_PROFILE.md` is generated
   from the data: per-parameter marginals, skewness, lot-to-lot variance components,
   parameter–parameter correlations, and the fraction of defects that stay inside absolute limits.
5. **Never a claim of realism beyond structure.** We claim the dataset reproduces the *structural
   phenomena* the problem statement describes (lot-relative anomalies inside absolute limits,
   sub-linear drift, measurement artefacts, lot shifts). We do **not** claim the numbers match any
   real device. `PROJECT_MASTER_SPEC.md § 14` makes this binding.

**Confidence:** ASSUMPTION (this is our methodology choice), but each rule maps to a
specific red-team attack it defeats.

## 4. Required difficulty structure

A dataset where all defects are obvious proves nothing. The generator must produce a graded
difficulty spectrum, and evaluation must be reported **per stratum**:

| Stratum | Definition | Purpose |
|---|---|---|
| `S0-clear-fail` | Exceeds absolute limit at some read-point | Sanity: static screening already catches these |
| `S1-escape-anomaly` | Inside absolute limits at *all* read-points, but lot-relative outlier at 24 h | **Module A's flagship target** |
| `S2-escape-drift` | Inside absolute limits at 0/24/96/168 h, lot-relative *normal* at 24 h, but unsafe projected trajectory | **Module B's flagship target** — the hardest and most valuable case |
| `S3-decoy-healthy` | Healthy but noisy; sits high in its lot by chance | False-positive pressure |
| `S4-decoy-sensor` | Measurement artefact, part is fine | Tests attribution; must **not** be rejected |
| `S5-lot-shift` | Whole lot shifted; individually "unusual" vs. history but internally consistent | Tests that we do not fail a whole good lot — the classic DPAT-vs-SPAT distinction (D-CD-02) |

**`S1` and `S2` existing at all is what makes the demo honest.** Reporting recall separately on
`S1` and `S2` is what makes the claim measurable. `S5` is the case most teams will fail loudly.

## 5. Reproducibility contract

| Requirement | Mechanism |
|---|---|
| Same seed ⇒ identical bytes | Single `numpy.random.Generator(PCG64(seed))` threaded explicitly; **no global RNG**; no dict/set iteration order in numeric paths |
| Provenance | `manifest.json` per dataset: config hash, generator git SHA, library versions, row counts, per-file SHA-256 |
| Independence of parts | Per-part RNG streams via `SeedSequence.spawn`, so adding a part does not change existing parts' values |
| Verifiability | `scripts/verify_reproducibility.sh` regenerates and diffs hashes; CI-gated |

The per-part `SeedSequence.spawn` detail matters: without it, changing `n_parts` reshuffles the
whole dataset and every previously reported number silently changes. That is a subtle
reproducibility bug most projects ship. **Confidence:** HIGH (standard `numpy` practice).

## 6. Open questions

| ID | Question | Impact if unresolved |
|---|---|---|
| DQ-01 | Realistic lot-to-lot vs. within-lot variance ratio for IDDQ on a space-grade process | Only affects default config realism; swept in sensitivity analysis |
| DQ-02 | Realistic latent-defect prevalence (we assume 1–5 %, configurable) | Affects AUPRC baseline; we report prevalence alongside every metric |
| DQ-03 | Typical socket-to-socket measurement bias magnitude on real burn-in boards | Affects `S4` difficulty only |
| DQ-04 | Whether ISRO flows record per-socket position at all | Affects whether the attribution feature is deployable as-is; documented as a data-availability precondition in `HUMAN_ACTIONS.md` |
