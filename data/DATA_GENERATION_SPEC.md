# DATA_GENERATION_SPEC.md — Generator Design

**Owner:** Data + ML Engineer · Implements `DATASET_SPEC.md`
**⚠️ SYNTHETIC DATA GENERATOR. Produces no claim about any real device.**

## 1. Design stance

The generator is a **forward simulation of a documented physical and statistical model**, not a
collection of random draws. Two rules make that concrete and auditable:

1. **Every parameter carries a provenance tag.** The config schema requires
   `{value, provenance: cited|derived|assumed, source, rationale}` for each numeric parameter, and
   the generator **refuses to start** if any tag is missing (`TEST-GEN-001`). This is unusual, cheap,
   and it directly answers the strongest attack on any synthetic dataset — "you tuned the data".
2. **The generator is written against a frozen spec, before the detector exists**, and that ordering
   is visible in git history (DR-10). A generator authored after the model is a generator tuned to
   the model.

## 2. Generative model

For part `i`, parameter `p`, read-point `t`:

```
value(i,p,t) = μ_lot(p, ℓ(i))                     lot centre        (process/lot effect)
             + δ_type(p, τ(i))                    type offset
             + b_i(p)                             part-to-part baseline offset
             + A_i(p) · Φ(t ; shape_i, τ_i) · AF(T_i,zone, Ea_p)     degradation
             + s_socket(p, k(i)) + s_tester(p, m(i), t)              setup effects
             + η(i,p,t)                            measurement noise
             [+ step_i(p,t)]                       sudden-failure step, if applicable
```

Terms, with their justification:

| Term | Distribution / form | Provenance |
|---|---|---|
| `μ_lot` | `Normal(μ_type, σ_lot)`; `σ_lot/σ_within` set by config | `assumed` (DQ-01) — this ratio is *the* key realism knob and is swept in sensitivity analysis |
| `δ_type` | Fixed per `component_type` | `assumed` |
| `b_i` | Right-skewed for leakage: `LogNormal`; symmetric `Normal` for delay/vth | `derived` from D-B-04 (leakage distributions are strongly right-skewed) |
| `A_i` | Class-dependent: ≈0 healthy; `LogNormal` for drifters; **rejection-sampled** for `S1`/`S2` | `assumed` per class, with the inside-limits constraint enforced (`DATASET_SPEC § 7.1`) |
| `Φ(t)` | `(t/24)^n`, `log(1+t/τ)/log(1+24/τ)`, or `(1−e^(−t/τ))/(1−e^(−24/τ))`, normalised to `Φ(24)=1` | `derived` from D-B-03 (sub-linear/saturating degradation) |
| `AF` | `exp[(Ea/k_B)(1/T_ref − 1/T_zone)]`, T in K | **`cited`** — D-B-01 |
| `Ea` | Per-parameter, 0.3–0.9 eV | `cited` range (D-B-01); the specific per-parameter value is `assumed` (RQ-06) |
| `s_socket` | Small constant offset for affected sockets | `derived` from D-I-03/D-CD-04 |
| `s_tester` | Slow linear drift over `read_timestamp` | `assumed` |
| `η` | `Normal(0, σ_meas(p))`, plus heteroscedasticity: `σ ∝ √value` for leakage | `derived` — shot-noise-like scaling; leakage measurement precision degrades with magnitude |
| `step_i` | Multiplicative jump at a random read-point | `assumed`, only for `sudden_failure` |

**The critical property:** `Φ(t)` is *sub-linear* (`n < 1`, or log/saturating), so a naïve linear
extrapolation from `0→24 h` over-predicts `168 h`. This is not an accident of the generator — it is
the physically-motivated reason the Shape–Amplitude model beats the linear baseline, and it is what
makes that comparison a real result rather than a rigged one. If we made `Φ` linear, our own method
would show no advantage; we are generating data that is *harder* for us, not easier.

## 3. Per-part shape and identifiability

Each part draws `shape_i` (exponent `n` or time constant `τ`) from a **narrow** distribution around
its group's shape. Consequence: the population shape `Φ_g` is learnable, and per-part deviation
from it is a genuine, irreducible error source. The model cannot recover `shape_i` from two points —
which is exactly the real-world limitation, faithfully reproduced. Spread of `shape_i` is a config
knob; widening it degrades our own metrics, and we report metrics across a sweep of it in
`reports/SENSITIVITY.md`. Showing that curve, including where our method degrades, is far more
persuasive than a single flattering number.

## 4. Class assignment

Per lot, sample the class mixture from configured proportions, then per part:

```
1  assign class from the lot's mixture
2  draw parameters for the class
3  for early_latent_defect / accelerated_drift: enforce the inside-limits constraint
   by rejection sampling (S1/S2), else reclassify to S0
4  render read-points for t ∈ {0,24,96,168}
5  apply setup effects, then measurement noise
6  apply imperfections (missing/censored/duplicate/unit) per DATASET_SPEC § 8
7  derive stratum, failure_label, degradation_mode, is_escape from the *rendered* values,
   never from the intent
```

Step 7 matters: the label is computed from what was actually rendered. If noise pushes a part
outside limits, it becomes `S0` regardless of intent. Labels derived from intent rather than from
data are a subtle form of fabrication.

## 5. Correlation via a factor model

Correlated parameters are generated from shared latent factors, not by post-hoc copula fitting:

```
f_supply, f_threshold, f_package  ~ Normal(0,1)   per part
iddq      += λ₁ · f_supply
icc       += λ₂ · f_supply
leakage   += λ₃ · f_supply + λ₄ · f_leak_specific
prop_delay+= λ₅ · f_threshold
vth_shift += λ₆ · f_threshold
output_res+= λ₇ · f_package
```

Loadings `λ` are config with `derived` provenance, chosen to hit the § 9 target correlations.
Achieved correlations are **measured** into `reports/DATASET_PROFILE.md`. A factor model is used
because it is mechanistically interpretable — `f_supply` *means* something — whereas an arbitrary
covariance matrix is just numbers.

### 5.1 Joint-only anomalies

A configured subset of `early_latent_defect` parts receives an anomalous **factor** rather than an
anomalous parameter: each individual parameter stays within ~2σ of its lot, but the *combination*
is off-manifold (e.g. `iddq` high while `icc` is normal, breaking the shared-supply relationship).
These parts are detectable by robust Mahalanobis and *not* by any univariate rule. They are tagged
`joint_only: true` and reported as a separate line in the ablation table — which is how the
multivariate member proves it earns its place, rather than being assumed to.

## 6. Temperature model

Each `thermal_zone` has a stable offset from the 125 °C setpoint (`Normal(0, 3 °C)`, clipped to
±8 °C) plus small per-read jitter. `temperature_c` records the **actual** value. Degradation is
modulated by `AF` (§ 2), so hotter zones genuinely degrade faster — a real, physically-grounded
confound that Zonal DPAT exists to handle. This is what makes the zonal feature a solution to a
problem present in the data rather than a decoration.

## 7. Configuration

`data/config/default.yaml`, hashed into the manifest:

```yaml
seed: 20260930
scale: {n_lots: 40, parts_per_lot: {dist: loguniform, low: 30, high: 500}}
profile: mil_std_883_like     # read-point grid, absolute limits, PDA, k, alpha
class_mixture:                # per-lot Dirichlet around these proportions
  healthy_stable: {value: 0.62, provenance: assumed, rationale: "dominant class in a mature process"}
  healthy_noisy:  {value: 0.12, provenance: assumed, rationale: "FP pressure"}
  gradual_drift:  {value: 0.15, provenance: assumed, rationale: "normal wear-in"}
  accelerated_drift: {value: 0.04, provenance: assumed, rationale: "part of the 3% defect budget"}
  early_latent_defect: {value: 0.04, provenance: assumed, rationale: "Module A target"}
  sudden_failure: {value: 0.01, provenance: assumed, rationale: "sanity stratum"}
  intermittent:   {value: 0.01, provenance: assumed, rationale: "acknowledged hard case"}
  sensor_noise_anomaly: {value: 0.01, provenance: assumed, rationale: "attribution test"}
special_lots:
  lot_shift: 2
  unit_inconsistent: 2
  single_part: 1
  zero_iqr: 1
  tiny_n: 1
  tester_drift: 1
physics:
  k_boltzmann_ev_per_k: {value: 8.617333262e-5, provenance: cited, source: "SI/CODATA"}
  t_ref_c: {value: 125.0, provenance: cited, source: "D-A-02"}
  ea_ev:
    iddq_standby: {value: 0.7, provenance: cited, source: "D-B-01", rationale: "common default; swept"}
    prop_delay:   {value: 0.5, provenance: assumed, rationale: "NBTI-like; within cited 0.3-0.7 range"}
    output_res:   {value: 0.9, provenance: assumed, rationale: "package/interconnect mechanism"}
```

## 8. Outputs

`screening.parquet`, `truth.parquet`, `full.parquet`, `manifest.json`, plus
`reports/DATASET_PROFILE.md` (generated: marginals, skewness, variance components, achieved
correlations, stratum counts, escape counts, imperfection rates).

## 9. Anti-fabrication controls

| Control | Mechanism |
|---|---|
| No parameter without provenance | Generator refuses to start (`TEST-GEN-001`) |
| Generator cannot see the model | `datagen/**` may not import `backend/core/**` and vice versa (`TEST-ARCH-001`) |
| Labels derived from rendered values, not intent | § 4 step 7; `TEST-GEN-005` |
| Difficulty is not tuned to flatter us | `Φ` is sub-linear (§ 2); `shape_i` spread swept (§ 3); `S3`–`S5` decoys exist; `RT-002` audits |
| Achieved statistics published, not asserted | `reports/DATASET_PROFILE.md` is generated |
| Same seed ⇒ same bytes | `scripts/verify_reproducibility.sh`, CI-gated |

## 10. What the generator does **not** claim

It does not claim these are real device values, real ISRO lots, or a validated physical model of any
specific technology node. It claims to reproduce the **structural phenomena** named in the problem
statement: lot-relative anomalies that pass absolute limits, sub-linear parametric drift, thermal
acceleration, measurement artefacts, lot shifts, and dirty real-world data. That is the honest claim,
and it is sufficient for the evaluation the problem statement asks for.
