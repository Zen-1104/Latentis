# TEST_STRATEGY.md — What We Test, and Why Those Things

**Owner:** QA & Playwright Engineer + all implementing agents · Implements TR-01..TR-10
**Governing rule:** INV-6 — a failing test is fixed in the *implementation*. Changing a test requires a
`DECISIONS.md` entry with justification and the Lead Orchestrator's sign-off.

## 1. What a test must be worth

A test that asserts an implementation against itself is worse than no test: it consumes time and creates
false confidence. So every test in this project must fall into one of five categories, and the category is
recorded in `tests/tests.json`:

| Category | The test's oracle | Example |
|---|---|---|
| **Known-answer** | A value computed by hand, or from a published worked example | `TEST-STAT-001`: quartiles of a 9-value list, hand-computed under the type-7 convention |
| **Property** | A mathematical invariant that must hold for all inputs (Hypothesis) | Median is invariant to permutation; MAD is scale-equivariant |
| **Behavioural contract** | A row of a specification table | Every row of `ANOMALY_SPEC § 9` degenerate cases |
| **Differential** | Two independent computations of the same quantity must agree | Mahalanobis contributions sum to `D²`; risk components sum to the total |
| **Adversarial** | An input designed to break a stated claim | `RT-004` ID permutation; injected lot shift vs. the exchangeability guard |

Explicitly **not** acceptable as the only coverage for a numeric function: a snapshot of whatever the code
currently outputs. Snapshot tests are permitted for *rendering structure* and are banned for *numeric
results*.

## 2. The pyramid, with real proportions

```
                  ┌────────────────────────────────┐
                  │  RT-001..RT-012  red team      │   12 adversarial suites
                  ├────────────────────────────────┤
                  │  E2E (Playwright)              │   ~20 specs, 5 journeys
                  ├────────────────────────────────┤
                  │  Integration (API + DuckDB)    │   ~60
                  ├────────────────────────────────┤
                  │  Property (Hypothesis)         │   ~35   ← the load-bearing tier
                  ├────────────────────────────────┤
                  │  Unit (pure numeric core)      │  ~220
                  └────────────────────────────────┘
```

The unusual weighting is the property tier. For robust statistics, property tests are how correctness is
*proved* rather than sampled: a hand-computed example shows the code works on one input; a property test
over thousands of generated cohorts shows the estimator has the mathematical behaviour it claims.

## 3. Property tests — the specific invariants

Written with Hypothesis, each with a shrinking-friendly strategy over cohort arrays.

| Property | Applies to | Why it catches real bugs |
|---|---|---|
| Permutation invariance | every cohort statistic | Catches accidental dependence on input order — the same class of bug as INV-2 |
| Scale equivariance: `f(cx) = c·f(x)` | median, IQR, MAD, robust σ | Catches unit-handling errors, the project's most likely silent failure |
| Shift equivariance: `f(x+c) = f(x)+c` | median, PAT limits | Catches baseline-handling errors |
| Translation invariance of `z` | `z_dpat`, `z_mad` | A robust distance must not move when the whole cohort shifts |
| Breakdown resistance | median/MAD vs. mean/σ | Corrupting up to 49 % of the cohort must not move the median arbitrarily; the *same* test on mean ± 3σ demonstrates masking, which is an ablation row |
| Monotone in `k` | PAT limits | Larger `k` ⇒ weakly wider window, never narrower |
| Monotone in `α` | conformal bound | Smaller `α` ⇒ weakly wider bound ⇒ weakly more rejections |
| Bound ≥ point estimate | `Û168 ≥ V̂168` | A one-sided upper bound below its own point estimate is a sign error, the classic conformal bug |
| `Φ_g(24) = 1` exactly | shape families | The normalisation the whole amplitude interpretation rests on |
| Linear degeneracy | shape model | With `Φ(168) = 7` the model must reproduce linear extrapolation exactly, to floating-point tolerance |
| Contributions sum to `D²` | Mahalanobis | Differential check on the exact decomposition |
| Risk components sum to total | risk | `RISK_SCORING_SPEC § 1` adding-up property |
| No `NaN`/`inf` on any finite input | every core function | The degenerate-case guarantee (`ANOMALY_SPEC § 9`) |
| Idempotence of unit normalisation | ingest | Normalising twice must equal normalising once |

## 4. Named test IDs by area

Full traceability in `tests/TEST_MATRIX.md`; the machine-readable register is `tests/tests.json`.

| Prefix | Area | Notable members |
|---|---|---|
| `TEST-STAT-*` | Robust statistics | `001` hand-computed quartiles (pins the type-7 convention); `002` leave-one-out; `006` adjusted-boxplot sign convention vs. Hubert & Vandervieren |
| `TEST-GEN-*` | Generator | `001` refuses to start without provenance tags; `004` **`S1 ∪ S2` non-empty and every member inside all limits**; `005` labels derived from rendered values |
| `TEST-DL-*` | Data leakage | `001` fitted feature schema equals the allow-list exactly; `002` no 96 h/168 h column in `screening.parquet`; `003` no value correlation with withheld columns |
| `TEST-CONF-*` | Conformal | `001` the `⌈(n+1)(1−α)⌉` order statistic on a tiny hand-checked set; `002` empirical coverage inside its binomial interval; `003` monotonicity in `α` |
| `TEST-NP-*` | NP threshold | `002` the order-statistic rule and its `δ`; refusal when `n_def` is insufficient |
| `TEST-ARCH-*` | Boundaries | `001` import graph: `core` imports neither `datagen` nor `app` nor any I/O module |
| `TEST-PROV-*` | Provenance | `001` units non-empty; `002` operands match the registry; `003` no bare floats on decision fields; `004` single-member provenance enum; `005` dispositions append-only |
| `TEST-EXPL-*` | Explainability | `001` no numeric literal in narrative templates; `002` registry coverage both directions; `003` counterfactual round-trip |
| `TEST-API-*` | Contract | `001` Zod/OpenAPI agreement; `004` error enum reachable both ways; `005` no `5xx` in the corpus |
| `TEST-RISK-*` | Risk | `001` components sum to total within `1e-9` |
| `TEST-SPLIT-*` | Splits | `001` train/calib/test lot-disjointness verified from the artifact, not the script |
| `TEST-A11Y-*` | Accessibility | `001` contrast, focus order, no colour-only encoding |
| `TEST-REP-*` | Reporting | `002` synthetic banner on page 1 and every footer |
| `RT-001..012` | Red team | `tests/RED_TEAM_PLAN.md` |

`TEST-GEN-004` deserves its emphasis: if it fails, the Escape Set is invalid, the flagship claim
(`LER(static) = 0` by construction) is unsupported, and the release is **blocked**. It is the single most
important test in the repository.

## 5. Test data policy

- Unit tests use **small, hand-constructed arrays** with values chosen so the answer is computable by hand
  and written in the test's docstring. No unit test loads a generated dataset.
- Property tests use Hypothesis strategies, with the seed recorded and failing examples committed to
  `tests/regressions/` as permanent known-answer cases.
- Integration and E2E tests use a **small fixed dataset** (`seed=20260930`, 6 lots) generated in CI, never
  a committed binary.
- The **test split of the evaluation dataset is off-limits** to every test except the release scoring run
  (AG-5). A test that reads `test` split truth is itself a leak.

## 6. Determinism requirements (TR-06)

Every test is deterministic. Concretely: seeded RNG passed explicitly, no wall-clock in assertions, stable
sort keys, fixed `n_jobs=1` for sklearn estimators in tests, and no reliance on dict ordering across
processes. A flaky test is treated as a **P1 defect against the implementation**, not as a test to retry,
because flakiness in a numeric pipeline usually means an unseeded path — which would also break INV-8.

## 7. Coverage targets, and what coverage does not mean

| Area | Line coverage target |
|---|---|
| `backend/core/**` (numeric core) | **≥ 95 %** |
| `backend/app/**`, `backend/services/**` | ≥ 85 % |
| `datagen/**` | ≥ 90 % |
| `frontend/src/design/**`, feature logic | ≥ 80 % |

Coverage is a **floor, not a goal**. 100 % coverage with snapshot-only assertions would satisfy the number
and prove nothing. The gate that actually matters is § 1: every numeric function has at least one
known-answer or property test, checked by a script that reads `tests/tests.json` and fails if any core
public function has no test of an acceptable category.

## 8. CI structure

```
fast   (pre-commit, < 60 s)   ruff · black --check · mypy · unit tests marked fast · eslint · tsc
full   (per push)             all unit + property + integration; coverage gates; TEST-ARCH-001
nightly / pre-release         E2E (Playwright), red-team RT-001..012, reproducibility check,
                              performance traces, PDF rendering
```

`scripts/verify_reproducibility.sh` runs in the nightly job and as a release gate: regenerate the dataset
from the recorded seed and config, compare SHA-256 hashes, retrain, compare artifact hashes, re-score,
compare metrics (INV-8). A drift here invalidates every published number, so it blocks the tag.

## 9. What is deliberately not tested

Stated so that the gaps are known rather than discovered:

- **The physical realism of the generator.** We test that it implements its documented model
  reproducibly; we do **not** test that the model matches real devices, because we have no real device
  data. `DATA_GENERATION_SPEC § 10` states this limit and `FINAL_STATUS.md` repeats it.
- **Absolute performance on real hardware.** Performance targets are measured on the development machine
  and reported as such in `reports/PERFORMANCE.md`.
- **Cross-browser rendering beyond Chromium.** Single-machine offline demo (DMR-01); Firefox/WebKit are
  out of scope and this is recorded as a known limitation rather than left implicit.
- **Multi-user concurrency.** There is no authentication and no multi-user model (SR-09). Testing
  concurrent operators would be testing a capability we deliberately do not claim.
