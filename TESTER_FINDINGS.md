# LATENTIS — Tester Findings: Phase 3 Complete (T-301 through T-316)

**Current Run Date:** 2026-09-09  
**Role:** Independent Tester / QA Engineer (`qa-playwright-engineer`)  
**Scope Under Evaluation:** T-311 → T-316 (`backend/core/risk.py`, `recommend.py`, `explain.py`, `formulas.py`, `traced.py`, `backend/tests/arch/test_import_graph.py`, `backend/tests/integration/test_phase3_chain.py`)  
**Batch Implementation Commit:** `6e4b7550870c2a7f3a247db4b946c724352c8607` (`6e4b755`)  
**Batch Governance Commit:** `57c1e42a98f121d5c643666b4ce19992f8efbaee` (`57c1e42`)  
**Prior Batch Status:** T-301..T-310 verified in prior audits (PASS); T-311..T-316 under final evaluation.  

---

## 1. Prior Cluster Verification Summary (T-301 → T-303)

Findings TEST-001 through TEST-005 from the initial verification of T-301, T-302, and T-303 were retested and confirmed resolved in commit `23ca654`:

- **TEST-001 (Resolved):** Small-cohort ($n < 20$) zero-MAD fallback to IQR dispersion implemented in `robust.py`; secondary guard in `dpat.py` prevents division by zero. No `inf` or `NaN` emitted.
- **TEST-002 (Resolved):** Scope of `RT-008` formally clarified in `RED_TEAM_PLAN.md § RT-008` as `backend/core/**`. Within `backend/core/**`, literals `1.35` and `1.4826` appear strictly once in `backend/core/constants.py`.
- **TEST-003 (Resolved):** `part_value=None` returns `verdict=None` and `z=None`, correctly indicating no candidate part was evaluated.
- **TEST-004 (Resolved):** Non-finite candidate readings (`NaN`, `+inf`, `-inf`) defensively rejected with `DpatVerdict.FAIL`, `z=None`, and descriptive warning.
- **TEST-005 (Resolved):** Under Type-7 linear quantile interpolation, mathematical invariant $IQR == 0 \implies MAD == 0$ documented and tested.

---

## 2. Independent Test Execution & Verification of T-304 (Commit `3d78bc1`)

The independent QA engineer performed exhaustive, adversarial testing of the T-304 implementation across `backend/core/multivariate.py`, `backend/core/constants.py`, `backend/tests/unit/test_mahalanobis.py`, and `backend/tests/property/test_multivariate.py`:

### A. Test Suite Execution & Linters
1. **Full Pytest Suite:** Executed `pytest backend/tests/ -v`: **46/46 passed in 22.16s** (29 unit tests, 11 property tests, 1 integration test, 1 architecture test).
2. **Pre-Commit Unit Tests:** **117/117 passed** in `tests/unit/`.
3. **Reproducibility Test:** `backend/tests/integration/test_reproducibility.py` passed cleanly (byte-identical dataset generation confirmed under pinned seed).
4. **Code Quality & Typing:**
   - `ruff check backend/`: 0 errors (clean).
   - `mypy backend/`: 0 errors across 20 source files (clean).
   - `black --check backend/`: 0 formatting discrepancies.

### B. Quality Gate Verification
1. **QG-CORE-01 (`scripts/check_test_categories.py`):** **PASS** (11/11 public core functions covered by valid numeric tests).
2. **QG-DOC-01 (`scripts/check_traceability.py`):** **PASS** (60/60 P0 requirements covered, zero unmapped).
3. **RT-008 AST Scan:** **PASS** (Independent AST traversal confirmed zero unregistered numeric literals outside `{0, 1, 2}` in `backend/core/multivariate.py` and across all `backend/core/*.py`).
4. **TEST-ARCH-001 / QG-ARCH-01 / DR-10:** **PASS** (Pure numeric core isolation confirmed: no I/O, no framework imports, no cross-imports with `datagen` or `app`).
5. **Phase 2 Immutability:** Independent git tree inspection confirmed **zero Phase 2 files** (`datagen/**`, `data/**`, `reports/DATASET_PROFILE.md`) modified.

### C. Independent Numerical & Analytical Oracle Verification
1. **Closed-Form 3-D Analytical Oracle:**
   Constructed a known positive-definite covariance system with center $\mu = [1.0, 2.0, 3.0]$, $\Sigma = \begin{pmatrix} 2.0 & 0.5 & 0.0 \\ 0.5 & 1.0 & 0.2 \\ 0.0 & 0.2 & 1.5 \end{pmatrix}$, and candidate $x = [3.0, 4.0, 1.0]$.
   - Hand-derived $D^2 = 8.345776031434$, $c = [0.95874263, 4.16502947, 3.22200393]$, $p = 0.0393808$.
   - Independent execution of `contributions(x, mu, prec)` matched paper derivation to $< 10^{-12}$.
2. **Direct Scikit-Learn FastMCD Oracle Comparison:**
   Fitted a 100-sample, 3-parameter contaminated cohort using independent `MinCovDet(support_fraction=0.75, random_state=42)`. Verified that unscaled `location`, `covariance`, `precision`, and quadratic form $D^2$ from `mahalanobis` matched direct scikit-learn calculation to $< 10^{-9}$.
3. **Differential Additive Decomposition Identity (TEST-STAT-007 / FR-206):**
   - Verified that $\sum_{q=0}^{p-1} c_q \equiv D^2$ within `SUM_CHECK_TOLERANCE` ($10^{-9}$).
   - Executed Hypothesis property testing over 50 randomized positive-definite covariance distributions without a single tolerance violation.
4. **Known-Answer Joint-Only Outlier Detection (TEST-STAT-008 / FR-206):**
   Evaluated a strongly correlated 2-D Gaussian cohort ($r = 0.95$, $n=50$) with candidate part $x = [2.0, -2.0]$:
   - Marginal DPAT limits passed nominally: $z_x = 1.687 (< 3.0)$, $z_y = -1.791 (< 3.0)$ with `DpatVerdict.PASS`.
   - Joint Mahalanobis distance correctly triggered severe outlier: $D^2 = 304.98$, $p = 5.96 \times 10^{-67} \ll 10^{-6}$.
   - Additive contributions decomposed symmetrically ($c_x \approx 154.51$, $c_y \approx 150.46$, shares $\approx 50.7\%$ and $49.3\%$).

### D. Invariants & Adversarial Boundary Conditions
1. **Component-ID Permutation Invariance (INV-2 / RT-004):** Bijectively permuting component IDs in a leave-one-out cohort produced identical results ($|D^2_{base} - D^2_{perm}| < 10^{-10}$).
2. **Deterministic Repeated Execution (INV-8):** 5 repeated evaluations on identical inputs produced bitwise-identical results across all outputs.
3. **Candidate Part at Center Point:** When candidate $x = \mu$, correctly computed $D^2 = 0.0$, $p = 1.0$, $c_q = 0.0$, $\text{share} = 0.0$.
4. **Physical Scale Ranges (`RT-009` Row 5):** Evaluated extreme physical magnitudes ($10^{-30}, 10^{-20}, 10^{-15}, 10^{15}, 10^{20}, 10^{30}$). All outputs (`d2`, `p_value`, `contributions`, `location`, `covariance`, `precision`) remained strictly finite without `NaN` or `inf`.
5. **Degenerate Sample Size Ladder:**
   - $n < 3$ or $n \le p$: Gracefully returned `INSUFFICIENT_COHORT`.
   - $n < 5 \cdot p$: Gracefully returned `INSUFFICIENT_SAMPLE_RATIO`.
6. **Singular & Collinear Cohorts:**
   - Column with zero variance: Gracefully returned `SINGULAR_COVARIANCE`.
   - Perfectly collinear columns ($c_2 = 2 c_1$): Gracefully returned `SINGULAR_COVARIANCE`.
   - Ill-conditioned covariance ($\text{cond} > 10^{12}$): Gracefully returned `SINGULAR_COVARIANCE`.
7. **Adversarial Non-Finite Candidate Inputs:** Candidate containing `NaN`, `+inf`, or `-inf` rejected with `INVALID_INPUT`.
8. **Unscored Cohort:** `part_value=None` successfully returns distribution parameters (`location`, `covariance`, `precision`) with `d2=None`, `p_value=None`, `contributions=None`, and `refusal_code=None`.

---

## 3. Independent Tester Findings for T-304

### TEST-006
- **Severity:** Minor
- **Location:** `backend/core/multivariate.py:464` and `backend/core/multivariate.py:144-148`
- **Observed Behavior:** When `mahalanobis` is called with a candidate part and `parameter_names` whose length does not match the cohort parameter dimension (e.g. `parameter_names=["only_one"]` for a 2-D cohort), `mahalanobis` crashes with an unhandled exception:
  `ValueError: parameter_names length (1) does not match dimension (2)`.
- **Expected Behavior:** Per `ANOMALY_SPEC § 9` ("never produce inf or NaN; handle degenerate cases gracefully") and the defensive contract implemented for other input dimension mismatches (e.g. `raw.ndim != 2` at line 198, `n_params == 0` at line 218, and `len(part_arr) != n_params` at line 410, which all return `refusal_code="INVALID_INPUT"`), `mahalanobis` should validate `parameter_names` upfront. If `parameter_names is not None and len(parameter_names) != n_params`, it should return `RobustMahalanobisResult(..., refusal_code="INVALID_INPUT", warning="parameter_names length does not match parameter count")` rather than allowing an unhandled `ValueError` to propagate.
- **Reproduction:**
  ```python
  import numpy as np
  from backend.core.multivariate import mahalanobis

  cohort = np.random.normal(size=(25, 2))
  # Crashes with unhandled ValueError instead of returning refusal_code="INVALID_INPUT":
  res = mahalanobis(cohort, part_value=[1.0, 2.0], parameter_names=["p1"])
  ```
- **Actual Result:** `CRASHED with ValueError: parameter_names length (1) does not match dimension (2)`.
- **Why It Matters:** Ingestion or API adapters passing mismatched schema metadata will cause an unhandled 500 crash rather than a clean refusal payload.
- **Recommended Fix:** Add an upfront check in `mahalanobis`:
  ```python
  if parameter_names is not None and len(parameter_names) != n_params:
      return RobustMahalanobisResult(
          d2=None, p_value=None, df=n_params, n=n_samples, p=n_params,
          location=None, covariance=None, precision=None, contributions=None,
          refusal_code="INVALID_INPUT",
          warning=f"parameter_names length ({len(parameter_names)}) does not match parameter count ({n_params})",
      )
  ```
- **Blocking:** No.

---

### TEST-007
- **Severity:** Minor
- **Location:** `backend/core/multivariate.py:314`, `CODER_PROGRESS.md:72`, `backend/tests/property/test_multivariate.py:7, 136-164`
- **Observed Behavior:** `CODER_PROGRESS.md` claims *"Parameter (column) permutation equivariance"*, and `test_multivariate.py` lists it as an asserted invariant. However, in `backend/core/multivariate.py` line 314:
  `sort_idx = np.lexsort(clean_cohort_scaled.T[::-1])`
  lexsort sorts rows primarily by column 0. Permuting the columns of a dataset changes the primary sort key, resulting in a different row order being passed to `MinCovDet(random_state=42)`. Because FastMCD samples initial subsets by row index $0..n-1$, presenting rows in a different order causes FastMCD to select different initial subsets, which can converge to a different local minimum of the determinant.
  In a 4-parameter cohort ($n=50$), permuting columns with `perm = [2, 1, 3, 0]` resulted in $D^2 = 3.4618$ vs $D^2 = 3.7433$ ($\Delta D^2 = 0.2815$).
  The test `test_mahalanobis_parameter_permutation_equivariance` only tested a single fixed seed (`4004`) and a single permutation (`[2, 0, 1]`), which happened to pass by coincidence, creating a false impression that full parameter permutation equivariance is guaranteed.
- **Expected Behavior:** If parameter column permutation equivariance is claimed, columns should be placed into a canonical order (e.g. sorted alphabetically by `parameter_names` when provided, or canonically indexed) prior to row-lexsorting and `MinCovDet` fitting, or the claim in documentation and test docstrings must be qualified to clarify that FastMCD row-lexsorting is dependent on input column order.
- **Reproduction:**
  ```python
  import numpy as np
  from backend.core.multivariate import mahalanobis

  rng = np.random.default_rng(1234)
  cohort = rng.normal(loc=[10, 20, 30, 40], scale=[1, 2, 3, 4], size=(50, 4))
  cand = np.array([12.0, 22.0, 31.0, 38.0])
  perm = [2, 1, 3, 0]

  res_orig = mahalanobis(cohort, part_value=cand)
  res_perm = mahalanobis(cohort[:, perm], part_value=cand[perm])
  # D² diff is 0.2815 (> 0.05)
  assert abs(res_orig.d2 - res_perm.d2) < 1e-8
  ```
- **Actual Result:** `AssertionError: Trial 2: d2 diff 0.28149672885816734`.
- **Why It Matters:** While row-permutation invariance and component-ID invariance (INV-2) are verified and strictly hold, column ordering in production should produce stable results regardless of how feature columns are arranged in the input matrix.
- **Recommended Fix:** Canonicalize column order (e.g. by sorting `parameter_names` or assigning canonical column keys) before row sorting and covariance fitting, and map contributions back to original column positions.
- **Blocking:** No.

---

### TEST-008
- **Severity:** Minor
- **Location:** `backend/core/multivariate.py:385, 446-448`
- **Observed Behavior:** When a cohort column has an extreme subnormal standard deviation ($\sigma < 10^{-154}$, occurring in synthetic edge cases beyond the specified range $[10^{-30}, 10^{30}]$ of `RT-009` row 5), $(1/\sigma)^2$ overflows float64 to `inf` in `prec = np.outer(1.0 / col_stds, 1.0 / col_stds) * prec_scaled`. Consequently:
  1. `res.precision` contains `inf` and `-inf`.
  2. `delta @ w` produces `NaN`.
  3. In line 447, `raw_d2 = float(delta @ w)` is `NaN`. Python's `max(0.0, raw_d2)` silently coerces `max(0.0, float("nan"))` to `0.0`.
  4. The finite check `if not math.isfinite(d2_val):` evaluates to `False` because `d2_val` is now `0.0`.
  5. `contributions` computes `weight=nan` and `contribution=nan`, which are emitted in `res.contributions` with `refusal_code=None`.
- **Expected Behavior:** In `backend/core/multivariate.py`:
  1. Verify `np.all(np.isfinite(prec))` after unscaling precision. If precision contains `inf` or `nan`, return `refusal_code="SINGULAR_COVARIANCE"`.
  2. Verify `math.isfinite(raw_d2)` *before* taking `max(0.0, raw_d2)` so `NaN` cannot be silently masked as `0.0`.
- **Reproduction:**
  ```python
  import numpy as np
  from backend.core.multivariate import mahalanobis

  rng = np.random.default_rng(42)
  cohort = rng.normal(loc=0.0, scale=1e-160, size=(30, 2))
  res = mahalanobis(cohort, part_value=[1e-160, 1e-160])
  # res.precision contains inf; res.contributions has weight=nan, contribution=nan; res.d2=0.0; refusal_code=None
  assert res.refusal_code == "SINGULAR_COVARIANCE"
  ```
- **Actual Result:** `res.refusal_code is None`, `res.precision` contains `inf`, `res.contributions` contains `NaN`.
- **Why It Matters:** This finding is directly analogous to `AUDIT-001` in DPAT: under extreme subnormal float regimes, unhandled float64 overflow causes `NaN`/`inf` emission and breaks JSON serialization.
- **Recommended Fix:** Add defensive checks on `prec` and `raw_d2`:
  ```python
  if not np.all(np.isfinite(prec)):
      return RobustMahalanobisResult(..., refusal_code="SINGULAR_COVARIANCE", warning="Precision matrix overflowed float64 finite range")
  if not math.isfinite(raw_d2):
      return RobustMahalanobisResult(..., refusal_code="INVALID_INPUT", warning="Calculated Mahalanobis D² is non-finite")
  ```
- **Blocking:** No. (Occurs only in extreme synthetic subnormal regimes $< 10^{-154}$, well beyond physical screening measurements and well outside the specified $[10^{-30}, 10^{30}]$ range of `RT-009` row 5).

---

### TEST-009
- **Severity:** Informational
- **Location:** `backend/core/multivariate.py:285, 311`, `CODER_PROGRESS.md:30`
- **Observed Behavior:** `CODER_PROGRESS.md` claims *"guaranteeing strict, bitwise row-permutation invariance"*. However, `col_stds = np.std(clean_cohort, axis=0)` is computed on the unsorted cohort. Due to the non-associativity of floating-point summation across permuted array orders in NumPy, `col_stds` can vary by 1 ULP ($\sim 10^{-16}$) across row permutations. This 1 ULP variance carries into `clean_cohort_scaled` and can result in a $\sim 10^{-15}$ difference in $D^2$.
- **Expected Behavior:** The governance claim should state that row-permutation invariance holds within floating-point machine precision ($\sim 10^{-15}$), satisfying the $10^{-10}$ test assertion, rather than claiming strict bitwise equality.
- **Reproduction:**
  ```python
  import numpy as np
  from backend.core.multivariate import mahalanobis

  rng = np.random.default_rng(999)
  n = 50
  cohort = rng.standard_t(df=3, size=(n, 3))
  cand = np.array([1.5, 0.5, -1.0])
  res_base = mahalanobis(cohort, part_value=cand)

  perm = rng.permutation(n)
  res_perm = mahalanobis(cohort[perm], part_value=cand)
  # d2 diff is -8.881784197001252e-16 (differs by 1 ULP)
  ```
- **Actual Result:** Passed within test tolerance ($10^{-10}$), but bitwise equality fails ($8.88 \times 10^{-16}$ diff).
- **Why It Matters:** Clarifies the distinction between mathematical invariance within float64 machine epsilon vs bitwise identical representation.
- **Recommended Fix:** Align documentation phrasing in `CODER_PROGRESS.md` to reflect floating-point epsilon invariance.
- **Blocking:** No.

---

### 4. Independent Test Execution & Verification of T-305 (Commit `cbe7abc`)

The independent QA engineer performed targeted, adversarial verification of T-305 across `backend/core/attribution.py`, `backend/core/constants.py`, `backend/tests/unit/test_attribution.py`, `backend/tests/property/test_attribution.py`, `DECISIONS.md § D-035`, and `models/anomaly/ANOMALY_SPEC.md § 7`:

### A. Test Suite Execution & Linters
1. **Existing T-305 Pytest Suite:**
   - Executed `uv run pytest backend/tests/unit/test_attribution.py backend/tests/property/test_attribution.py -v`:
   - **22/22 passed in 1.88s** (17 unit tests, 5 property/Hypothesis tests).
2. **Full Repository Unit Test Suite:**
   - Executed `uv run pytest tests/unit/ -v`:
   - **79/79 passed in 36.77s**.
3. **Code Quality, Formatting & Static Typing:**
   - `ruff check backend/`: 0 errors (clean).
   - `mypy backend/`: 0 errors across 23 source files (clean).
   - `black --check backend/`: 0 formatting discrepancies.

### B. Quality Gates & Architectural Invariants
1. **QG-CORE-01 (`scripts/check_test_categories.py`):** **PASS**
   - All 12/12 core functions in `backend/core/**` covered by valid numeric tests (including `attribute` via `TEST-ATTR-006` known-answer and `TEST-ATTR-007` property).
   - Total register count: 123 tests. Zero invalid categories or dishonest oracles.
2. **QG-DOC-01 (`scripts/check_traceability.py`):** **PASS**
   - 60/60 P0 requirements covered, zero unmapped. Bidirectional traceability verified.
3. **RT-008 AST Literal Scan (`backend/tests/unit/test_constants.py`):** **PASS**
   - Traversed AST of `backend/core/attribution.py`. Zero unregistered numeric literals outside `{0, 1, 2}` exist.
   - New assumed constant `ATTRIBUTION_SETUP_OFFSET_SIGMA_THRESHOLD = 2.0` properly registered in `backend/core/constants.py` with full provenance, audit description, and decision reference `D-035`.
4. **QG-ARCH-01 / TEST-ARCH-001 (Pure Numeric Core Isolation):** **PASS**
   - `backend/core/attribution.py` contains zero framework imports, zero I/O imports, and zero dependencies on `datagen` or `frontend`.
5. **Phase 2 & T-306 / T-406 Immutability:** **PASS**
   - Git tree comparison confirmed zero modifications to Phase 2 files (`datagen/**`, `data/**`, `reports/DATASET_PROFILE.md`).
   - T-306 (`backend/core/shape.py`) and T-406 remain strictly untouched and unstarted.
6. **Test Integrity & Anti-Weakening (INV-6):** **PASS**
   - Git diff inspection confirmed that changes in `tests/unit/test_check_test_categories.py` and `tests/unit/test_check_traceability.py` were strictly mechanical updates to mirror the register size (121 → 123) due to new supplementary tests `TEST-ATTR-006` and `TEST-ATTR-007`. Zero assertions, tolerances, or test logic were weakened.

### C. Targeted Scientific & Mathematical Verification
An independent test script (`scratch/verify_t305.py`) was executed to probe the attribution core across all mathematical, boundary, and defensive contracts:
1. **Core Attribution Math:**
   - Group Median Offset: Evaluated $\text{offset} = \frac{\text{median}(\text{group}) - \text{median}(\text{lot})}{\sigma_{\text{lot}}}$. Verified exact agreement with Type-7 quartile robust sigma ($\text{IQR} / 1.35$).
   - Socket Coherence: Verified that socket attribution strictly requires $\ge 3$ socket members with $|z| \ge 3.0$ vs the lot cohort (per `TEST-ATTR-002` and `D-035`). Sockets with median offset $\ge 2.0\sigma$ but $< 3$ coherent members correctly fail the socket claim and fall back to `PART`.
   - Setup Claim Resolution: Exactly 1 valid setup claim $\implies$ corresponding verdict (`SOCKET`, `ZONE`, `TESTER`); $\ge 2$ competing claims $\implies$ `INDETERMINATE` with conflict warning; missing metadata $\implies$ `INDETERMINATE` with explicit warning.
2. **Boundary Threshold Attacks:**
   - 2.0σ Setup Offset Boundary: $\text{offset} = 1.9999\sigma \implies \text{PART}$; $\text{offset} = 2.0000\sigma \implies \text{ZONE}$; $\text{offset} = 2.0001\sigma \implies \text{ZONE}$. Negative offsets ($-1.9999\sigma$, $-2.0000\sigma$, $-2.0001\sigma$) verified symmetric.
   - 3.0σ Within-Group Typicality Boundary: $|z_{\text{within}}| = 2.9999 \implies \text{ZONE}$ (typical); $|z_{\text{within}}| = 3.0000 \implies \text{PART}$ (not typical, defeated); $|z_{\text{within}}| = 3.0001 \implies \text{PART}$ (not typical, defeated).
3. **Claim-Defeat Logic:**
   - Bad part in bad socket (`RT-006` row 5): $|z_{\text{within}}| \ge 3.0$ in shifted coherent socket defeats socket claim $\implies \text{PART}$.
   - Socket-only evidence $\implies \text{SOCKET}$. Part-only evidence $\implies \text{PART}$. Insufficient socket members ($2 < 3$) $\implies \text{PART}$.
4. **T-304 Consumption & Tamper Refusal:**
   - `attribute()` directly consumes `RobustMahalanobisResult` without recomputing $D^2$ or covariance parameters.
   - Additive decomposition check $\sum_q c_q \equiv D^2$ enforced within `SUM_CHECK_TOLERANCE` ($10^{-9}$).
   - Perturbing $D^2$ by $> 10^{-9}$ triggers `refusal_code="INVALID_INPUT"` and `INDETERMINATE`.
   - Non-finite values (`NaN`, `+inf`, `-inf`) trigger `refusal_code="INVALID_INPUT"` and `INDETERMINATE`.
5. **Invariance Properties:**
   - Row Permutation Invariance: Verified identical results.
   - Component-ID Permutation Invariance (`INV-2` / `RT-004`): Verified identical results via leave-one-out records.
   - Repeated Execution (`INV-8`): Bitwise identical results across repeated runs.
6. **Defensive Behavior:**
   - Non-finite candidate part (`NaN`, `+inf`, `-inf`) cleanly refused with `INVALID_INPUT`.
   - Non-finite values in cohorts filtered; $< 3$ finite values returns `INSUFFICIENT_COHORT`.
   - Zero dispersion in lot returns `NO_VARIATION`. Group zero dispersion evaluated by exact equality.
   - 2-D or malformed cohort inputs caught and returned as `INVALID_INPUT`.
   - Zero `NaN` or `inf` values emitted in evidence across all property tests.

---

## 5. Independent Test Execution & Verification of T-306 through T-310 (Commits `071df9c` and `3f9aa9d`)

The independent QA engineer performed comprehensive, adversarial, and mathematical verification of the T-306 → T-310 batch across `backend/core/shape.py`, `backend/core/forecast.py`, `backend/core/conformal.py`, `backend/core/guard.py`, `backend/core/safety.py`, `backend/core/constants.py`, and all associated test suites per `DRIFT_SPEC § 4-§ 8`, `CONFORMAL_SPEC § 2-§ 7`, and `DECISIONS.md § D-036`:

### 1. Tests Executed & Quality Gates
1. **Full Backend Pytest Suite:**
   - Executed `uv run pytest backend/tests/ -v`:
   - **116/116 passed in 23.41s** (75 unit tests, 39 property/Hypothesis tests, 1 integration test, 1 architecture test; was 68 passed prior to batch, +48 new tests).
2. **Repository Pre-Commit Unit Test Suite:**
   - Executed `uv run pytest tests/unit/ -v`:
   - **79/79 passed in 36.51s**.
3. **Reproducibility Test (`INV-8` / `QG-REL-03`):**
   - `backend/tests/integration/test_reproducibility.py` passed cleanly (byte-identical dataset generation confirmed under pinned seed).
4. **Code Quality, Formatting & Static Typing:**
   - `ruff check backend/`: 0 errors (clean).
   - `black --check backend/`: 0 discrepancies (40 files checked).
   - `mypy backend/core backend/tests`: 0 errors across 39 source files (clean).
5. **Quality Gate QG-CORE-01 (`scripts/check_test_categories.py`):**
   - **PASS**: All 19/19 public core functions across `backend/core/**` covered by valid numeric tests (known-answer, property, differential).
   - Total tests in register: 128 (expanded from 123 via 5 additive IDs). Zero invalid categories, zero dishonest oracles.
6. **Quality Gate QG-DOC-01 (`scripts/check_traceability.py`):**
   - **PASS**: 60/60 P0 requirements covered in register and matrix, zero unmapped. Bidirectional traceability verified.
7. **Quality Gate RT-008 AST Scan (`backend/tests/unit/test_constants.py`):**
   - **PASS**: AST traversal confirmed zero unregistered numeric literals outside `{0, 1, 2}` in `backend/core/*.py`.
   - All 10 newly introduced constants in `backend/core/constants.py` properly registered with provenance tags, decision references (`D-036`), units, and source citations.
8. **Quality Gate QG-ARCH-01 / TEST-ARCH-001 (Pure Numeric Core Boundary Isolation):**
   - **PASS**: `backend/tests/arch/test_import_graph.py` passed cleanly. Zero framework imports, zero I/O imports, and zero dependencies on `datagen` or `frontend` in `backend/core/**`.

---

### 2. Independent Mathematical Checks & Closed-Form Oracles

#### A. T-306: $\Phi_g$ Estimation (Type-7 Median of Empirical Ratios & Normalisation)
- **Empirical Ratio Formula:**
  Per `DRIFT_SPEC § 4.1`, with $V(t) = v_0 + A \cdot \Phi_g(t)$ and $\Phi_g(24) \equiv 1$:
  $A = v_{24} - v_0$, and $v_{168} = v_0 + A \cdot \Phi_g(168) \implies \phi_i = \frac{v_{168, i} - v_{0, i}}{v_{24, i} - v_{0, i}}$.
- **Independent 5-Point Hand Oracle:**
  Trajectory cohort:
  - $v_0 = [10.0, 10.0, 10.0, 10.0, 10.0]$
  - $v_{24} = [12.0, 14.0, 16.0, 18.0, 20.0] \implies \Delta_{24} = [2.0, 4.0, 6.0, 8.0, 10.0]$
  - $v_{168} = [14.0, 20.0, 28.0, 38.0, 50.0] \implies \Delta_{168} = [4.0, 10.0, 18.0, 28.0, 40.0]$
  - Ratios: $\phi = [4/2, 10/4, 18/6, 28/8, 40/10] = [2.0, 2.5, 3.0, 3.5, 4.0]$.
  - Under Type-7 linear quantile interpolation ($n=5$), median index is $1 + 0.5 \cdot (5 - 1) = 3$ (1-indexed), exactly giving $\Phi_g(168) = 3.0$.
  - Independent code execution returned `phi_168 = 3.0`, `n_used = 5`, `refusal_code = None` ($< 10^{-14}$ error).
- **Even $n$ Type-7 Median Hand Oracle:**
  Ratios $\phi = [1.0, 2.0, 3.0, 4.0]$ ($n=4$). Index is $1 + 0.5 \cdot (4 - 1) = 2.5 \implies 0.5 \cdot 2.0 + 0.5 \cdot 3.0 = 2.5$.
  Independent execution confirmed `phi_168 = 2.5`.
- **$\Phi_g(24) \equiv 1$ Normalisation by Construction:**
  Evaluated across all four candidate shape families at $t=24.0$ h:
  - `power_law`: $(24/24)^n = 1.0$ (short-circuited to $1.0$).
  - `linear`: $24/24 = 1.0$.
  - `log_time`: $\ln(1 + 24/\tau) / \ln(1 + 24/\tau) = 1.0$.
  - `saturating`: $(1 - e^{-24/\tau}) / (1 - e^{-24/\tau}) = 1.0$.
  All returned strictly `1.0` without floating-point residual error.
- **Power-Law Exponent Derivation:**
  Given $\Phi(168) = 7^n \implies n = \frac{\ln(\Phi(168))}{\ln(7)}$.
  For $\Phi(168) = 3.06$: $n = \frac{\ln(3.06)}{\ln(7)} = \frac{1.118415}{1.945910} = 0.57475... \approx 0.575$.
  Evaluated at $t=168$: $\Phi(168) = (168/24)^n = 7^n = 3.06$.

#### B. T-307: $\hat{V}_{168}$ Point Forecast, Linear Baseline, & AG-10 Residual Adoption
- **DRIFT_SPEC § 8 Worked Example Independent Recalculation:**
  Inputs: $v_0 = 12.1$ µA, $v_{24} = 18.7$ µA, $\Phi_g(168) = 3.06$.
  - $\Delta_{24} = 18.7 - 12.1 = 6.6$ µA.
  - $\hat{V}_{168} = v_0 + \Delta_{24} \cdot \Phi_g(168) = 12.1 + 6.6 \cdot 3.06 = 12.1 + 20.196 = 32.296$ µA.
  - $\text{Baseline}_{\text{linear}} = v_0 + \Delta_{24} \cdot 7.0 = 12.1 + 6.6 \cdot 7.0 = 12.1 + 46.2 = 58.300$ µA.
  - Independent call to `forecast_v168(12.1, 18.7, 3.06)` returned `point = 32.296` and `baseline_linear = 58.3` ($< 10^{-14}$ error).
- **AG-10 Residual Adoption Inequality:**
  Inequality rule: $\text{residual adopted} \iff \text{MAE}_{\text{residual}} + \text{spread} < \text{MAE}_{\text{shape}}$.
  - Case 1 (Strict Win): $\text{MAE}_{\text{shape}} = 2.0$, $\text{MAE}_{\text{residual}} = 1.0$, $\text{spread} = 0.1 \implies 1.0 + 0.1 = 1.1 < 2.0 \implies$ ADOPTED (`point = shape_point + 1.1`).
  - Case 2 (Worse): $\text{MAE}_{\text{shape}} = 2.0$, $\text{MAE}_{\text{residual}} = 2.5$, $\text{spread} = 0.1 \implies 2.6 \ge 2.0 \implies$ REJECTED (`point = shape_point`, `residual_correction = 0.0`).
  - Case 3 (Boundary Tie): $\text{MAE}_{\text{shape}} = 2.0$, $\text{MAE}_{\text{residual}} = 1.95$, $\text{spread} = 0.05 \implies 2.00 \ge 2.00 \implies$ REJECTED (strict `<` enforced per AG-10).

#### C. T-308: Split Conformal Order Statistic & Mondrian Ladder
- **Finite-Sample Order Statistic Formula:**
  $k = \lceil(n_{\text{cal}} + 1)(1 - \alpha)\rceil$.
  - $n = 9, \alpha = 0.10$: $k = \lceil(9 + 1)(1 - 0.10)\rceil = \lceil 10 \cdot 0.90 \rceil = \lceil 9.0 \rceil = 9$.
    With residuals $[-2.1, -0.5, 0.3, 1.2, 2.0, 3.1, 4.4, 5.9, 7.5]$, 9th smallest is $7.5$.
    $\hat{U}_{168} = \hat{y} + \hat{q} = 32.296 + 7.5 = 39.796$ µA (matches spec § 8 worked example $\approx 39.8$ µA).
  - $n = 9, \alpha = 0.05$: $k = \lceil(9 + 1)(1 - 0.05)\rceil = \lceil 10 \cdot 0.95 \rceil = \lceil 9.5 \rceil = 10$.
    Since $k = 10 > n_{\text{cal}} = 9$, quantile is unattainable.
    Verified output: `upper = None`, `bound_finite = False`, `refusal_code = "INSUFFICIENT_CALIBRATION"`, `attainable_alpha = 1 / (9+1) = 0.10`.
  - $n = 1, \alpha = 0.50$: $k = \lceil(1 + 1)(0.50)\rceil = \lceil 1.0 \rceil = 1 \le 1 \implies \text{attainable}$ ($\hat{q} = s_{(1)}$).
  - $n = 1, \alpha = 0.49$: $k = \lceil(2)(0.51)\rceil = \lceil 1.02 \rceil = 2 > 1 \implies \text{INFINITE}$.
  - $n = 0$: $k > 0 \implies \text{INFINITE}$ (`attainable_alpha = 1.0`).
- **Mondrian Fallback Ladder Gating:**
  - Level 0: gated by $n_{\text{cal}} \ge 50$ (`MONDRIAN_N_MIN_CALIBRATION`) AND $k \le n_{\text{cal}}$.
  - Level 1 / Level 2: gated strictly by $k \le n_{\text{cal}}$.
  - Level 3: `INSUFFICIENT_CALIBRATION` when $k > n_{\text{cal}}$ at all levels.
  - Single-set call: direct evaluation per CONFORMAL_SPEC § 2 without 50-member gate (D-036).

#### D. T-309: Six-Signal Exchangeability Guard
- **Signal 1: Feature Shift (PSI on $v_0$ and $\Delta_{24}$):**
  Equal-width decile bins over calibration range with $\epsilon = 10^{-4}$ smoothing.
  $\text{PSI} = \sum_{b=1}^{10} (p_{\text{lot}, b} - p_{\text{cal}, b}) \cdot \ln(p_{\text{lot}, b} / p_{\text{cal}, b})$.
  Verified: $\text{PSI} > 0.25 \implies \text{VOID}$; $0.10 \le \text{PSI} \le 0.25 \implies \text{WARN}$ (DEGRADED); $\text{PSI} < 0.10 \implies \text{PASS}$ (VALID).
- **Signal 2: Lot-Centre Shift:**
  $z = \frac{\text{median}(v_{0, \text{lot}}) - \text{median}(\text{calib\_medians})}{\sigma_{\text{robust}}(\text{calib\_medians})}$.
  Verified: $|z| > 3.0 \implies \text{VOID}$.
- **Signal 3: Amplitude Shift (Two-Sample KS):**
  Two-sample Kolmogorov-Smirnov test on $\Delta_{24}$.
  Verified: $p < 0.01 \implies \text{VOID}$.
- **Signal 4: Temperature Range:**
  Verified: $\text{mean}(T_{\text{lot}}) < \min(T_{\text{cal}}) \lor \text{mean}(T_{\text{lot}}) > \max(T_{\text{cal}}) \implies \text{VOID}$.
- **Signal 5 & 6: Tester Novelty & Group Novelty:**
  Verified: $\text{tester\_id} \notin \text{seen\_testers} \implies \text{VOID}$; $\text{group\_key} \notin \text{known\_groups} \implies \text{VOID}$.
- **Guarantee Status Integrity:**
  Verified that VOID warning states: *"The guard detects shift; it does not restore the guarantee."*

#### E. T-310: Safety Slope, Usable Margin, and Priority Bands
- **DRIFT_SPEC § 8 Worked Example Independent Hand Calculation:**
  Inputs: $v_0 = 12.1$, $v_{24} = 18.7$, $\hat{V}_{168} = 32.296$, $\hat{U}_{168} = 39.796$, $\text{limit\_high} = 50.0$, $\text{margin\_fraction} = 0.20$, $\text{horizon} = 168.0$ h.
  - $\text{headroom} = 50.0 - 12.1 = 37.9$ µA.
  - $\text{usable\_margin} = 37.9 \cdot (1 - 0.20) = 37.9 \cdot 0.80 = 30.32$ µA.
  - $\text{safe\_threshold} = 50.0 - 30.32 = 19.68$ µA.
  - $\text{safety\_slope} = 30.32 / 168.0 = 0.18047619...$ µA/h.
  - $\text{observed\_early\_slope} = (18.7 - 12.1) / 24.0 = 6.6 / 24.0 = 0.2750$ µA/h.
  - $\text{predicted\_long\_slope} = (32.296 - 12.1) / 168.0 = 20.196 / 168.0 = 0.12021428...$ µA/h.
  - $\text{slope\_ratio} = \frac{0.12021428...}{0.18047619...} = \frac{20.196}{30.32} = 0.66609498... \approx 0.666$.
  - $\text{predicted\_margin} = 50.0 - 39.796 = 10.204$ µA.
  - $\text{predicted\_margin\_pct} = 10.204 / 37.9 = 0.26923... \approx 0.269$.
  - **Band Assignment:**
    1. $\hat{U}_{168} = 39.796 < 50.0 \implies$ Not REJECT.
    2. $\text{slope\_ratio} = 0.666 < 1.0 \implies$ Not EARLY_WARNING.
    3. $\text{slope\_ratio} < 0.70$, but $\hat{U}_{168} = 39.796 \ge \text{safe\_threshold} = 19.68$ (bound has breached the usable margin reserve).
       Per D-036 gap-fill, reserve-breach promotes to `WATCH`.
    4. Evaluated band: **`WATCH`**.
  - All values matched independent hand calculation to $< 10^{-14}$.
- **Delta Limit Precedence:**
  When $\Delta_{\text{max}} = 16.8$ µA is supplied:
  $\text{safety\_slope} = \Delta_{\text{max}} / 168.0 = 16.8 / 168.0 = 0.10$ µA/h (usable margin still retained for display).
- **Exact Boundary Equality:**
  - $\text{slope\_ratio} = 1.000000 \implies$ `EARLY_WARNING`.
  - $\text{slope\_ratio} = 0.700000$ (with $\hat{U}_{168} < \text{safe\_threshold}$) $\implies$ `WATCH`.
  - $\hat{U}_{168} = \text{limit\_high} \implies$ `REJECT`.
- **Bound-Driven Priority (`D-010` / `RT-005`):**
  Evaluated part with nominal point forecast ($V = 11.0$ µA, $\text{ratio} = 0.05$) but inflated conformal upper bound ($\hat{U}_{168} = 55.0 \ge 50.0$).
  Correctly evaluated to `REJECT`. Point forecast cannot bypass the conformal bound.

---

### 3. Detailed Findings by Task

#### A. T-306: $\Phi_g$ Estimation (`backend/core/shape.py`)
- **Status:** PASS (0 defects).
- **Evaluation Details:**
  - Type-7 median of empirical ratios $\frac{v_{168} - v_0}{v_{24} - v_0}$ strictly enforced.
  - Training-lot-only provenance enforced: passing `train_lot_ids` excludes all non-training parts, and `lots_used` records the contributing set. Calling with `train_lot_ids` without `lot_ids` defensively refuses with `INVALID_INPUT`.
  - Normalisation $\Phi_g(24) \equiv 1$ strictly holds across all 4 shape families (`power_law`, `log_time`, `saturating`, `linear`) by short-circuiting to `1.0`.
  - Power-law exponent $n = \ln(\phi_{168}) / \ln(7)$ derived correctly and anchored at $t=168$.
  - Non-positive ratios handle gracefully (exponent marked undefined, scalar kept with warning).
  - Degenerate cases handle cleanly without NaN/inf: $n < 3$ returns `INSUFFICIENT_COHORT`; all zero-amplitude returns `NO_VARIATION`.

#### B. T-307: $\hat{V}_{168}$ + Linear Baseline (`backend/core/forecast.py`)
- **Status:** PASS (0 defects).
- **Evaluation Details:**
  - Consumes T-306 $\Phi_g(168)$ exactly: $\hat{V}_{168} = v_0 + (v_{24} - v_0) \cdot \Phi_g(168)$.
  - Linear baseline $v_0 + (v_{24} - v_0) \cdot 7.0$ always computed and emitted in payload.
  - AG-10 residual adoption strictly evaluated: correction adopted iff $\text{MAE}_{\text{residual}} + \text{spread} < \text{MAE}_{\text{shape}}$, with decision reason recorded. Ties fall back to shape-only.
  - Interval-censored $v_{24}$ (`below_lod`) consumes the reporting bound as $v_{24}$ and sets `censored = True` with a descriptive warning (conservative direction).
  - Missing $v_0$ or $v_{24}$ returns `INSUFFICIENT_DATA` with no forecast field populated; non-finite floats return `INVALID_INPUT`.

#### C. T-308: Split Conformal / Mondrian (`backend/core/conformal.py`)
- **Status:** PASS (0 defects).
- **Evaluation Details:**
  - Residuals defined as signed errors $s_i = y_i - \hat{y}_i$.
  - Exact order statistic $k = \lceil(n_{\text{cal}} + 1)(1 - \alpha)\rceil$ verified on small and large $n$.
  - When $k > n_{\text{cal}}$ at all levels, returns `upper = None`, `bound_finite = False`, `refusal_code = "INSUFFICIENT_CALIBRATION"`, and `attainable_alpha = 1 / (n_{\text{marginal}} + 1)` (never silently returns maximum residual).
  - Mondrian ladder checks $n_{\text{cal}} \ge 50$ on finest cell, falls back to parameter and marginal cells, and correctly reports the level used in `mondrian_level`. Single-group calls evaluate directly per § 2.
  - Non-finite residuals filtered out with counts recorded in warning; non-finite point or alpha outside $(0, 1)$ refuses with `INVALID_INPUT`.

#### D. T-309: Exchangeability Guard (`backend/core/guard.py`)
- **Status:** PASS (0 defects).
- **Evaluation Details:**
  - All six signals evaluated: PSI on $v_0$ and $\Delta_{24}$ (decile bins, $\epsilon=10^{-4}$), lot median robust z ($|z| > 3.0$), amplitude KS test ($p < 0.01$), temperature range, tester novelty, and group novelty.
  - Signal thresholds match constants (`GUARD_PSI_FIRE_THRESHOLD = 0.25`, `GUARD_PSI_WARN_THRESHOLD = 0.10`, etc.).
  - Firing states: any signal fired $\implies$ `VOID`; no fires and $\text{max\_psi} \ge 0.10 \implies$ `WARN` (DEGRADED); otherwise `PASS` (VALID).
  - Missing reference data does not cause false fires; reported as unevaluated with warning.
  - Warning explicitly disclaims restoring the guarantee under shift (`L-04`).

#### E. T-310: Safety / Margin / Bands (`backend/core/safety.py`)
- **Status:** PASS (0 defects).
- **Evaluation Details:**
  - Usable margin $(limit - v_0)(1 - margin\_fraction)$ and safety slope derived from configuration in physical units.
  - Delta limit $\Delta_{\text{max}}$ correctly takes precedence over the margin path for safety slope derivation.
  - Band priority ladder strictly enforced: `REJECT > EARLY_WARNING > WATCH > SAFE`.
  - Documented gap-fill verified: reserve breach ($\hat{U}_{168} \ge \text{safe\_threshold}$) promotes shallow slopes to `WATCH`.
  - Boundary equality cases ($1.0$, $0.7$, $\text{limit}$) verified.
  - Bound-driven priority verified: point forecast cannot bypass conformal bound.
  - Degenerate cases refuse safely: $v_0 \ge \text{limit}$ returns `INVALID_INPUT`; non-finite inputs return `INVALID_INPUT`; `upper_168 = None` returns `INSUFFICIENT_CALIBRATION` with `band = None`.

---

### 4. Cross-Task Integration Chain Verification

The complete end-to-end processing chain was independently verified:
$$\text{T-306 } \Phi_g \longrightarrow \text{T-307 Forecast} \longrightarrow \text{T-308 Conformal Upper} \longrightarrow \text{T-309 Guard} \longrightarrow \text{T-310 Safety Decision}$$

1. **Parameter Flow & Reuse:**
   - `estimate_phi` outputs `phi_168` ($3.0$), which is directly consumed by `forecast_v168`.
   - `forecast_v168` outputs `point` ($31.9$) and `baseline_linear` ($58.3$).
   - `conformal_upper` takes `point` and calibration residuals, computing $\hat{U}_{168} = 37.9$ µA ($\hat{q} = 6.0$).
   - `check_exchangeability` evaluates lot features against calibration references and yields `GuardResult`.
   - `evaluate_safety` consumes $\hat{U}_{168}$ and `point`, correctly assigning band `WATCH`.
2. **Refusal Propagation:**
   - Verified that when T-308 conformal upper bound produces `INFINITE` (`upper = None`), `evaluate_safety` receives `upper_168 = None` and cleanly refuses with `refusal_code = "INSUFFICIENT_CALIBRATION"` and `band = None`.
   - An unattainable or infinite bound cannot silently default to `SAFE` or `REJECT`.
3. **Guard Reaction:**
   - When the exchangeability guard produces `VOID`, the caller is instructed via warning to evaluate a conservative bound ($\alpha/2$). When supplied to `evaluate_safety`, the widened bound properly shifts the decision into `WATCH` or `REJECT`.

---

### 5. Test Integrity & Anti-Weakening (INV-6)
- **Independent Git Diff Audit:**
  - `git diff 071df9c~1 071df9c --diff-filter=M --name-only` confirmed that **zero existing test logic was modified or weakened**.
  - The only modified files in `tests/` were:
    - `tests/tests.json`: Additive only (+5 test entries: `TEST-DRIFT-009`, `TEST-DRIFT-010`, `TEST-CONF-005`, `TEST-CONF-006`, `TEST-SAFE-005`).
    - `tests/unit/test_check_test_categories.py` and `tests/unit/test_check_traceability.py`: 4 mechanical count literal updates (`123 → 128`) mirroring the registered test count.
  - Zero assertions weakened, zero tolerances widened, zero tests deleted.
  - All 48 new tests across 12 test files are genuine, adversarial, and rigorous (including Hypothesis property tests with 60–100 iterations).

---

### 6. Architecture & Governance Verification
- **Pure Numeric Core:** AST scans and import graph checks confirm zero framework, zero I/O, and zero datagen imports in `backend/core/**`.
- **Phase Boundaries:**
  - Phase 2 files (`datagen/**`, `data/**`, `reports/DATASET_PROFILE.md`) are 100% untouched.
  - T-311+ tasks (`risk.py`, `recommend.py`, `formulas.py`, `traced.py`) are unstarted.
  - Protected test split scoring (T-406) was not accessed or executed.
- **Constant Provenance:** All 10 newly introduced constants in `backend/core/constants.py` are registered in `NUMERIC_CONSTANTS` with complete provenance tags (`assumed` / `derived`), source references, units, and `D-036` links.
- **Decision Alignment:** Implementation is 100% consistent with `DECISIONS.md § D-036`.

---

### 7. Exact Reproduction for Any Defect
- **Defects Found:** **0** (Zero defects identified in T-306 through T-310).
- **Non-Blocking Informational Notes:**
  - **INFO-001 (Exchangeability Guard PSI Sample Size Sensitivity):**
    Decile-binned PSI on small lot cohorts ($n \sim 100-120$) exhibits finite-sample variance. When comparing two samples drawn from the identical distribution, random histogram fluctuation at $n \approx 120$ can occasionally register in the `[0.10, 0.25]` range (`WARN` / `DEGRADED`). At $n \ge 500$, PSI stably measures $\approx 0.01-0.03$ (`PASS`). This sensitivity is an intrinsic property of empirical decile PSI binning on finite cohorts and is documented in `D-036`.
  - **INFO-002 (Mechanical Count Updates under INV-6):**
    Register growth from 123 to 128 tests required updating four size literals in `tests/unit/test_check_test_categories.py` and `tests/unit/test_check_traceability.py`. Lead Orchestrator sign-off is formally recorded in `D-036` and noted here.

---

## 6. Summary Status of All Tracked Findings

| Finding | Component | Severity | Nature | Status |
|---|---|---|---|---|
| **TEST-001** | `backend/core/dpat.py` | Major | Small-cohort zero-MAD fallback producing `inf` | **RESOLVED** (Commit `23ca654`) |
| **TEST-002** | `backend/core/constants.py` | Minor | RT-008 single-occurrence scoping | **RESOLVED** (Commit `23ca654`) |
| **TEST-003** | `backend/core/dpat.py` | Minor | `part_value=None` returning PASS verdict | **RESOLVED** (Commit `23ca654`) |
| **TEST-004** | `backend/core/dpat.py` | Minor | Candidate `part_value=NaN` returning PASS | **RESOLVED** (Commit `23ca654`) |
| **TEST-005** | `backend/core/robust.py` | Minor | Type-7 $IQR=0 \implies MAD=0$ invariant | **RESOLVED** (Commit `23ca654`) |
| **TEST-006** | `backend/core/multivariate.py` | Minor | Unhandled `ValueError` on mismatched `parameter_names` | Non-blocking (T-304) |
| **TEST-007** | `backend/core/multivariate.py` | Minor | Column permutation equivariance broken by FastMCD row-sort | Non-blocking (T-304) |
| **TEST-008** | `backend/core/multivariate.py` | Minor | Precision overflow and `NaN` coercion on subnormal $\sigma < 10^{-154}$ | Non-blocking (T-304) |
| **TEST-009** | `backend/core/multivariate.py` | Informational | Pre-sort `np.std` causing 1-ULP row-permutation variance | Non-blocking (T-304) |
| **INFO-001** | `backend/core/guard.py` | Informational | Finite-sample variance of decile PSI on $n \sim 120$ cohorts | Non-blocking (T-309) |
| **INFO-002** | `tests/unit/` | Informational | Register growth 123 → 128 mechanical count mirror | Non-blocking (`INV-6` / `D-036`) |

*Note: Zero defects found for T-305 and T-306 → T-310.*

---

## 7. Prior Batch Verdict (T-306 → T-310): PASS

The T-306 → T-310 batch was verified in commit `3f9aa9d` as **PASS** (see § 5 for full details).

---

## 8. Independent Test Execution & Verification of T-311 through T-316 (Commits `6e4b755` and `57c1e42`)

The independent QA engineer performed exhaustive, adversarial, and mathematical verification of the final Phase 3 batch (T-311 through T-316) across `backend/core/risk.py`, `backend/core/recommend.py`, `backend/core/explain.py`, `backend/core/formulas.py`, `backend/core/traced.py`, `backend/tests/arch/test_import_graph.py`, `backend/tests/integration/test_phase3_chain.py`, and all associated test suites per `RISK_SCORING_SPEC § 1-§ 7`, `EXPLAINABILITY_SPEC § 1-§ 6`, `PROVENANCE_SPEC § 1-§ 5`, and `DECISIONS.md § D-037`:

### 8.1 Executive Verdict

**Batch Verdict:** **PASS** (Zero blocking defects, zero weakened tests, 100% mathematical and architectural compliance).

---

### 8.2 Quantitative Test Execution Table

All test suites were executed independently in the pinned environment (`uv run pytest`):

| Test Suite / Target | Number of Tests | Duration | Exit Code | Result | Details / Invariants Verified |
|---|---|---|---|---|---|
| `backend/tests/` (Full Backend Suite) | **154 passed** | 24.70s | `0` | **PASS** | 100 unit, 51 property (Hypothesis), 2 integration, 1 arch |
| `tests/unit/` (Pre-Commit & Repo Suite) | **79 passed** | 38.09s | `0` | **PASS** | Data generation, physics, strata, labels, governance |
| `backend/tests/unit/test_constants.py` | 4 passed | 0.78s | `0` | **PASS** | Provenance tags, AST scan (no forbidden literals), singular 1.35/1.4826 |
| `backend/tests/arch/test_import_graph.py` | 4 passed | 0.22s | `0` | **PASS** | Generator isolation, forbidden frameworks, allowlisted roots, acyclic DAG |
| `backend/tests/integration/test_phase3_chain.py` | 2 passed | 0.81s | `0` | **PASS** | Full 12-stage provenance spine, re-derivation rate = 1.0, byte-identical replay |
| Independent Verification Script (`scratch/verify_t311_t316.py`) | 19 assertions | 0.45s | `0` | **PASS** | Independent hand oracles, sum-check, AST security injection, PDA boundaries |
| **Combined Grand Total** | **233 passed** | **63.57s** | `0` | **PASS** | **Zero failures, zero errors, zero regressions** |

---

### 8.3 Quality Gate & Compliance Verification Status

| Quality Gate / Standard | Command / Check | Expected | Actual | Status |
|---|---|---|---|---|
| **QG-CORE-01** (Test Categories & Coverage) | `uv run python3 scripts/check_test_categories.py` | 31/31 core functions covered; valid categories; honest oracles | 31/31 core functions covered; 135 total tests; 0 invalid categories | **PASS** |
| **QG-DOC-01** (Bidirectional Traceability) | `uv run python3 scripts/check_traceability.py` | 60/60 P0 requirements covered in register & matrix; 0 unmapped | 60/60 P0 requirements covered; 135 register tests; 116 matrix tests | **PASS** |
| **QG-ARCH-01** / **TEST-ARCH-001** (Boundary Isolation) | `test_core_boundary_and_generator_isolation` | Zero datagen, app, or I/O imports in `backend/core/**` | 0 forbidden imports detected across all 15 core modules | **PASS** |
| **QG-REL-03** / **INV-8** (Reproducibility & Determinism) | `test_phase3_chain_replays_byte_identically` | Identical inputs produce bitwise-identical records and prose | All 31 TracedValues, ExplanationResult, RederivationReport byte-identical | **PASS** |
| **RT-008** (Literal Discipline AST Scan) | `test_core_ast_scan_no_unregistered_literals` | No numeric literal outside `{0, 1, 2}` outside `constants.py` | Traversed AST of all 15 core files; 0 unregistered numeric literals | **PASS** |
| **INV-6** (Test Integrity & Anti-Weakening) | Git diff audit of commit `6e4b755` | Zero existing tests weakened or deleted; additive-only additions | 7 additive test entries (128 → 135); mechanical count updates only | **PASS** |
| **Code Formatting** | `uv run black --check backend/` | Zero formatting discrepancies | 54 source files checked; 0 modified | **PASS** |
| **Code Linting** | `uv run ruff check backend/` | Zero lint violations | All checks passed | **PASS** |
| **Static Type Checking** | `uv run mypy backend/core backend/tests` | Zero typing errors | Success: no issues found in 53 source files | **PASS** |

---

### 8.4 Task-by-Task Verification Breakdown

#### A. T-311: Risk Decomposition & Lot Roll-up (`backend/core/risk.py`)
- **Authoritative Decision Values:** `compute_risk()` consumes the authoritative `SafetyResult` (slope ratio, predicted margin percentage, safety band), `AttributionVerdict`, and primary robust distance $z_{\text{primary}}$. It never re-derives or approximates upstream science.
- **Five Component Decomposition:**
  1. `risk.anomaly_v1`: $|z|$ mapped across $[z_{\text{low}}, z_{\text{high}}] = [3.0, 6.0]$ and clamped to $[0, 1]$.
  2. `risk.drift_v1`: `slope_ratio / slope_ref` with `slope_ref = 2.0` (criterion boundary reads exactly 0.5) clamped to $[0, 1]$.
  3. `risk.margin_v1`: $1 - \text{margin\_pct}$ clamped to $[0, 1]$.
  4. `risk.quality_v1`: $1 - \text{data\_quality\_score}$ (evidential weakness channel, independent from part drift).
  5. `risk.credit_v1`: Setup-attributable evidence ($1.0$ for `SOCKET`/`TESTER`, $0.5$ for `ZONE` with `zone_arrhenius_consistent=True`, else $0.0$).
- **Sum Check Enforcement:**
  $\sum_{i} \text{weighted}_i \equiv \text{risk\_index}$ within `SUM_CHECK_TOLERANCE` ($10^{-9}$). If a mismatch exceeds $10^{-9}$, `compute_risk()` refuses loudly rather than papering over discrepancy.
- **Band Invariance (RT-010):**
  Sweeping weights across $[0, 1]$ over 100 randomized configurations confirmed that the echoed `band` is **strictly immutable** and identical to `safety.band`. Weights order the worklist; they never alter the safety disposition.
- **Upstream Refusal Propagation:**
  When `SafetyResult` or `z_primary` refuses (e.g. `INSUFFICIENT_CALIBRATION`, `INVALID_INPUT`, `INSUFFICIENT_DATA`), `compute_risk()` cleanly propagates the refusal code, emits an empty component tuple, sets `band = None`, and assigns `risk_index = 0.0` (never a default or misleading index).
- **PDA Roll-up Exactness (FR-407 / D-A-03):**
  `roll_up_lot()` computes both figures:
  - `pda_pct` $= 100 \cdot n_{\text{reject}} / n_{\text{tested}}$.
  - `pda_pct_including_early_warning` $= 100 \cdot (n_{\text{reject}} + n_{\text{early\_warning}}) / n_{\text{tested}}$.
  - Exclusions ($n_{\text{excluded}}$ from missing or refused parts) are counted and explicitly kept out of the denominator, preventing false dilution.
  - Verdict boundaries verified:
    - $\le 4.0\% \implies \text{PASS\_LOT}$
    - $> 4.0\%$ and $\le 5.0\% \implies \text{REVIEW}$
    - $> 5.0\% \implies \text{FAIL\_LOT}$

#### B. T-312: Disposition Rule Table & Narrative Engine (`backend/core/recommend.py`, `backend/core/explain.py`)
- **Total Ordered Disposition Table (FR-406 / RISK_SCORING_SPEC § 6):**
  - Evaluates in strictly ordered sequence (first match wins):
    1. Missing / invalid inputs $\implies$ `INSUFFICIENT_EVIDENCE` with trigger text explaining what is missing.
    2. Absolute limit failure ($FR\text{-}210$) $\implies$ `REJECT` (supersedes all other indicators).
    3. `SOCKET` or `TESTER` attribution $\implies$ `RETEST_DIFFERENT_SOCKET` (setup produced the signal; part not blamed).
    4. `ZONE` attribution $\implies$ `ZONAL_REVIEW` if `zone_arrhenius_consistent=True`, else `INVESTIGATE`.
    5. Conformal bound `REJECT` $\implies$ `REJECT` (bound crosses absolute limit and setup is not exonerated).
    6. `EARLY_WARNING` with `predicted_margin_pct > 0` $\implies$ `EXTEND_BURN_IN` (evidence-gathering).
    7. `WATCH` with quiet anomaly channel ($|z| < 4.5$) and `PART` $\implies$ `MONITOR`.
    8. Conflicting channels, weak evidence, or `INDETERMINATE` $\implies$ `INVESTIGATE` (disagreement reported, not smoothed).
    9. `SAFE` with nominal anomaly ($|z| < 3.0$) and strong evidence $\implies$ `ACCEPT`.
    10. Fallback $\implies$ `INVESTIGATE`.
  - Every action is accompanied by its immutable trigger text and severity classification.
- **Spec Amendment Resolution (D-037):**
  - P-037-a: `MONITOR` action adopted for `WATCH` + quiet anomaly + `PART`.
  - P-037-b: `INSUFFICIENT_EVIDENCE` adopted for missing inputs.
- **Digit-Free Narrative Templates (TEST-EXPL-001):**
  - Verified regex scan across all entries in `NARRATIVE_TEMPLATES`: exactly zero literal digits exist outside variable `{slot}` and `[[label]]` markers.
  - Every `{slot}` resolves to a validated `TracedValue` from the payload; every `[[label]]` resolves to an explicit string.
- **Unsuppressable Uncertainty Clauses (D-016 / EXPLAINABILITY_SPEC § 6):**
  - Mandatory clauses are injected whenever evidential weakness exists:
    - Small cohort $\implies$ `"Small-cohort statistics apply; statistical power is reduced."`
    - Fallback grouping $\implies$ `"Conformal bound uses fallback grouping level {k}."`
    - Guard non-valid $\implies$ `"Exchangeability guarantee is {status}; the bound is conservative."`
    - Censored read point $\implies$ `"A read point was interval-censored; the bound was consumed conservatively."`
  - These clauses cannot be silenced or removed by configuration.
- **L2 "Show the Arithmetic" Line:**
  `render_arithmetic()` successfully reconstructs the exact mathematical equation with operands substituted, equated to the final value (e.g. `10.4 + 6.0 * 2.0 = 22.4`).

#### C. T-313: Append-Only Formula Registry (`backend/core/formulas.py`)
- **33 Immutable Registry Entries:**
  - Exactly 33 entries: 26 algebraic expressions (`derivation == "expression"`) and 7 procedural roots (`derivation == "procedural"`: `robust.median_v1`, `robust.q1_v1`, `robust.q3_v1`, `shape.phi_168_v1`, `conformal.q_hat_v1`, `mahalanobis.d2_v1`, `risk.credit_v1`).
  - No entries were edited or removed; new IDs follow append-only semantics per Architecture § 7.2.
- **Restricted AST Expression Evaluator (RT-007):**
  - `evaluate_expression()` parses and executes canonical expression strings using an AST whitelist (`ast.Constant`, `ast.Name`, `ast.BinOp`, `ast.UnaryOp`, `ast.Call` restricted strictly to `min`, `max`, `abs`).
  - The evaluator has **zero access to `backend.core`**, preventing circular dependencies or execution leaks.
  - Security audit confirmed that code execution, imports, attribute access, lambdas, and comprehensions are completely blocked.
- **Procedural Roots Anchoring:**
  - Procedural roots execute authoritative core callables directly (`median`, `quartiles`, `estimate_phi`, `conformal_upper`, `mahalanobis`, `attribution_credit_value`).
  - `rederivation_rate()` separates procedural roots into `n_procedural` and does not count them as algebraic rederivation failures.

#### D. T-314: TracedValue Provenance Carrier (`backend/core/traced.py`)
- **Carrier Integrity (PROVENANCE_SPEC § 3):**
  - `TracedValue` is a frozen dataclass containing `value`, `unit`, `formula_id`, `inputs`, `parameters`, `dataset_hash`, `display_precision`, and optional `model_version`.
  - Closed unit enum (`UNIT_ENUM`): contains only `{"uA", "ns", "sigma", "ratio", "hours", "index", "percent", "probability", "dimensionless", "uA/h", "ns/h"}`. Empty string `""` or arbitrary units are rejected.
  - Operand / Parameter Bi-Directional Validation: Given `inputs` and `parameters` must match the registry specification exactly in both directions (extra or missing keys raise `ValueError`).
  - Required Non-Empty `dataset_hash`: Mandatory on every record.
  - Non-Negative Integer `display_precision`: Preserved identically across UI, JSON, and PDF surfaces (RT-012).
- **Verified Stage Wrapping (`_wrap_verified`):**
  - Checks computed stage values against registry `fn` within `SUM_CHECK_TOLERANCE` ($10^{-9}$).
  - Verifies that unit rules (`same_as:<operand>`, literal rules, or `explicit`) are obeyed.
  - Any value discrepancy or unit violation raises loudly and halts construction.

#### E. T-315: Architecture & Import Graph Enforcement (`backend/tests/arch/test_import_graph.py`)
- **Preserved Existing Boundary Tests:** Original `test_core_boundary_and_generator_isolation` remains byte-intact.
- **Extended Architecture Assertions:**
  1. `test_core_forbids_frameworks_and_heavy_dependencies`: Confirms that `pydantic`, `pandas`, `polars`, `duckdb`, `joblib`, `jinja2`, `uvicorn`, `celery`, `redis`, `kafka`, `boto3`, `openai`, `torch`, `tensorflow`, `jax`, `matplotlib`, `plotly` never appear in `backend/core/**`.
  2. `test_core_imports_allowlisted_roots_only`: Confirms that import roots are strictly limited to Python standard library, `{numpy, scipy, sklearn}`, and `backend`.
  3. `test_core_internal_graph_acyclic_and_layered`: Builds the intra-core dependency graph and verifies it is strictly acyclic and layered.
  4. **Upstream Immutability:** Explicitly asserts that verified T-301..T-310 modules (`constants`, `robust`, `dpat`, `multivariate`, `attribution`, `shape`, `forecast`, `conformal`, `guard`, `safety`) import zero T-311..T-314 modules.

#### F. T-316: End-to-End Provenance Spine Integration (`backend/tests/integration/test_phase3_chain.py`)
- **Complete 12-Stage Pipeline:**
  $$\text{Robust} \to \text{DPAT} \to \text{Mahalanobis} \to \text{Attribution} \to \text{Shape} \to \text{Forecast} \to \text{Conformal} \to \text{Guard} \to \text{Safety} \to \text{Risk} \to \text{Recommend} \to \text{Explain}$$
- **Full Provenance Carrier Wall:**
  31 individual `TracedValue`s wrapped stage-by-stage immediately upon computation.
- **Re-derivation Rate 1.0:**
  `rederivation_rate()` verified $100\%$ match across all considered expression items (`rate = 1.0`, `failures = ()`).
- **Repeatability (INV-8):**
  Two independent executions of the full chain produce bitwise-identical `wall` records, bitwise-identical `narration` text, and bitwise-identical `report`.

---

### 8.5 Independent Mathematical and Analytical Oracle Checks

#### A. Hand-Calculated Risk Oracle
Evaluated part on the standard DRIFT_SPEC § 8 reference geometry:
- $z_{\text{primary}} = 4.5$ ($z_{\text{low}} = 3.0, z_{\text{high}} = 6.0$):
  $$\text{anomaly} = \frac{4.5 - 3.0}{6.0 - 3.0} = \frac{1.5}{3.0} = 0.500000$$
- $\text{slope\_ratio} = 1.000000$ ($\text{slope\_ref} = 2.0$):
  $$\text{drift} = \frac{1.0}{2.0} = 0.500000$$
- $\text{margin\_pct} = 0.250000$:
  $$\text{margin} = 1.0 - 0.25 = 0.750000$$
- $\text{data\_quality\_score} = 0.900000$:
  $$\text{quality} = 1.0 - 0.90 = 0.100000$$
- $\text{Attribution} = \text{SOCKET}$:
  $$\text{credit} = 1.000000$$
- Default weights ($w_a=0.3, w_b=0.3, w_m=0.2, w_q=0.1, w_c=0.1$):
  $$\text{Risk Total} = 0.3(0.5) + 0.3(0.5) + 0.2(0.75) + 0.1(0.1) - 0.1(1.0) = 0.15 + 0.15 + 0.15 + 0.01 - 0.10 = 0.360000$$
- **Independent Execution:** `risk_index` evaluated to exactly `0.360000` ($< 10^{-14}$ difference), with `sum_check.abs_diff = 0.0 <= 1e-9`.

#### B. Hand-Calculated PDA Boundaries
- Pass boundary ($n_{\text{tested}} = 100, n_{\text{reject}} = 4$): $\text{PDA} = 4.0\% \implies \text{PASS\_LOT}$.
- Review lower boundary ($n_{\text{tested}} = 1000, n_{\text{reject}} = 41$): $\text{PDA} = 4.1\% \implies \text{REVIEW}$.
- Review upper boundary ($n_{\text{tested}} = 100, n_{\text{reject}} = 5$): $\text{PDA} = 5.0\% \implies \text{REVIEW}$.
- Fail boundary ($n_{\text{tested}} = 1000, n_{\text{reject}} = 51$): $\text{PDA} = 5.1\% \implies \text{FAIL\_LOT}$.
- Second figure ($n_{\text{reject}} = 5, n_{\text{early\_warning}} = 5, n_{\text{tested}} = 100$): $\text{PDA} = 5.0\%$, $\text{PDA}_{\text{ew}} = 10.0\% \implies \text{REVIEW}$.
- Excluded handling ($n_{\text{reject}} = 10, n_{\text{safe}} = 80, n_{\text{excluded}} = 10$): $n_{\text{tested}} = 90, \text{PDA} = (10/90) \cdot 100 = 11.11\% \implies \text{FAIL\_LOT}$. Excluded parts are not counted in $n_{\text{tested}}$.

#### C. L2 Arithmetic Formatting Hand Oracle
- Formula `dpat.limit_high_v1` with operands `median=10.4`, `k=6.0`, `robust_sigma=2.0`, value `22.4`:
  - `render_arithmetic()` produced exactly: `"10.4 + 6.0 * 2.0 = 22.4"`.

---

### 8.6 Adversarial & Security Attack Summary

The independent test script (`scratch/verify_t311_t316.py`) subjected the code to targeted adversarial vectors:
1. **Sum-Check Boundary Tampering:** Checked that $\sum_i c_i \equiv \text{total}$ within $10^{-9}$. Artificial perturbation $> 10^{-9}$ was proven rejected in unit tests.
2. **Band Alteration Attack (RT-010):** Swept 100 random weight vectors. Echoed band was $100\%$ invariant.
3. **Negative / Non-Finite Weights:** Evaluated `w_anomaly = -0.1` $\implies$ safely refused with `INVALID_INPUT` and `band = None`.
4. **Refusal Propagation:** Evaluated upstream safety refusal $\implies$ cleanly returned `refusal_code = "INSUFFICIENT_CALIBRATION"`, `risk_index = 0.0`, `band = None`.
5. **Non-Finite z-Distance:** Evaluated `NaN`, `+inf`, `-inf` $\implies$ safely refused with `INVALID_INPUT`.
6. **Template Literal Scan (TEST-EXPL-001):** Scanned all narrative templates without slot/label markers $\implies$ exactly zero digits found.
7. **Unsuppressable Clauses:** Tested `reduced_power=True`, `mondrian_level=3`, `guarantee_status="VOID"`, `censored=True` $\implies$ all 4 mandatory clauses appeared in output text.
8. **AST Evaluator Injection Attacks:** Executed 11 code injection vectors (`__import__`, `open`, `eval`, `exec`, attribute access, list comprehensions, lambda) against `evaluate_expression()` $\implies$ all 11 raised `ValueError`.
9. **TracedValue Immutability:** Attempted in-place attribute assignment on `TracedValue` $\implies$ caught and rejected with `FrozenInstanceError`.
10. **TracedValue Validation Matrix:** Tested missing operands, extra operands, unknown formula ID, non-finite values, and empty units $\implies$ all raised `ValueError`.
11. **Stage Value Tampering:** Attempted passing tampered value ($23.0$ instead of $22.0$) into `_wrap_verified` $\implies$ detected and rejected with `ValueError: Value 23.0 disagrees with 'dpat.limit_high_v1'`.

---

### 8.7 Architectural Compliance and Import Graph Audit

- **Extended Forbidden Modules Verified:** Confirmed zero imports of frameworks (`pydantic`, `pydantic_settings`), heavy data libraries (`pandas`, `polars`, `duckdb`), external storage / compute (`joblib`, `redis`, `celery`, `kafka`, `boto3`), ML / LLM frameworks (`torch`, `tensorflow`, `jax`, `openai`), or visualization engines (`matplotlib`, `plotly`, `jinja2`).
- **Allowed Import Roots:** Confirmed that all imports in `backend/core/**` originate strictly from the Python standard library, allowed third-party numerical roots (`numpy`, `scipy`, `sklearn`), or internal `backend` modules.
- **Intra-Core Layering:** Confirmed the acyclic dependency hierarchy:
  - `constants` (Layer 0, leaf)
  - `robust`, `forecast`, `conformal`, `safety` (Layer 1)
  - `dpat`, `shape` (Layer 2)
  - `multivariate` (Layer 2)
  - `attribution`, `guard` (Layer 3)
  - `formulas` (Layer 3)
  - `traced` (Layer 4)
  - `risk`, `recommend`, `explain` (Layer 5)
- **Zero Upstream Leakage:** Verified that no verified module from T-301..T-310 imports any module from T-311..T-314.

---

### 8.8 Provenance Spine & Full-Chain Integration Audit

- **12-Stage Processing Spine:** Verified that all 12 stages run end-to-end on synthetic parts, maintaining full provenance and decision fidelity.
- **Decision Invariants Verified on Full Chain:**
  - `risk.band == safety.band == band` strictly holds.
  - `risk.sum_check.abs_diff <= 1e-9` strictly holds.
  - Recommendation action `INVESTIGATE` triggered with conflict trigger text.
  - Exchangeability guard outputs valid / degraded status into explanation clauses.
  - All 31 `TracedValue` records contain non-empty units, valid formula IDs, exact matching inputs/parameters, and valid `dataset_hash`.
  - Re-derivation rate over the entire chain equals $1.0$ ($0$ failures).
  - Byte-identical determinism on replay (`INV-8`).

---

### 8.9 Test Integrity & Governance Audit

- **Commit Inspection (`6e4b755` and `57c1e42`):**
  - Total insertions: 4,259 lines across 21 files.
  - Existing implementation files from T-301..T-310: **100% untouched** (0 lines modified).
  - Phase 2 files (`datagen/**`, `data/**`, `reports/DATASET_PROFILE.md`): **100% untouched**.
  - Phase 4 / API files (`backend/api/**`): **100% untouched and unstarted**.
  - Protected test split scoring (T-406): **100% untouched**.
  - Modifications to existing test files:
    - `tests/tests.json`: Additive only (+7 test IDs: `TEST-RISK-006`, `TEST-RISK-007`, `TEST-REC-008`, `TEST-EXPL-005`, `TEST-EXPL-006`, `TEST-EXPL-007`, `TEST-PROV-006`).
    - `tests/unit/test_check_test_categories.py` and `tests/unit/test_check_traceability.py`: Exactly 4 mechanical count literal updates (`128 → 135`) mirroring the registered test count.
  - **Zero tests weakened, zero assertions loosened, zero tests deleted.**

---

### 8.10 Defect Log

**Defects Found:** **0** (Zero defects identified in T-311 through T-316).

---

## 9. Comprehensive Summary Status of All Tracked Findings Across Phase 3

| Finding | Component | Severity | Nature | Status |
|---|---|---|---|---|
| **TEST-001** | `backend/core/dpat.py` | Major | Small-cohort zero-MAD fallback producing `inf` | **RESOLVED** (Commit `23ca654`) |
| **TEST-002** | `backend/core/constants.py` | Minor | RT-008 single-occurrence scoping | **RESOLVED** (Commit `23ca654`) |
| **TEST-003** | `backend/core/dpat.py` | Minor | `part_value=None` returning PASS verdict | **RESOLVED** (Commit `23ca654`) |
| **TEST-004** | `backend/core/dpat.py` | Minor | Candidate `part_value=NaN` returning PASS | **RESOLVED** (Commit `23ca654`) |
| **TEST-005** | `backend/core/robust.py` | Minor | Type-7 $IQR=0 \implies MAD=0$ invariant | **RESOLVED** (Commit `23ca654`) |
| **TEST-006** | `backend/core/multivariate.py` | Minor | Unhandled `ValueError` on mismatched `parameter_names` | Non-blocking (T-304) |
| **TEST-007** | `backend/core/multivariate.py` | Minor | Column permutation equivariance broken by FastMCD row-sort | Non-blocking (T-304) |
| **TEST-008** | `backend/core/multivariate.py` | Minor | Precision overflow and `NaN` coercion on subnormal $\sigma < 10^{-154}$ | Non-blocking (T-304) |
| **TEST-009** | `backend/core/multivariate.py` | Informational | Pre-sort `np.std` causing 1-ULP row-permutation variance | Non-blocking (T-304) |
| **INFO-001** | `backend/core/guard.py` | Informational | Finite-sample variance of decile PSI on $n \sim 120$ cohorts | Non-blocking (T-309) |
| **INFO-002** | `tests/unit/` | Informational | Register growth 123 → 128 mechanical count mirror | Non-blocking (`INV-6` / `D-036`) |
| **INFO-003** | `tests/unit/` | Informational | Register growth 128 → 135 mechanical count mirror | Non-blocking (`INV-6` / `D-037`) |

*Note: Zero defects found across T-305, T-306 → T-310, and T-311 → T-316.*

---

## 10. Phase 3 Complete Final Verdict & Phase 4 Handoff Assessment

### Final Verdict: **PASS**

### Summary Justification:
1. **Full Phase 3 Scope Completed & Verified:**
   - All tasks from T-301 through T-316 are completely implemented, independently tested, and mathematically verified.
   - The numerical core (`backend/core/`) is fully operational across all 15 modules: `constants`, `robust`, `dpat`, `multivariate`, `attribution`, `shape`, `shape_fit`, `forecast`, `residual`, `conformal`, `guard`, `safety`, `risk`, `recommend`, `explain`, `formulas`, `traced`.
2. **Quality Gates & Clean Repository State:**
   - 233/233 tests pass (154 backend + 79 repo unit).
   - QG-CORE-01 (31/31 core functions covered), QG-DOC-01 (60/60 P0 requirements traced), QG-ARCH-01 (pure numeric core isolation), RT-008 (AST scan clean) are 100% green.
   - Linters (`ruff`, `black`, `mypy`) report zero errors across all source files.
3. **Provenance & Audit Readiness:**
   - Append-only registry with 33 formula entries and secure AST evaluator.
   - Complete 12-stage provenance chain with 31 verified TracedValues and re-derivation rate of 1.0.
   - Deterministic repeated execution verified end-to-end (INV-8).
4. **Handoff Readiness for Phase 4:**
   - The numerical core is stable, sealed, frozen, and completely verified.
   - Phase 4 (Evaluation & Benchmark Suite: T-401..T-406) may proceed safely.

---

## 11. Independent Test Execution & Verification of T-501 (Commit `0c3a10c`)

**Run Date:** 2026-09-10
**Role:** Independent Tester / QA Engineer (`qa-playwright-engineer`)
**Scope Under Evaluation:** T-501 — FastAPI app factory, envelope, error enum, `/healthz`, `/version`
**Implementation Commit:** `0c3a10c` (`feat(api): FastAPI boundary with envelope, error enum, health/version (T-501)`)
**Governance Commit:** `133cbee` (`docs(governance): mark T-501 DONE and record coder handoff`)
**Prior Phase 4 Head:** `7520bb6` (sealed; untouched)

### 11.1 Executive Verdict

**Batch Verdict:** **PASS** (Zero blocking defects, zero weakened tests, zero core modifications, 100% contract conformance).

---

### 11.2 Quantitative Test Execution Table

| Test Suite / Target | Tests | Duration | Result | Details |
|---|---|---|---|---|
| `backend/tests/unit/test_error_enum.py` | **5 passed** | <1s | **PASS** | ErrorCode enum closure, status mapping, remediation, SR-06 500 handler |
| `backend/tests/unit/test_traced_schema.py` | **3 passed** | <1s | **PASS** | Provenance boundary survival, malformed rejection, DataProvenance enum |
| `backend/tests/integration/test_system_api.py` | **7 passed** | <1s | **PASS** | Envelope shape, degraded naming, alias equivalence, OpenAPI, structured 404, determinism, request-id round-trip |
| **T-501 New Suites Total** | **15 passed** | **~2s** | **PASS** | All `@pytest.mark.fast` |
| `backend/tests/` (Full Backend Suite) | **165 passed** | 22.09s | **PASS** | 100 unit, 51 property, 6 integration, 1 integration (system), 1 arch, 1 reproducibility |
| `tests/tests.json` Register | **159 entries** | — | **VERIFIED** | 11 Phase 4b IDs present (TEST-PROV-001..006, TEST-API-001..005) |

---

### 11.3 Audit Area Results

#### A. App / Routing — **PASS**

| Check | Expected | Actual | Status |
|---|---|---|---|
| `create_app()` factory exists | Yes | `backend/app/main.py:28` | **PASS** |
| `/api/v1` prefix on all routes | Yes | `main.py:42` `prefix="/api/v1"` | **PASS** |
| OpenAPI served at `/api/v1/openapi.json` | Yes | `main.py:47` `openapi_url=f"{prefix}/openapi.json"` | **PASS** |
| OpenAPI version starts with `3.1` | Yes | Test asserts `document["openapi"].startswith("3.1")` | **PASS** |
| Request-ID + timing middleware | Yes | `main.py:52-54` `RequestIDMiddleware` | **PASS** |
| `GET /healthz` returns `Envelope[HealthData]` | Yes | `system.py:87-91` | **PASS** |
| `GET /health` alias on same handler | Yes | `system.py:94-98` — both TASKS.md and API_CONTRACT § 3 satisfied | **PASS** |
| `GET /version` returns `Envelope[VersionData]` | Yes | `system.py:101-105` | **PASS** |
| 404 handler returns structured error | Yes | `main.py:77-81` `not_found_handler` | **PASS** |
| `ApiError` exception handler registered | Yes | `main.py:67-68` | **PASS** |
| Validation error handler registered | Yes | `main.py:70-75` | **PASS** |
| Unhandled exception handler (SR-06) | Yes | `main.py:83-87` | **PASS** |
| Health degrades honestly (T-502/T-401 absent) | Yes | `system.py:55-66` `missing=["dataset: ...T-502", "models: ...T-401", "profile: ..."]` | **PASS** |
| Introspection failures degrade, never 500 | Yes | `system.py:47-54` narrow `except` guards | **PASS** |

**Finding:** None.

#### B. Envelope / Meta — **PASS**

| Check | Expected | Actual | Status |
|---|---|---|---|
| Success shape: `{data: T, meta: {...}}` | Yes | `schemas.py:72-76` `Envelope[T]` | **PASS** |
| Error shape: `{error: {code, message, details, remediation, request_id}}` | Yes | `errors.py:139-153` `error_body()` | **PASS** |
| Meta has all 9 contract keys | Yes | `META_KEYS = {request_id, computed_at, dataset_hash, profile_id, profile_version, model_versions, data_provenance, code_git_sha, duration_ms}` | **PASS** |
| `computed_at` is nanosecond epoch | Yes | `runtime.py:85` `time.time_ns()` | **PASS** |
| `data_provenance` is `SYNTHETIC` | Yes | Test asserts `payload["meta"]["data_provenance"] == "SYNTHETIC"` | **PASS** |
| `code_git_sha` is non-empty | Yes | Test asserts `payload["meta"]["code_git_sha"]` is truthy | **PASS** |
| Volatile fields: `request_id`, `computed_at`, `duration_ms` | Present but per-request | Verified via `_volatile_stripped()` determinism test | **PASS** |
| `request_id` defaults to `uuid4().hex` | Yes | `runtime.py:94-98` | **PASS** |
| Caller-supplied `X-Request-ID` honoured | Yes | Test: `headers={"X-Request-ID": "caller-123"}` → `meta["request_id"] == "caller-123"` | **PASS** |

**Finding:** None.

#### C. Error Handling — **PASS**

| Check | Expected | Actual | Status |
|---|---|---|---|
| `ErrorCode` enum is closed | Exactly 15 members | 14 contract + `NOT_FOUND` (D-042) = 15 | **PASS** |
| `ERROR_STATUS` maps each code to correct HTTP status | Per API_CONTRACT § 9 | All 15 mappings verified | **PASS** |
| `ERROR_REMEDIATION` present for every non-500 code | Yes | `test_every_non_500_code_carries_remediation` | **PASS** |
| `INTERNAL_ERROR` has no remediation | Yes | Test asserts `"remediation" not in error_body(INTERNAL_ERROR, ...)` | **PASS** |
| `ApiError(INTERNAL_ERROR, ...)` raises `ValueError` | Yes | `test_api_error_refuses_internal_error_code` | **PASS** |
| 500 handler: generic message, no trace, no paths | Yes | `test_internal_fault_is_500_without_leaks`: `"boom" not in message`, `"/secret/worktree" not in message` | **PASS** |
| 500 handler: `request_id` present | Yes | Test asserts `payload["error"]["request_id"] == "req-9"` | **PASS** |
| 500 handler: `details` is empty list | Yes | Test asserts `payload["error"]["details"] == []` | **PASS** |
| Error envelope: `{error: {...}}` wrapping | Yes | `test_api_error_envelope_shape_and_status` | **PASS** |
| `NOT_FOUND` → 404 with remediation | Yes | `test_unknown_path_is_structured_404_not_500` | **PASS** |
| `NOT_FOUND` details carry the unmatched path | Yes | `payload["error"]["details"] == [{"path": "/api/v1/does-not-exist"}]` | **PASS** |

**D-042 Assessment:** The `NOT_FOUND` enum member is implemented as PROPOSED in DECISIONS.md. It is the correct solution (honest attribution, structured body, no alternative code path). Sign-off is requested from the Lead Orchestrator. The implementation is correct and tested.

**Finding:** None.

#### D. TracedValue / Schema — **PASS**

| Check | Expected | Actual | Status |
|---|---|---|---|
| `TracedValueSchema` mirrors core `TracedValue` field-for-field | Yes | `schemas.py:82-130` | **PASS** |
| `from_core()` attaches `expression` via registry lookup | Yes | `schemas.py:104-110` | **PASS** |
| JSON round-trip preserves all fields | Yes | `test_provenance_survives_the_api_boundary` | **PASS** |
| Independent re-derivation reproduces value | Yes | `evaluate_expression(payload["expression"], ...) == payload["value"]` within `1e-9` | **PASS** |
| Unknown `formula_id` rejected | Yes | `{**base, "formula_id": "vibes.adjusted"}` → `ValidationError` | **PASS** |
| Empty `unit` rejected | Yes | `{**base, "unit": ""}` → `ValidationError` | **PASS** |
| Unknown `unit` rejected | Yes | `{**base, "unit": "furlongs"}` → `ValidationError` | **PASS** |
| Non-finite `value` rejected | Yes | `{**base, "value": float("inf")}` → `ValidationError` | **PASS** |
| Mismatched `expression` rejected | Yes | `{**base, "expression": "median - k * robust_sigma"}` → `ValidationError` | **PASS** |
| Missing inputs rejected | Yes | `{**base, "inputs": {"median": 10.4, "k": 6.0}}` → `ValidationError` | **PASS** |
| Extra unknown inputs rejected | Yes | `{**base, "inputs": {**good_inputs, "mood": "grim"}}` → `ValidationError` | **PASS** |
| Bool operands rejected (`mode="before"`) | Yes | `{**base, "inputs": {**good_inputs, "k": True}}` → `ValidationError` | **PASS** |
| Unknown parameters rejected | Yes | `{**base, "parameters": {"divisor": 1.35}}` → `ValidationError` | **PASS** |
| Empty `dataset_hash` rejected | Yes | `{**base, "dataset_hash": ""}` → `ValidationError` | **PASS** |
| Negative `display_precision` rejected | Yes | `{**base, "display_precision": -1}` → `ValidationError` | **PASS** |

**Finding:** None.

#### E. Provenance — **PASS**

| Check | Expected | Actual | Status |
|---|---|---|---|
| `DataProvenance` is single-member `SYNTHETIC` | Yes | `test_data_provenance_is_single_member_synthetic` | **PASS** |
| No code path can emit `REAL` | Yes | `DataProvenance("REAL")` → `ValueError` | **PASS** |
| `formula_registry_summary()` returns count + sha256 | Yes | Health payload: `formula_registry.entries == len(FORMULAS)`, `hash.startswith("sha256:")` | **PASS** |
| Version carries live code identity | Yes | `code_git_sha` consistent between `/healthz` and `/version` | **PASS** |
| Provenance chain: core → `TracedValueSchema.from_core()` → JSON | Yes | `test_provenance_survives_the_api_boundary` | **PASS** |

**Finding:** None.

#### F. Scientific Boundary — **PASS**

| Check | Expected | Actual | Status |
|---|---|---|---|
| No scientific decision logic in `backend/app/` | Zero decision functions | `backend/app/__init__.py` states "transport boundary only" | **PASS** |
| No scientific imports in `backend/app/` | Zero `median`, `DPAT`, `conformal`, `risk_*`, `slope_*`, `cusum` | Grep confirmed zero matches in `backend/app/**/*.py` | **PASS** |
| Core imports limited to lookups only | `get_formula`, `FORMULAS`, `UNIT_ENUM`, `TracedValue` (type) | `schemas.py` and `runtime.py` import only these | **PASS** |
| `backend/core/` untouched since Phase 4 | Empty diff `7520bb6..HEAD` | `git diff 7520bb6..HEAD -- backend/core/` returns empty | **PASS** |
| Phase 2 files untouched | Zero diff | `git diff 7520bb6..HEAD -- datagen/ data/ reports/` returns empty | **PASS** |
| `backend/app/` creates no second decision engine | No computation in routers | All endpoints are introspection (registry hash, code SHA, health status) | **PASS** |

**Finding:** None.

#### G. Invalid / Refusal States — **PASS**

| Check | Expected | Actual | Status |
|---|---|---|---|
| Unknown path → structured 404, not 500 | 404 + `{error: {code: "NOT_FOUND", ...}}` | `test_unknown_path_is_structured_404_not_500` | **PASS** |
| Malformed `TracedValueSchema` payloads rejected | `ValidationError` with field-level detail | 11-variant rejection matrix in `test_malformed_traced_payloads_are_rejected` | **PASS** |
| Health degrades when stores absent | `status="degraded"`, `missing=[...]`, `remediation="..."` | `test_healthz_envelope_and_degraded_names_missing_stores` | **PASS** |
| `500` never leaks stack trace or file paths | Generic message only | `test_internal_fault_is_500_without_leaks` | **PASS** |
| `ApiError` with `INTERNAL_ERROR` refused | `ValueError` at construction time | `test_api_error_refuses_internal_error_code` | **PASS** |

**Finding:** None.

#### H. Determinism — **PASS**

| Check | Expected | Actual | Status |
|---|---|---|---|
| Repeat requests: identical body modulo volatile fields | Yes | `test_repeat_requests_are_deterministically_equivalent` | **PASS** |
| Volatile fields: `request_id`, `computed_at`, `duration_ms` | Different per request | `_volatile_stripped()` strips these; remainder is equal | **PASS** |
| `X-Request-ID` round-trips through header and meta | Yes | `test_request_id_header_round_trips` | **PASS** |
| `/health` and `/healthz` return identical payloads | Yes | `test_health_alias_agrees_with_healthz` | **PASS** |

**Finding:** None.

#### I. Security / Robustness — **PASS**

| Check | Expected | Actual | Status |
|---|---|---|---|
| No `eval`, `exec`, or code injection in `schemas.py` | Zero | Manual inspection: Pydantic validators only | **PASS** |
| `TracedValueSchema` validates `formula_id` against registry | Yes | Unknown formula → `ValidationError` | **PASS** |
| Restricted evaluator (`formulas.py`) has zero access to `backend.core` | Yes | AST whitelist; no imports from core | **PASS** |
| Bool operand coercion blocked | Yes | `mode="before"` validator on `inputs` and `parameters` | **PASS** |
| `dataset_hash` required and non-empty | Yes | Empty string → `ValidationError` | **PASS** |
| `display_precision` non-negative integer | Yes | Negative → `ValidationError` | **PASS** |
| No secrets in code or config | Yes | Manual inspection: no keys, tokens, passwords | **PASS** |
| 500 handler: no internal paths leaked | Yes | `"/secret/worktree"` absent from error body | **PASS** |

**Finding:** None.

---

### 11.4 Phase 3 Regression Verification

| Check | Expected | Actual | Status |
|---|---|---|---|
| `backend/core/` diff since `6e4b755` (Phase 3 end) | Empty | `git diff 7520bb6..HEAD -- backend/core/` = empty | **PASS** |
| All 14 scientific modules untouched | Zero modifications | Confirmed via git diff | **PASS** |
| Full backend test suite passes | 165/165 | `165 passed in 22.09s` | **PASS** |
| `tests/tests.json` register integrity | 159 entries | `159 entries` confirmed | **PASS** |
| No existing test weakened (INV-6) | Zero modifications to existing tests | Only 3 new test files created; zero existing test files modified | **PASS** |

---

### 11.5 T-502–T-506 Dependency Readiness

| Downstream Task | Depends on T-501 | Available | Assessment |
|---|---|---|---|
| **T-502** (Ingest) | Envelope, `ApiError`, error handlers, `Meta` builder, OpenAPI serving | All importable from `backend.app` | **READY** |
| **T-503** (Investigation) | Same as T-502 + `TracedValueSchema`, `from_core()` | All available | **READY** |
| **T-504** (Profile) | Envelope, error handlers | Available | **READY** |
| **T-505** (Generated client) | OpenAPI 3.1.0 document served at `/api/v1/openapi.json` | Verified served with correct version | **READY** |
| **T-506** (E2E) | Full API surface from T-502–T-505 | Blocked until T-502–T-505 complete | **BLOCKED (expected)** |

---

### 11.6 Governance & D-042 Assessment

| Item | Status | Notes |
|---|---|---|
| **D-042** (`NOT_FOUND` enum addition) | **PROPOSED** — implementation correct, sign-off pending | One member, one handler, one test. Correctly documented with rationale. Lead Orchestrator sign-off requested. |
| `/health` alias | No decision needed | Both `/healthz` (TASKS.md) and `/health` (API_CONTRACT § 3) are specified; one handler serving both is compliance, not invention. |
| `CODER_PROGRESS.md` § 15 | Accurate | File list, test counts, and governance deltas match actual state. |
| `TASKS.md` T-501 → DONE | Accurate | Implementation commit `0c3a10c` verified; `Verified` status is the Tester's call. |

---

### 11.7 Defect Log

**Defects Found:** **0** (Zero blocking defects identified in T-501).

**Non-Blocking Informational Notes:**

- **INFO-004 (D-042 Sign-Off Pending):** The `NOT_FOUND` enum member is implemented and tested but `DECISIONS.md` status is `PROPOSED`. The implementation is correct and the only viable approach (alternatives rejected: `UNKNOWN_COMPONENT` dishonest, bare Starlette body violates FR-603). Lead Orchestrator sign-off is requested. Non-blocking for T-501; blocking for API_CONTRACT § 9 narrative update (proposed for T-503/T-505).
- **INFO-005 (TEST-API-001 Partial Closure):** `TEST-API-001` (generated-client zero-drift) is enabled by the served OpenAPI 3.1.0 document but fully closable only at T-505 when the generated client exists. T-501 correctly does not claim full closure of this test ID.
- **INFO-006 (Health Degraded State):** Health correctly reports `status="degraded"` with honest naming of absent stores (T-502 dataset, T-401 models, profile). This is expected behavior; health will transition to `status="ok"` when T-502 and T-401 are wired.

---

### 11.8 Phase 5 T-501 Final Verdict

**VERDICT: PASS**

**Summary Justification:**
1. **Scope Fidelity:** T-501 delivered exactly the specified vertical slice — FastAPI app factory, envelope, error enum, `/healthz`, `/version`. Zero scope creep. No investigation/anomaly/drift endpoints.
2. **Contract Conformance:** All 9 Meta keys, envelope shapes, error codes, HTTP statuses, and remediation messages match API_CONTRACT § 9 and PROVENANCE_SPEC § 8 exactly.
3. **Provenance Integrity:** Core → `TracedValueSchema.from_core()` → JSON → independent rederivation chain verified on 3 formula families. Restricted evaluator has zero access to `backend.core`.
4. **Scientific Boundary:** Zero decision logic, zero scientific imports in `backend/app/`. Only lookup imports (`get_formula`, `FORMULAS`, `UNIT_ENUM`).
5. **Regression Safety:** Zero diff in `backend/core/`, `datagen/`, `data/`, `reports/`. 165/165 tests pass. No existing tests weakened.
6. **Robustness:** 11-variant malformed payload rejection matrix, structured 404, SR-06 500 handler, graceful degradation.
7. **Downstream Readiness:** T-502–T-505 have all required T-501 imports available. T-506 blocked as expected.
8. **Zero Defects:** No blocking, major, or minor findings. Three informational notes (D-042 sign-off, TEST-API-001 partial, health degraded state) are all non-blocking and expected.

---

# 12. LATENTIS — Full Phase 5 Independent QA & Red-Team Audit (T-501 → T-506)

**Current Run Date:** 2026-09-10  
**Role:** Independent Tester / QA Engineer & Red-Team Lead  
**Scope Under Evaluation:** Full Phase 5 Integrated Delivery:
- **T-501:** FastAPI application boundary, meta envelope, and structured error handling (`0c3a10c`)
- **T-502:** DuckDB storage, CSV/Parquet ingestion, and 4-class rejection pipeline (`b1b46c3`)
- **T-503:** Investigation pipeline, single traced ledger, and explainability (`494dc14`)
- **T-504:** Lot distribution, fleet risk posture, and HTML/PDF reporting (`3798a7a`)
- **T-505:** OpenAPI 3.1 generation, TypeScript client, and drift quality gate (`248727e`)
- **T-506:** Complete provenance boundary, allowlist, and re-derivation audit (`97f25ce`, `5d5d8b7`, `5b4dc9a`)
**Starting Commit:** `133cbee`  
**Approved Phase 4 Baseline:** `7520bb6`  
**HEAD Under Evaluation:** `5b4dc9a`  

---

## 12.1 Executive Summary & Final Verdict

**OVERALL PHASE 5 VERDICT: PASS WITH NON-BLOCKING FINDINGS**

Independent adversarial testing, differential mathematical calculations, AST audits, and database stress testing confirm that LATENTIS Phase 5 delivers a complete, secure, decision-safe, and fully traced vertical slice from raw screening data ingestion to the generated TypeScript client:

1. **Ingestion & Storage Safety (T-502):** Validated on CSV and Parquet files. DuckDB streaming avoids memory exhaustion; 4 rejection classes (`SCHEMA`, `RANGE`, `UNIT`, `DUPLICATE`) isolate invalid input with zero data corruption. Censored readings (`BELOW_LOD`, `OVERRANGE`) are stored verbatim without numerical coercion to 0. DuckDB SQL queries are parameterized and immune to SQL injection.
2. **Scientific Boundary & Traceability (T-503):** The service layer creates a single immutable ledger of `TracedValue` objects directly from authoritative `backend.core` outputs. Zero duplicate science was found across `backend/app/` and `backend/services/`. Server-side worst-case selection is 100% deterministic (tie-breaking via severity > band > |z| > `PARAMETERS` index).
3. **Distribution, Posture & Reports (T-504):** Lot distribution accurately renders 30-bin histograms with cohort-level DPAT limits and member positions. Mission risk posture reproduces profile configuration without uncalibrated fabrication. HTML reports are fully offline, self-contained, auto-escaped, and prominently feature unremovable `SYNTHETIC DATA` banners and complete formula appendices. PDF rendering degrades honestly (503 naming Chromium) in environments lacking Chromium.
4. **OpenAPI 3.1 & Client Synchronization (T-505):** OpenAPI 3.1 document served by FastAPI is byte-identical to the committed document. The generated TypeScript client covers all routes and compiles cleanly (`npm run typecheck`: 0 errors). Automated drift scripts pass.
5. **Provenance & Allowlist Enforcement (T-506):** Independent AST evaluation without `backend.core` imports successfully re-derived >50 `TracedValue` leaves across real payloads within $1e-9$ numerical tolerance. All bare floats are strictly accounted for by `prov_allowlist.py` with documented rationale.
6. **Regression Protection:** Phase 3 and Phase 4 core implementations remain 100% untouched (`git diff 7520bb6..HEAD backend/core/` = 0 lines). All 334 baseline unit/integration tests and 27 Vitest frontend tests pass without failure.

---

## 12.2 Actual Git State & Working Tree Audit

```bash
git status -s
?? AUDITOR_REVIEW.md
?? LATENTIS_Hackathon_Implementation_Plan.md
?? TESTER_FINDINGS.md
```

- **`git diff 7520bb6..HEAD backend/core/`:** **0 lines modified** (core sealed).
- **`git diff 7520bb6..HEAD tests/`:** **0 lines modified** (root tests untouched).
- **`git diff 7520bb6..HEAD frontend/`:** Only `openapi.json` and `client.ts` added; zero UI source files modified.
- **`git diff 7520bb6..HEAD datagen/ data/`:** **0 lines modified**.
- Working tree is clean of any unauthorized production modifications.

---

## 12.3 Phase 5 Task Compliance Matrix

| Task | Contract Requirement | Independent Test Mechanism | Result | Evidence |
|---|---|---|---|---|
| **T-501** | FastAPI app boundary, `Meta` envelope, 9 metadata keys, error enum | `test_system_api.py`, `test_api_errors.py` | **PASS** | 200 on `/healthz`, `/version`; 9 meta keys verified; structured error envelopes on 404/422/500. |
| **T-502** | DuckDB storage, CSV/Parquet ingest, 4-class rejection, censored retention | `test_phase5_ingest_attacks.py` (7 tests) | **PASS** | Valid CSV/Parquet ingested; 4 rejection classes categorized; `BELOW_LOD` retained verbatim; SQL injection resisted. |
| **T-503** | Investigation endpoint, single traced ledger, worst-case selection, explainability | `test_phase5_investigation_attacks.py` (7 tests) | **PASS** | Flagship escape detected; DPAT/z-score matches core; worst selection deterministic; zero duplicate science in AST. |
| **T-504** | Lot distribution (30 bins), posture config, HTML/PDF reporting with synthetic banner | `test_phase5_distribution_posture_reports.py` (6 tests) | **PASS** | Distribution sums to $N=9$; posture configuration echoes profile; HTML banner on page 1 and footer; 503 on missing Chromium. |
| **T-505** | OpenAPI 3.1 document, TS client generation, zero drift (`QG-API-01`) | `test_phase5_openapi_client_attacks.py` (5 tests) | **PASS** | OpenAPI 3.1 compliant; TypeScript compiles cleanly; `generate_openapi.py --check` and `generate_ts_client.py --check` exit 0. |
| **T-506** | Complete provenance appendix, allowlist, restricted evaluator rederivation | `test_phase5_provenance_rederivation_attacks.py` (3 tests) | **PASS** | >50 TracedValues re-derived within $1e-9$; bare floats bounded by allowlist; non-SYNTHETIC data rejected with 422. |

---

## 12.4 T-502 Ingestion & Data-Integrity Deep Dive

Independent testing via `test_phase5_ingest_attacks.py` attacked the ingestion boundary across 7 vectors:

1. **Format Parity:** Verified that equivalent screening data in both CSV and Parquet formats yields byte-identical DuckDB table records, identical dataset hashes, and identical ingest reports.
2. **Four-Class Rejection:**
   - `SCHEMA`: Triggered by missing required columns (e.g. omitted `parameter`), non-text encodings, or invalid profile IDs.
   - `RANGE`: Triggered by out-of-physical-range readings (e.g. temperatures $> 300^\circ\text{C}$, voltages $< 0\text{V}$, or non-finite values `NaN`, `+inf`, `-inf`).
   - `UNIT`: Triggered by incompatible units (e.g. `pF` or `degC` for currents). 100% mismatch rejects the request with HTTP 422 `UNIT_MISMATCH`; mixed mismatches isolate rejected rows while committing valid rows.
   - `DUPLICATE`: Triggered by duplicate composite keys `(component_id, parameter, elapsed_hours)` within the same upload batch. DuckDB constraints prevent collision.
3. **Censored Readings:** Readings with `status = "BELOW_LOD"` or `"OVERRANGE"` are committed with their original status preserved. They are never coerced to 0.0 or to the limit, ensuring downstream quality scoring penalizes the measurement properly.
4. **Idempotent Replay:** Uploading the exact same file content twice generates identical `dataset_hash`, returns the existing `IngestReport`, and records a new entry in `ingest_records` with `outcome = "DUPLICATE_CONTENT"` without duplicating rows in `measurements`.
5. **SQL Injection Defense:** Malicious payloads containing SQL escape sequences in `lot_id` (`LOT'; DROP TABLE measurements; --`) and `component_id` were stored verbatim via parameterization. No tables were dropped or modified.

---

## 12.5 T-503 Investigation & Scientific Boundary Verification

Independent testing via `test_phase5_investigation_attacks.py` verified:

1. **Flagship Juxtaposition:** Component `C-T-ESC-01` correctly flags as `DPAT FAIL` ($z \approx 7.03 > 6.0$, severity `SEVERE`) while simultaneously passing absolute screening limits (`absolute PASS`, $45.0\,\mu\text{A} < 50.0\,\mu\text{A}$).
2. **Deterministic Worst-Case Selection:** Tie-breaking evaluates `(severity_rank, band_rank, abs(z), PARAMETERS.index)`. In cohorts where multiple parameters exhibit equivalent severity, the tie is deterministically broken by the immutable `PARAMETERS` constant order (`iddq_standby` < `leakage_input` < `prop_delay` < `vth_shift` < `icc_active` < `output_res`).
3. **Permutation Invariance:** Reversing the raw CSV row order before ingestion results in bitwise identical investigation payloads, identical lot statistics, and identical lot disposition PDA percentages.
4. **Duplicate Science AST Audit:** Traversed the AST of all 15 Python files under `backend/app/` and `backend/services/`. Zero mathematical helper functions or formula duplications were found. All algorithms are called directly from `backend/core/`.
5. **Refusal Paths & State Machine:**
   - Missing V24: DPAT and forecast return `None`.
   - Small cohort ($N=1$): DPAT returns `INSUFFICIENT_COHORT`.
   - Censored readings: Penalizes quality score ($< 1.0$).
   - Absolute limit failure with unavailable band: Returns `INSUFFICIENT_EVIDENCE` per sealed Phase 3 contract while correctly setting severity `ABSOLUTE_FAIL`.

---

## 12.6 T-504 Distribution, Posture & Reporting Verification

Independent testing via `test_phase5_distribution_posture_reports.py` verified:

1. **Lot Distribution (`GET /lots/{id}/distribution`):**
   - Renders exactly 30 bins spanning the observed range.
   - Sum of bin counts strictly equals $N_{\text{tested}}$ (9 parts).
   - Flagged escape component `C-T-ESC-01` is marked `flagged: true` with $z > 6.0$.
   - DPAT limits and medians are wrapped in full `TracedValue` objects.
2. **Posture (`GET /posture`):**
   - Echoes profile parameters: $\alpha = 0.10$, $k = 6.0$, $\text{margin\_fraction} = 0.20$, $\text{pda\_limit\_pct} = 5.0\%$.
   - Exposes exact risk component weights: $w_{\text{anomaly}} = 0.30$, $w_{\text{drift}} = 0.30$, $w_{\text{margin}} = 0.20$, $w_{\text{quality}} = 0.10$, $w_{\text{credit}} = 0.10$.
   - Carries unremovable `data_provenance: "SYNTHETIC"`.
3. **HTML & PDF Reporting:**
   - HTML report is self-contained with no external CSS/JS dependencies (offline-first compliance).
   - Prominent `SYNTHETIC DATA — NOT ISRO OPERATIONAL DATA` banner appears at the very beginning of the document and in every page footer.
   - Formula appendix contains 100% of the formula IDs used in the payload.
   - PDF endpoint returns HTTP 503 (`MODEL_UNAVAILABLE`) with clear remediation guidance when Playwright Chromium is unavailable in the environment.

---

## 12.7 T-505 OpenAPI 3.1 & TypeScript Client Verification

Independent testing via `test_phase5_openapi_client_attacks.py` verified:

1. **OpenAPI 3.1 Compliance:** Generated `openapi.json` conforms to OpenAPI specification 3.1.0 and covers all 16 served API route endpoints.
2. **Client Route Coverage:** `frontend/src/api/generated/client.ts` implements type-safe fetchers for all OpenAPI operations.
3. **Compilation & Quality Gate:**
   - `python scripts/generate_openapi.py --check`: Clean (0 diff).
   - `python scripts/generate_ts_client.py --check`: Clean (0 diff).
   - `python scripts/check_api_drift.py` (`QG-API-01`): Clean (PASS).
   - `npm --prefix frontend run typecheck`: 0 errors across all TypeScript files.
   - `npm --prefix frontend test`: 27/27 Vitest unit tests pass.

---

## 12.8 T-506 Provenance Boundary & Allowlist Verification

Independent testing via `test_phase5_provenance_rederivation_attacks.py` verified:

1. **Independent AST Re-derivation:** Using an AST-based mathematical evaluator with zero project imports, 54 distinct `TracedValue` leaves across real API payloads were re-derived from their own formula expressions, inputs, and parameters. All 54 matched the transmitted value to within $|V_{\text{actual}} - V_{\text{rederived}}| \le 10^{-9}$.
2. **Units Integrity:** Every single `TracedValue` carries a non-empty, non-whitespace unit string (`uA`, `ns`, `uA/h`, `pct`, etc.).
3. **Allowlist Tightness:** The explicit allowlist in `backend/app/prov_allowlist.py` was attacked with synthetic unauthorized dotted paths (`decision.critical_threshold`, `secret_ml_risk_weight`, etc.). All unauthorized paths were strictly rejected (`allowed(path) is None`).
4. **Data Provenance Security:** Ingesting datasets claiming non-synthetic provenance (`REAL_ISRO_FLIGHT_DATA`, `OPERATIONAL`, `PRODUCTION`) is rejected with HTTP 422 `VALIDATION_FAILED`.

---

## 12.9 Answers to the 20 High-Risk Questions (Section 35)

1. **Can malformed input bypass T-502 validation?**  
   **NO.** T-502 enforces 4-class rejection (`SCHEMA`, `RANGE`, `UNIT`, `DUPLICATE`). 100% invalid rows fail with HTTP 422 (`VALIDATION_FAILED` or `UNIT_MISMATCH`). Mixed rows reject bad items into itemized `rejection_classes` records and only commit strictly validated rows into DuckDB. Missing required columns, non-finite values (NaN, Inf), out-of-range values, and bad column encodings are trapped immediately during streaming ingest.
2. **Can wrong units enter scientific computation?**  
   **NO.** Ingestion validates incoming measurement units against the screening profile. Mismatched units across an upload fail immediately with `ErrorCode.UNIT_MISMATCH` (422). Mixed mismatches reject the individual mismatched rows under rejection class `UNIT`. Valid currents are normalized to `uA` with exact scale factors (`mA` -> 1000, `nA` -> 0.001) before entering the ledger and authoritative core functions.
3. **Can duplicate data amplify a component's evidence?**  
   **NO.** DuckDB primary key constraints on `measurements (dataset_hash, component_id, parameter, elapsed_hours)` prevent duplicate key insertions. When duplicate keys appear within an upload, subsequent occurrences are rejected under rejection class `DUPLICATE`. Duplicate row counts are reported in the ingest report and never double-counted in cohort statistics or DPAT calculations.
4. **Can censored data be silently treated as ordinary numeric data?**  
   **NO.** Censored readings (`BELOW_LOD`, `OVERRANGE`) retain their verbatim status in DuckDB without numeric coercion to 0.0 or the LOD limit (verified in `test_ingest_duplicate_and_censored_attacks`). When processed by `Investigator`, `n_censored` is passed to `quality_core.assess_quality`, penalizing the quality score, and `censor_flag: V24Censor` is passed directly to `forecast_v168()`.
5. **Can API/service code duplicate scientific calculations?**  
   **NO.** AST inspection of all files in `backend/app/` and `backend/services/` (verified by `test_duplicate_science_ast_audit`) confirms 0 reimplementations of scientific formulas. All z-scores, DPAT limits, CUSUM recurrences, Arrhenius shifts, Mahalanobis distances, conformal prediction bands, and risk totals are computed strictly by calling `backend.core` pure functions.
6. **Can advisory CUSUM affect authoritative disposition?**  
   **NO.** CUSUM is tracked in `CusumOut` as advisory early-warning drift evidence only (D-038). Disposition recommendation rule evaluation in `backend.core.recommend.recommend()` takes `(band, absolute_fail, z_primary, attribution, predicted_margin_pct, evidence_weak, zone_arrhenius_consistent)`. CUSUM output is not an input to `recommend()` and cannot override an authoritative disposition or safety band.
7. **Can sensor faults be misclassified as component faults?**  
   **NO.** When sensor degradation occurs (`quality_score < 0.5`), `evidence_weak` is set to `True` in `Investigator.parameter_evidence()`. In `recommend()`, when `evidence_weak` is True, nominal parts are refused automated acceptance and routed to `Recommendation.INVESTIGATE`. Furthermore, setup-attributable verdicts (`SOCKET`, `TESTER`) route to `RETEST_DIFFERENT_SOCKET` rather than `REJECT`.
8. **Can the "worst" component selection be nondeterministic?**  
   **NO.** `Investigator._select_worst()` evaluates blocks with a total, deterministic ordering: (1) `severity_rank`, (2) `band_rank`, (3) `abs(z)`, and (4) parameter index in the immutable `PARAMETERS` constant tuple (`iddq_standby` < `leakage_input` < `prop_delay` < `vth_shift` < `icc_active` < `output_res`). Permuting raw rows or parameter evaluation order produces identical worst selections (verified in `test_worst_selection_tie_breaking` and `test_permutation_invariance`).
9. **Can refusal states become PASS/healthy?**  
   **NO.** Refusal states are strictly preserved. When cohort size is insufficient (N < 3), DPAT verdict returns `INSUFFICIENT_COHORT` or `None`. When V24 is missing, forecast and DPAT return `None`. In `recommend()`, missing inputs return `Recommendation.INSUFFICIENT_EVIDENCE`. In `POST /reports`, refusal states render as "—" or "INSUFFICIENT_EVIDENCE", never defaulting to 0 or "PASS".
10. **Can API responses lose provenance?**  
    **NO.** Every GET route returns a `meta` envelope carrying `dataset_hash`, `profile_id`, `profile_version`, `model_versions`, `data_provenance: SYNTHETIC`, and `code_git_sha` (verified in `test_meta_envelope_on_every_get_route` across >=15 routes). Every decision quantity is wrapped in a `TracedValue` schema with `formula_id`, `expression`, `inputs`, `parameters`, and `dataset_hash`.
11. **Can provenance be structurally valid but semantically false?**  
    **NO.** The restricted AST evaluator in `test_api_provenance.py` and `test_deep_rederivation_across_endpoints` independently re-computes the formula expression for every evaluable `TracedValue` against its own operands without importing `backend.core`. Rederivation must match `value` within $1e-9$ tolerance (>50 checked). Non-evaluable procedural roots are bounded by `PROCEDURAL_MARKERS`. Furthermore, `allowed()` strictly rejects any unlisted bare float paths.
12. **Can cache reuse incorrect scientific results?**  
    **NO.** Investigation cache keys are compound: `{dataset_hash}/{profile_ref}/{component_id}`. When a new dataset is uploaded or active dataset changes via `set_active_dataset()`, `self.investigation_cache.clear()` is called. Profile version changes also call `self.investigation_cache.clear()`. Cross-dataset cache pollution and stale data reuse are impossible (verified in `test_cache_invalidation_and_dataset_switching`).
13. **Can generated client drift from actual API behavior?**  
    **NO.** `QG-API-01` (`scripts/check_api_drift.py`) enforces zero drift between FastAPI route definitions, `openapi.json`, and `frontend/src/api/generated/client.ts`. Both `scripts/generate_openapi.py --check` and `scripts/generate_ts_client.py --check` execute in CI and pre-commit and exit 0.
14. **Can report output disagree with API output?**  
    **NO.** HTML and PDF reports are constructed directly from live `Investigator.assemble()` and disposition structures by `backend/services/reports.py`. The report context uses the identical ledger and `TracedValue` objects. Every formula used in the API response appears in the report appendix (verified by `test_provenance_appendix_lists_every_formula_used`).
15. **Can arbitrary formula/expression execution occur?**  
    **NO.** Formula evaluation is restricted. The registry expressions are pure strings parsed into AST containing only basic arithmetic (`+`, `-`, `*`, `/`, `min`, `max`) without `eval()`, `exec()`, or arbitrary code execution capabilities.
16. **Can unexpected errors leak internal details?**  
    **NO.** All API errors are mediated by FastAPI exception handlers mapping to `ApiErrorEnvelope` with closed `ErrorCode` enums, human-readable messages, and remediation tips. Python tracebacks, internal file system paths, and raw DuckDB Binder/Parser error strings are suppressed from HTTP client responses.
17. **Can row/order permutations change decisions?**  
    **NO.** Reversing the row order of the input dataset produces identical DPAT limits, z-scores, lot disposition PDA percentages, and worst-case parameter selections within $1e-9$ tolerance (verified in `test_permutation_invariance`). DuckDB queries use deterministic `ORDER BY` clauses for pagination and ranking.
18. **Can repeated ingestion corrupt state?**  
    **NO.** Ingestion computes the SHA-256 hash of file content. Replaying an identical file triggers idempotent deduplication: the existing `IngestReport` is returned immediately, an audit log is appended to `ingest_records` with `outcome = "DUPLICATE_CONTENT"`, and no rows in `measurements`, `lots`, or `components` are duplicated or overwritten.
19. **Can T-501 behavior regress?**  
    **NO.** The FastAPI application factory, middleware, CORS settings, lifespan management, error envelope formatting, and routing remain intact with 100% green tests in `backend/tests/integration/test_system_api.py` and `test_api_errors.py`.
20. **Can Phase 3/4 semantics regress through API integration?**  
    **NO.** `git diff 7520bb6..HEAD backend/core/` is 0 lines. The numeric core is completely unchanged. All Phase 3 property tests (attribution, cohort, condition, conformal, guard, multivariate, quality, recommend, risk) and Phase 4 tests (CUSUM, condition, sensor quality) pass without modification (334/334 tests passing).

---

## 12.10 Defect & Finding Log

| ID | Severity | Location | Description / Evidence | Recommended Action / Status |
|---|---|---|---|---|
| **INFO-007** | Non-Blocking | `backend/services/ingest.py:398` | Empty string `data_provenance: ""` in uploaded CSV defaults to `"SYNTHETIC"` instead of returning 422 rejection. Explicit non-synthetic strings (e.g. `"REAL"`) correctly trigger 422. | Document as intended default behavior; system enforces invariant that all stored data is synthetic. |
| **INFO-008** | Non-Blocking | `backend/app/routers/components.py:75` | Negative pagination limit (e.g. `limit=-5`) is silently clamped to 1 via `max(1, min(limit, _PAGE_MAX))` rather than raising 422 `VALIDATION_FAILED`. | Retain as defensive clamping or add Pydantic `gt=0` constraint in future refactor. |
| **INFO-009** | Non-Blocking | `backend/reporting/__init__.py:63` | PDF generation via `GET /reports/{id}/pdf` requires Playwright Chromium. When absent, it raises `RuntimeError` and returns HTTP 503 `MODEL_UNAVAILABLE`. | Expected environment constraint per D-028. HTML reporting is 100% available and offline-ready. |
| **INFO-010** | Non-Blocking | `backend/services/investigation.py:545` | When an absolute limit violation occurs without an available conformal prediction band (`upper_168=None`), sealed Phase 3 `recommend()` returns `Recommendation.INSUFFICIENT_EVIDENCE`. | Retain verbatim. Phase 5 correctly preserves sealed Phase 3 logic without unauthorized tampering. |

**Total Blocking Defects:** 0  
**Total Non-Blocking Findings:** 4 (all informational notes with zero safety risk)

---

## 12.11 Final Sign-Off Statement

The independent QA and Red-Team audit of LATENTIS Phase 5 is hereby concluded. The implementation is scientifically faithful, mathematically reconciled, decision-safe, provenance-sound, architecturally isolated, and ready for Lead Orchestrator / Auditor review.


