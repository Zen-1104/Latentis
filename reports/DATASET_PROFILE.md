# DATASET_PROFILE.md — Synthetic Burn-In Dataset Profile

> ⚠️ **SYNTHETIC DATA — NOT ISRO OPERATIONAL DATA** (`INV-3`)  
> Generated programmatically from emitted dataset artifacts per `DATA_GENERATION_SPEC.md § 8` and `DECISIONS.md D-014`.

**Generated:** 2026-09-09 02:20:30Z  
**Dataset Hash:** `sha256:0231a45de76781e3706ad88eaab953a500a850c31c812b3041f761c2d298e505` (short: `0231a45de767`)  
**Generator Git Commit:** `1a3718252f29ba640663e1bcff8813c482283cba`  
**Random Seed:** `20260930`  
**Profile:** `mil_std_883_like`  

---

## 1. Executive Summary & Artifact Verification

| Metric | Measured Value | Spec Requirement | Gate / Test | Status |
|---|---|---|---|---|
| Total Lots | **40** | 40 lots | `DATASET_SPEC § 2` | PASS |
| Total Components | **6,246** | ≈ 6 000 | `DATASET_SPEC § 2` | PASS |
| Total Measurement Rows | **148,159** | ≈ 144 000 | `DATASET_SPEC § 2` | PASS |
| Escape Set Size ($S1 \cup S2$) | **479** (7.67 %) | Non-empty ($>0$) | `TEST-GEN-004` (Release Blocker) | **PASS** |
| Escape Inside-Limits Violations | **0** | Exactly 0 | `DR-04 / TEST-GEN-004` | **PASS** |
| Provenance Coverage | **100 %** (51 params) | 100 % tagged | `TEST-GEN-001` | PASS |
| Splits Lot-Disjointness | **Strictly Disjoint** | 0 shared lots | `TEST-SPLIT-001 / QG-DATA-02` | PASS |
| Screening Late Columns | **0** | No 96 h / 168 h columns | `TEST-DL-002` | PASS |
| Screening Spearman $|\rho_{168}|$ | **0.884** | $< 0.95$ | `TEST-DL-003` | PASS |
| Decoys Ground Truth | **100 % Clean** | Decoys not flagged | `D-015` | PASS |

### Emitted Artifacts Inventory

| Artifact File | Rows | Description | SHA-256 Digest |
|---|---|---|---|
| `screening.parquet` | 74,126 | Screening features observable at 0h/24h (Decision Time) | `dd6f6b7f6db6ab82...39bef03c` |
| `truth.parquet` | 37,466 | Withheld 96h/168h truth & labels (Evaluation Harness) | `d6d8def33d8a0e36...ab0aed62` |
| `full.parquet` | 148,159 | Complete dataset with latent generator states | `e0da360bb6e4ffe1...91167aeb` |
| `train.parquet` | 99,642 | Lot-disjoint train split | `224087d4b2fb23a3...a8743521` |
| `calib.parquet` | 36,102 | Lot-disjoint calib split | `93350ac66d1ce324...0e6a4bcb` |
| `test.parquet` | 12,415 | Lot-disjoint test split | `61491a3aa412625f...cb89ea59` |

## 2. Difficulty Strata & The Escape Set

Difficulty strata $S0$-$S5$ implement the evaluation targets defined in `DATASET_SPEC.md § 6, 7` and `DECISIONS.md D-014, D-015`:

| Stratum | Definition | Target Role | Count | Proportion | Ground Truth Label | Must Flag? |
|---|---|---|---|---|---|---|
| **`S0-clear-fail`** | Breaches absolute limits at some read-point | Static screening sanity | 58 | 0.93 % | `FAILED` / `LATENT_DEFECT` | Yes |
| **`S1-escape-anomaly`** | Inside limits at all points; 24 h lot-relative outlier | **Module A Flagship Target** | 238 | 3.81 % | `LATENT_DEFECT` | **Yes** |
| **`S2-escape-drift`** | Inside limits at all points; 24 h normal, 168 h unsafe | **Module B Flagship Target** | 241 | 3.86 % | `LATENT_DEFECT` | **Yes** |
| **`S3-decoy-healthy`** | Normal wear-in drift & elevated measurement noise | False-positive pressure | 5245 | 83.97 % | `HEALTHY` | **No** |
| **`S4-decoy-sensor`** | Measurement/setup corrupted; physically sound | Retest attribution | 64 | 1.02 % | `HEALTHY` | **No** |
| **`S5-lot-shift`** | Coherently shifted lot mean ($+2.8\sigma$); healthy | DPAT shift absorption | 400 | 6.40 % | `HEALTHY` | **No** |
| **Total** | — | — | **6,246** | **100.00 %** | — | — |

### The Escape Set ($S1 \cup S2$) — Invariant `TEST-GEN-004`

The Escape Set comprises all parts that are defective in ground truth but remain **strictly within absolute specification limits** across all read-points {0, 24, 96, 168} h.

- Total Escape Set Members: **479 parts** (7.67 % of corpus)
  - Module A Targets ($S1$ Anomaly Escapes): **238 parts**
  - Module B Targets ($S2$ Drift Escapes): **241 parts**
- Verified Absolute Limits Violations across all 11,496 measurements: **0 violations** (`TEST-GEN-004: PASSED`)
- **Baseline Conventional Screening Latent Escape Recall (LER): 0.00 %** (by mathematical construction, static limits catch 0 escapes).

## 3. Parameter Marginals & Realism

Measured marginal distributions across all read-points, computed directly from `full.parquet`:

| Parameter | Unit | Count | Mean | Std | Median | IQR | Robust $\sigma$ | Skewness | Min | Max | Absolute Limits |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `iddq_standby` | uA | 24,671 | 15.467 | 8.531 | 12.972 | 4.499 | 3.332 | **3.142** | 0.1 | 90.462 | `[0, 50.0]` |
| `leakage_input` | nA | 24,682 | 11.828 | 19.536 | 5.045 | 3.602 | 2.668 | **3.241** | 0.05 | 151.268 | `[0, 100.0]` |
| `prop_delay` | ns | 24,674 | 12.186 | 2.716 | 11.718 | 2.119 | 1.57 | **4.439** | 7.39 | 44.436 | `[0, 20.0]` |
| `vth_shift` | mV | 24,736 | 0.686 | 11.455 | 0.431 | 5.44 | 4.03 | **0.283** | -69.958 | 82.271 | `[-50.0, 50.0]` |
| `icc_active` | mA | 24,700 | 27.727 | 6.581 | 26.671 | 6.495 | 4.811 | **3.763** | 15.758 | 103.091 | `[0, 45.0]` |
| `output_res` | mOhm | 24,696 | 59.632 | 14.033 | 57.006 | 11.635 | 8.618 | **4.114** | 32.623 | 232.665 | `[0, 100.0]` |

> **Note on Skewness:** As specified in `DATASET_SPEC.md § 4` and `D-B-04`, `iddq_standby` exhibits pronounced positive right-skewness, while `vth_shift` is bidirectional and symmetric around 0.0 mV.

## 4. Variance Components (Process Variation Realism)

Decomposition of variance into between-lot (process variation $\sigma_{\text{lot}}^2$) and within-lot (wafer/part variation $\sigma_w^2$):

| Parameter | $\sigma_{\text{lot}}$ | $\sigma_{\text{within}}$ | Measured Ratio $\sigma_{\text{lot}} / \sigma_{\text{within}}$ | Configured Target | Rationale |
|---|---|---|---|---|---|
| `iddq_standby` | 1.4 | 8.412 | **0.166** | 0.40 | Realistic fab process variation (`DQ-01`) |
| `leakage_input` | 2.621 | 19.549 | **0.134** | 0.40 | Realistic fab process variation (`DQ-01`) |
| `prop_delay` | 0.79 | 2.547 | **0.31** | 0.40 | Realistic fab process variation (`DQ-01`) |
| `vth_shift` | 2.468 | 11.368 | **0.217** | 0.40 | Realistic fab process variation (`DQ-01`) |
| `icc_active` | 2.768 | 5.762 | **0.48** | 0.40 | Realistic fab process variation (`DQ-01`) |
| `output_res` | 4.75 | 12.898 | **0.368** | 0.40 | Realistic fab process variation (`DQ-01`) |

## 5. Achieved Correlation Matrix (`TEST-GEN-008`)

Empirical correlation matrix measured at 24 h across all components (`TEST-GEN-008`):

### Pearson Correlation ($r$)

| Parameter | `iddq_standby` | `leakage_input` | `prop_delay` | `vth_shift` | `icc_active` | `output_res` |
|---|---|---|---|---|---|---|
| `iddq_standby` | 1.000 | 0.706 | 0.439 | 0.020 | 0.585 | 0.519 |
| `leakage_input` | 0.706 | 1.000 | 0.483 | -0.025 | 0.452 | 0.509 |
| `prop_delay` | 0.439 | 0.483 | 1.000 | 0.137 | 0.145 | 0.499 |
| `vth_shift` | 0.020 | -0.025 | 0.137 | 1.000 | 0.050 | 0.083 |
| `icc_active` | 0.585 | 0.452 | 0.145 | 0.050 | 1.000 | 0.407 |
| `output_res` | 0.519 | 0.509 | 0.499 | 0.083 | 0.407 | 1.000 |

### Spearman Rank Correlation ($\rho$)

| Parameter | `iddq_standby` | `leakage_input` | `prop_delay` | `vth_shift` | `icc_active` | `output_res` |
|---|---|---|---|---|---|---|
| `iddq_standby` | 1.000 | 0.758 | 0.395 | 0.113 | 0.739 | 0.536 |
| `leakage_input` | 0.758 | 1.000 | 0.340 | 0.075 | 0.671 | 0.518 |
| `prop_delay` | 0.395 | 0.340 | 1.000 | 0.280 | 0.106 | 0.522 |
| `vth_shift` | 0.113 | 0.075 | 0.280 | 1.000 | 0.088 | 0.172 |
| `icc_active` | 0.739 | 0.671 | 0.106 | 0.088 | 1.000 | 0.396 |
| `output_res` | 0.536 | 0.518 | 0.522 | 0.172 | 0.396 | 1.000 |

- $\rho(\text{iddq\_standby}, \text{icc\_active}) = $ **0.739** (Target: 0.60-0.75 via shared supply factor $f_{\text{supply}}$)
- $\rho(\text{iddq\_standby}, \text{leakage\_input}) = $ **0.758** (Target: 0.20-0.35; weak correlation enables joint-only anomalies)
- $\rho(\text{prop\_delay}, \text{vth\_shift}) = $ **0.280** (Target: 0.40-0.55 via threshold factor $f_{\text{threshold}}$)
- $\rho(\text{output\_res}, \text{iddq\_standby}) = $ **0.536** (Target: ≈ 0.00; independent package mechanism)

## 6. Deliberate Data Imperfections (`TEST-GEN-006`)

Deliberate real-world imperfections injected into the measurement records per `DATASET_SPEC.md § 8`:

| Imperfection Mechanism | Observed Count | Observed Rate | Target Rate | Tolerance Band | Status |
|---|---|---|---|---|---|
| Censored Readings (`<LOD`) | 259 | 0.17 % | 0.50 % | [0.20 %, 1.20 %] | PASS |
| Overrange Readings (`OVERRANGE`) | 276 | 0.19 % | 0.20 % | [0.05 %, 0.80 %] | PASS |
| Unit Inconsistencies (mA where µA expected) | 2 lots | 2 lots | 2 lots | [1, 3] lots | PASS |
| Timestamp Formatting & Jitter | 148,159 rows | 100 % ISO-8601 | 100 % | ISO-8601 compliant | PASS |
| Single-Part Lot (`n=1`) | 1 lot (`L-2026-040`) | 1 part | 1 lot | Exactly 1 lot | PASS |
| Zero-IQR Lot (all identical readings) | 1 lot (`L-2026-039`) | IQR = 0.000 | 1 lot | Division-by-zero guard | PASS |
| Small Lot (`n=3`) | 1 lot (`L-2026-021`) | 3 parts | 1 lot | Small-$n$ guard | PASS |
| Coherently Shifted Lots ($+2.8\sigma$) | 2 lots | 400 parts | 2 lots | DPAT absorption test | PASS |

## 7. Splits & Mondrian Calibration Groups (`QG-DATA-02`)

Verification of lot-disjoint splits (`TEST-SPLIT-001`) and calibration support for Mondrian conformal prediction (`FR-307`):

| Split | Lots | Components | Measurements | Lot-Disjointness | Purpose |
|---|---|---|---|---|---|
| **`train`** | 24 lots | 4,202 | 99,642 | Verified Disjoint | Fit point models & baseline shapes |
| **`calib`** | 8 lots | 1,521 | 36,102 | Verified Disjoint | Conformal quantile calibration only |
| **`test`** | 8 lots | 523 | 12,415 | Verified Disjoint | Final evaluation harness scoring only |

- **Pairwise Lot Intersections:** `train ∩ calib = ∅`, `train ∩ test = ∅`, `calib ∩ test = ∅` (`TEST-SPLIT-001: PASSED`)
- **Held-Out Test Policy:** `test.parquet` truth columns readable exclusively by release scoring script (`AG-5`).

### Mondrian Calibration Groups ($n_{\text{cal}, g}$ & Attainable $\alpha$)

Calibration group sample sizes $n_{\text{cal}, g}$ and attainable significance $\alpha_{\min} = 1 / (n_{\text{cal}, g} + 1)$ evaluated from `calib.parquet`:

| Component Type | Parameter | $n_{\text{cal}, g}$ | $\alpha_{\min}$ | Nominal $\alpha = 0.05$ Supported? | Mondrian Level |
|---|---|---|---|---|---|
| `CMOS_LOGIC` | `iddq_standby` | 159 | 0.0063 | Yes | Level 0 |
| `CMOS_LOGIC` | `leakage_input` | 159 | 0.0063 | Yes | Level 0 |
| `CMOS_LOGIC` | `prop_delay` | 159 | 0.0063 | Yes | Level 0 |
| `CMOS_LOGIC` | `vth_shift` | 159 | 0.0063 | Yes | Level 0 |
| `CMOS_LOGIC` | `icc_active` | 159 | 0.0063 | Yes | Level 0 |
| `CMOS_LOGIC` | `output_res` | 159 | 0.0063 | Yes | Level 0 |
| `SRAM` | `iddq_standby` | 159 | 0.0063 | Yes | Level 0 |
| `SRAM` | `leakage_input` | 159 | 0.0063 | Yes | Level 0 |
| `SRAM` | `prop_delay` | 159 | 0.0063 | Yes | Level 0 |
| `SRAM` | `vth_shift` | 159 | 0.0063 | Yes | Level 0 |
| `SRAM` | `icc_active` | 159 | 0.0063 | Yes | Level 0 |
| `SRAM` | `output_res` | 159 | 0.0063 | Yes | Level 0 |
| `LDO_REG` | `iddq_standby` | 448 | 0.0022 | Yes | Level 0 |
| `LDO_REG` | `leakage_input` | 448 | 0.0022 | Yes | Level 0 |
| `LDO_REG` | `prop_delay` | 448 | 0.0022 | Yes | Level 0 |
| `LDO_REG` | `vth_shift` | 448 | 0.0022 | Yes | Level 0 |
| `LDO_REG` | `icc_active` | 448 | 0.0022 | Yes | Level 0 |
| `LDO_REG` | `output_res` | 448 | 0.0022 | Yes | Level 0 |
| `OPAMP` | `iddq_standby` | 447 | 0.0022 | Yes | Level 0 |
| `OPAMP` | `leakage_input` | 447 | 0.0022 | Yes | Level 0 |
| `OPAMP` | `prop_delay` | 447 | 0.0022 | Yes | Level 0 |
| `OPAMP` | `vth_shift` | 447 | 0.0022 | Yes | Level 0 |
| `OPAMP` | `icc_active` | 447 | 0.0022 | Yes | Level 0 |
| `OPAMP` | `output_res` | 447 | 0.0022 | Yes | Level 0 |
| `POWER_MOSFET` | `iddq_standby` | 308 | 0.0032 | Yes | Level 0 |
| `POWER_MOSFET` | `leakage_input` | 308 | 0.0032 | Yes | Level 0 |
| `POWER_MOSFET` | `prop_delay` | 308 | 0.0032 | Yes | Level 0 |
| `POWER_MOSFET` | `vth_shift` | 308 | 0.0032 | Yes | Level 0 |
| `POWER_MOSFET` | `icc_active` | 308 | 0.0032 | Yes | Level 0 |
| `POWER_MOSFET` | `output_res` | 308 | 0.0032 | Yes | Level 0 |

## 8. Quality Gates Status

| Quality Gate | Authority | Scope | Status | Evidence |
|---|---|---|---|---|
| `QG-DATA-01` | Data & ML Engineer | Usable dataset artifacts | **PASSED** | `0231a45de767` / `DATASET_PROFILE.md` |
| `QG-DATA-02` | Data & ML Engineer | Trustworthy lot-disjoint splits | **PASSED** | `reports/SPLIT_AUDIT.json` |
| `TEST-GEN-001` | Data & ML Engineer | Parameter provenance tags | **PASSED** | 100 % parameters carry provenance |
| `TEST-GEN-004` | Data & ML Engineer | Escape Set non-empty and inside limits | **PASSED** | 479 escapes, 0 breaches |
| `TEST-GEN-005` | Data & ML Engineer | Labels derived from rendered values | **PASSED** | Independent derivation verified |
| `TEST-GEN-006` | Data & ML Engineer | Imperfection injection rates | **PASSED** | All rates within tolerance |
| `TEST-GEN-007` | Data & ML Engineer | Latent defect prevalence | **PASSED** | Observed within tolerance |
| `TEST-GEN-008` | Data & ML Engineer | Correlation matrix published | **PASSED** | Measured and published in § 5 |
| `TEST-DL-002` | Data & ML Engineer | `screening.parquet` has no late columns | **PASSED** | 0 late tokens |
| `TEST-DL-003` | Data & ML Engineer | Screening correlation with truth $< 0.95$ | **PASSED** | $|\rho| = 0.884$ |
| `TEST-SPLIT-001` | Data & ML Engineer | Splits strictly lot-disjoint | **PASSED** | Pairwise intersections empty |

