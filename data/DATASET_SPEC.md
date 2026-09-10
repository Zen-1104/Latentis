# DATASET_SPEC.md — Synthetic Burn-In Dataset

**Owner:** Data + ML Engineer · **Status:** Specified, not generated
**⚠️ ALL DATA IS SYNTHETIC. No real ISRO data is used. See `PROJECT_MASTER_SPEC.md § 14`.**

## 1. Artifacts

Three **physically separate** files (not views), which is how leakage risk LK-1 is closed
structurally:

| Artifact | Contents | Who may read it |
|---|---|---|
| `screening.parquet` | Read-points at **0 h and 24 h only**, plus static metadata | The system, at decision time |
| `truth.parquet` | Read-points at **96 h and 168 h**, plus all labels | The evaluation harness only |
| `full.parquet` | Everything, plus latent generator state | The generator's own tests only |
| `manifest.json` | Config hash, generator git SHA, library versions, row counts, per-file SHA-256, seed | Everyone |

`screening.parquet` **contains no 96 h or 168 h columns at all.** A model cannot leak from a column
that does not exist in the file it reads.

## 2. Default scale

| Quantity | Default | Rationale |
|---|---|---|
| Lots | 40 | Enough for lot-disjoint 5-fold CV plus a held-out block |
| Parts per lot | 30–500, log-uniform | Real lots vary hugely; deliberately includes `n < 20` lots to exercise the small-lot guard |
| Component types | 5 | `CMOS_LOGIC`, `SRAM`, `LDO_REG`, `OPAMP`, `POWER_MOSFET` |
| Parameters per part | 6 | See § 4 |
| Read-points | 0, 24, 96, 168 h | Per D-A-02 |
| Total measurement rows | ≈ 40 × 150 × 6 × 4 ≈ 144 000 | Exercises the throughput NFR |
| Latent-defect prevalence | 3 % (configurable 1–5 %) | Labelled `assumed` (DQ-02) |
| Seeds for evaluation | 5 | MLR-05 |

## 3. Row grain

One row per `(component_id, parameter, elapsed_hours)`. Long format, not wide — because
parameters have different units, different limits and different degradation physics, and a wide
format invites unit-mixing bugs (`CLAUDE.md § 5`).

## 4. Measured parameters

Every parameter is chosen because it carries distinct physics, not because it sounds technical.

| Parameter | Unit | Nominal | Absolute max | Degradation direction | Why included |
|---|---|---|---|---|---|
| `iddq_standby` | µA | 8–14 | 50 | ↑ | The problem statement's flagship parameter; the classic latent-defect detector (D-B-04). Strongly right-skewed. |
| `leakage_input` | nA | 1–5 | 100 | ↑ | Second, weakly-correlated leakage path — lets a *joint* anomaly exist that neither parameter shows alone (the case only Mahalanobis catches) |
| `prop_delay` | ns | 8–12 | 20 | ↑ | Timing degradation (NBTI-like); slower, more log-shaped drift than leakage |
| `vth_shift` | mV | 0 | ±50 | ↑ or ↓ | **Bidirectional** — forces the code to handle two-sided limits and signed drift correctly, a common source of bugs |
| `icc_active` | mA | 20–30 | 45 | ↑ | Correlated with `iddq_standby` (shared supply path) — creates realistic correlation structure |
| `output_res` | mΩ | 40–60 | 100 | ↑ | Interconnect/package-side mechanism; different `Ea`, so it responds differently to zone temperature |

`vth_shift` earns its place specifically because a two-sided parameter breaks any implementation
that assumed "higher is worse". `leakage_input` earns its place because without a second,
imperfectly-correlated leakage path the multivariate detector has nothing to find that a univariate
one would miss — and then it should be deleted per AG-10.

## 5. Schema

### 5.1 `measurements` (long)

| Column | Type | Notes |
|---|---|---|
| `component_id` | str | `C-{lot}-{nnnn}`; **carries no information** about health (INV-2 / RT-004) |
| `lot_id` | str | `L-2026-{nnn}` |
| `component_type` | enum | § 2 |
| `parameter` | enum | § 4 |
| `elapsed_hours` | int | 0 / 24 / 96 / 168 |
| `measurement_value` | float | The reading |
| `measurement_unit` | str | Always present; validated against the profile |
| `status` | enum | `OK` / `BELOW_LOD` / `OVERRANGE` / `NOT_MEASURED` / `SUSPECT` |
| `temperature_c` | float | **Actual** measured zone temperature, not the setpoint |
| `voltage_v` | float | Applied bias during read |
| `read_timestamp` | datetime | Ordering and tester-drift analysis |
| `absolute_limit_low` / `_high` | float | From the profile; denormalised for auditability of the exact limit used |
| `board_id` / `socket_id` / `thermal_zone` | str | Position in the burn-in chamber — enables Zonal DPAT and socket attribution (D-CD-04) |
| `tester_id` | str | Equipment identity, for tester-drift attribution |
| `operator_id` | str | Pseudonymous (`OP-nn`); present because it is a real MSA covariate (D-I-03), not for flavour |
| `data_provenance` | const | Always `"SYNTHETIC"` (DR-09) |
| `ingest_id` | str | Traceability to the upload |

### 5.2 `components` (static)

`component_id`, `lot_id`, `component_type`, `board_id`, `socket_id`, `thermal_zone`,
`date_code`, `wafer_id`, `die_x`, `die_y`.

`wafer_id`/`die_x`/`die_y` are included **only** because they let us demonstrate the spatial-context
idea honestly if time allows; if unused by any model, they are documented as descriptive metadata
rather than quietly implying an unimplemented capability.

### 5.3 `truth` (withheld)

| Column | Notes |
|---|---|
| `component_id` | Join key |
| `value_96h`, `value_168h` | Per parameter — the hidden regression targets |
| `failure_label` | `HEALTHY` / `LATENT_DEFECT` / `FAILED` |
| `degradation_mode` | § 6 |
| `stratum` | `S0..S5` (§ 7) |
| `is_escape` | `true` when inside absolute limits at **all** read-points **and** defective |
| `true_amplitude`, `true_shape_exponent`, `true_onset_hours` | Latent generator state, for diagnostics |
| `sensor_artefact_magnitude` | Non-zero only for `S4` |

## 6. Behaviour classes

Each class is a distinct generative mechanism, not a different random seed.

| Class | Mechanism | Label | Must the system flag it? |
|---|---|---|---|
| `healthy_stable` | Baseline + measurement noise only | HEALTHY | No — flagging is a false positive |
| `healthy_noisy` | Baseline + 3× measurement noise | HEALTHY | No — this is the primary FP pressure |
| `gradual_drift` | Small amplitude, sub-linear shape, stays well inside limits at 168 h | HEALTHY | No — normal wear, and this is the hardest FP case |
| `accelerated_drift` | Large amplitude, sub-linear shape, **crosses** the limit before or near 168 h | LATENT_DEFECT | **Yes** — Module B's target |
| `early_latent_defect` | Elevated baseline (lot-relative outlier from 0 h) with modest drift, **never** exceeding the absolute limit | LATENT_DEFECT | **Yes** — Module A's flagship target |
| `sudden_failure` | Step change between read-points, exceeding the limit | FAILED | Yes — trivially; a sanity case |
| `intermittent` | Alternates between nominal and elevated across read-points | LATENT_DEFECT | **Yes** — the hardest case; a 2-point view may see either state, which is *deliberately* a partial-observability failure mode we report honestly |
| `sensor_noise_anomaly` | Part is healthy; the *measurement* is corrupted, coherently across a socket | HEALTHY | **No** — must be attributed to the setup and recommended for retest, not rejected |
| `lot_shift` | The whole lot's centre moves; parts are internally consistent | HEALTHY | **No** — DPAT must absorb this where SPAT would fail the lot (D-CD-02) |

`intermittent` is included knowing we may not detect it reliably from two read-points. Reporting
that limitation with a measured number is stronger than excluding the class and implying we handle
everything.

## 7. Difficulty strata and the Escape Set

| Stratum | Definition | Target metric |
|---|---|---|
| `S0-clear-fail` | Exceeds an absolute limit at some read-point | Sanity check — static screening already catches these |
| `S1-escape-anomaly` | Inside absolute limits at **all** read-points, but a lot-relative outlier at 24 h; defective | **Latent Escape Recall (Module A)** |
| `S2-escape-drift` | Inside absolute limits at all read-points, lot-relative **normal** at 24 h, unsafe projected 168 h trajectory; defective | **Latent Escape Recall (Module B)** — the hardest and most valuable stratum |
| `S3-decoy-healthy` | Healthy, but sits high in its lot by chance | False-positive rate |
| `S4-decoy-sensor` | Measurement artefact; part healthy | Attribution accuracy; must not be rejected |
| `S5-lot-shift` | Whole lot shifted, internally consistent | Must not fail the lot |

**The Escape Set** = `S1 ∪ S2` = every part where `absolute_limit → PASS` but ground truth says
defective. This is the flagship evaluation target and the reason the project exists.
`LER = recall on the Escape Set`, always reported beside FPR and flag rate.

**By construction, static absolute-limit screening scores `LER = 0` on the Escape Set.** That is
not rhetoric — it is a definitional property of the stratum, and it is the single cleanest
demonstration available of the problem the problem statement describes.

### 7.1 Construction constraint (the part most likely to be got wrong)

For `S1` and `S2` the generator must **enforce**, not hope for, the inside-limits property:

```
for every parameter p and every read-point t ∈ {0, 24, 96, 168}:
    limit_low(p) < value(part, p, t) < limit_high(p)
```

Implementation: generate the trajectory, then **rejection-sample** (re-draw amplitude with a
reduced ceiling) until the constraint holds, capped at `max_attempts`; if the cap is hit, reduce
the amplitude analytically to the largest value satisfying the constraint and record
`amplitude_clipped: true`. Any part failing the constraint is reassigned to `S0`, never silently
mislabelled. `TEST-GEN-004` asserts `S1 ∪ S2` is non-empty and that **every** member satisfies the
constraint — if that test fails, the flagship claim is invalid and the release is blocked.

## 8. Deliberate data imperfections

Real test data is dirty. A generator that produces clean data trains a system that dies on contact.

| Imperfection | Rate (default) | Purpose |
|---|---|---|
| Missing read-point rows | 1.5 % | Exercises FR-103 and the `INSUFFICIENT_DATA` path |
| `BELOW_LOD` censored readings | 0.5 % of leakage rows | Censoring must not be coerced to 0 (FR-107) |
| `OVERRANGE` readings | 0.2 % | Must not be coerced to the limit |
| Duplicate `(part, param, hours)` rows | 0.3 % | Duplicate detection |
| Unit inconsistency (mA where µA expected) | 2 lots | Unit validation (FR-108) — this is a *real* and dangerous field error |
| Timestamp jitter / mild non-monotonicity | 1 % | Ordering robustness |
| Single-part lot | 1 lot | Degenerate-statistics guard: `IQR = 0`, `n = 1` |
| Zero-IQR lot (all identical readings) | 1 lot | **Division-by-zero guard** — the classic crash, and `RT-009` requires we handle it |
| Tester drift across a shift | 1 tester | Tester-attribution capability |
| A lot with 3 parts | 1 lot | Small-`n` guard path |

The zero-IQR lot deserves emphasis: `robust_sigma = IQR/1.35 = 0` makes every non-median part
infinitely many sigmas out. The correct behaviour is a documented degenerate-case rule (fall back
to MAD; if MAD is also 0, report `NO_VARIATION` and defer to absolute limits with a warning) — not
a crash and not `inf`.

## 9. Correlation structure

Not independent noise per parameter — structured, and generated from a factor model (see
`DATA_GENERATION_SPEC.md § 5`):

- `iddq_standby` ↔ `icc_active`: strong positive (shared supply path), target ρ ≈ 0.6–0.75.
- `iddq_standby` ↔ `leakage_input`: weak positive, ρ ≈ 0.2–0.35 — deliberately weak so that a
  *joint* outlier can exist that neither margin reveals. This is the case that justifies the
  multivariate detector, and if the ablation shows no benefit, the detector goes (AG-10).
- `prop_delay` ↔ `vth_shift`: moderate positive (threshold shift slows switching), ρ ≈ 0.4–0.55.
- `output_res`: near-independent of the silicon-side parameters (different mechanism).
- Within-lot common-mode component shared by all parts in a lot (process/lot effect) — this is what
  makes lot-relative analysis meaningful in the first place.
- Zone-level common-mode from temperature via Arrhenius.

Achieved correlations are **measured and published** in `reports/DATASET_PROFILE.md`, not asserted
here. If the achieved values differ from these targets, the report is right and this section is
updated.

## 10. Field-by-field justification summary

Every column exists for a stated reason. Columns we considered and **excluded** to avoid
technical-sounding noise: `humidity` (not a burn-in variable in a dry oven), `lot_yield` (a
derived aggregate that would leak the answer), `supplier_name` (invites spurious correlation with
no mechanism), `cost` (irrelevant to the physics), `esd_class` (static attribute with no read-point
interaction), `capacitance`/`resistance` as generic names (superseded by the specific, mechanism-
linked `output_res`). Excluding a plausible-sounding field is a design decision worth stating,
because the temptation to pad the schema is exactly what makes a synthetic dataset look fake.

## 11. Reproducibility

| Guarantee | Mechanism |
|---|---|
| Seed ⇒ identical bytes | `numpy.random.Generator(PCG64(seed))`, threaded explicitly; no global RNG |
| Adding a part does not perturb existing parts | Per-part streams via `SeedSequence(seed).spawn()` keyed on a stable part index |
| Config change is visible | `manifest.json` records the SHA-256 of the resolved config |
| Verifiable by a third party | `scripts/verify_reproducibility.sh` regenerates and compares hashes; CI-gated |

The `SeedSequence.spawn` detail is load-bearing: with a single shared stream, changing `n_parts`
silently changes every part's values and invalidates every previously reported metric.

## 12. Validation gates on the generated dataset

`scripts/validate_dataset.py` must pass before any dataset is used:

1. `S1 ∪ S2` non-empty; every member satisfies the § 7.1 inside-limits constraint.
2. Every `S0` member genuinely violates a limit somewhere.
3. Latent-defect prevalence within ±0.5 pp of the configured value.
4. No `component_id` collisions; every `component_id` has ≥ 1 measurement row.
5. `screening.parquet` contains **no** column derived from 96 h or 168 h data (column-name and
   value-correlation check).
6. Every configured imperfection is actually present at approximately its configured rate.
7. Achieved correlations reported (no pass/fail — reported, so drift from § 9 is visible).
8. All units consistent with the profile except in the deliberately-inconsistent lots.
9. `manifest.json` complete; all hashes verify.
10. Every generator parameter carries a provenance tag (DR-03).

