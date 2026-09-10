# TEST_MATRIX.md — Requirement → Test Traceability

**Owner:** QA & Playwright Engineer · Implements TR-09 · Machine-readable twin: `tests/tests.json`

**Gate:** `scripts/check_traceability.py` fails the build if any **P0** requirement in
`PROJECT_MASTER_SPEC.md` has no test ID in this matrix, or if any test ID here is absent from
`tests/tests.json`. The matrix is therefore maintained, not decorative.

**Status vocabulary** (`CLAUDE.md § 4`): `Specified` · `Implemented` · `Verified` · `Measured`.
All rows below are `Specified` at Phase 0 — no code exists yet. The status column is updated by the
owning agent as work lands, alongside the commit hash in `TASKS.md`.

## 1. Ingest & validation (FR-101..FR-108)

| Req | Requirement | Test IDs | Category | P | Status |
|---|---|---|---|---|---|
| FR-101 | Ingest CSV/Parquet in the long schema | `TEST-ING-001`, `TEST-API-003` | contract | P0 | Specified |
| FR-102 | Schema + range + enum validation, itemised by row | `TEST-ING-002`, `TEST-API-004` | contract | P0 | Specified |
| FR-103 | Missing read-point detected; no imputation of a decision input | `TEST-ING-003`, `RT-009/1` | behavioural | P0 | Specified |
| FR-104 | Duplicate `(part, param, hours)` detection; per-part/per-lot data-quality score with itemised deductions (producer: `TEST-QUAL-007`, `TEST-QUAL-008`, `TEST-QUAL-009`) | `TEST-ING-004`, `TEST-QUAL-007`, `TEST-QUAL-008`, `TEST-QUAL-009` | behavioural | P1 | Specified |
| FR-105 | Timestamp non-monotonicity tolerated and reported | `TEST-ING-005` | behavioural | P2 | Specified |
| FR-106 | DataQualityReport with per-finding `action` | `TEST-ING-006` | contract | P0 | Specified |
| FR-107 | Censored readings retained, never coerced to 0 or to the limit | `TEST-ING-007`, `RT-009/6` | adversarial | P0 | Specified |
| FR-108 | Unit validation against the profile; mismatch rejects rows | `TEST-ING-008`, `TEST-PROV-001` | known-answer | P0 | Specified |

## 2. Module A — anomaly (FR-201..FR-210)

| Req | Requirement | Test IDs | Category | P | Status |
|---|---|---|---|---|---|
| FR-201 | Leave-one-out cohort: lot + type + read-point + `status=OK` | `TEST-STAT-002` | property | P0 | Specified |
| FR-202 | Robust statistics: median, Q1, Q3, IQR, MAD, robust σ | `TEST-STAT-001`, `TEST-STAT-003` | known-answer + property | P0 | Specified |
| FR-203 | DPAT limits `median ± k·IQR/1.35`, `k` from profile | `TEST-STAT-004` | known-answer | P0 | Specified |
| FR-204 | MAD path primary when `n < 20`, with `c(n)` correction | `TEST-STAT-005`, `RT-009/2` | behavioural | P0 | Specified |
| FR-205 | Adjusted boxplot (medcouple) sign convention | `TEST-STAT-006` | known-answer | P1 | Specified |
| FR-206 | Robust Mahalanobis (MCD) + exact additive contributions | `TEST-STAT-007`, `TEST-STAT-008` | differential | P1 | Specified |
| FR-207 | Max-severity aggregation with unanimity reporting | `TEST-AGG-001` | behavioural | P0 | Specified |
| FR-208 | PART / SOCKET / ZONE / TESTER / INDETERMINATE attribution | `TEST-ATTR-001..005`, `RT-006` | behavioural | P0 | Specified |
| FR-209 | NP threshold calibrated on `calib` only; refuses if `n_def` small | `TEST-NP-001`, `TEST-NP-002` | known-answer | P0 | Specified |
| FR-210 | `ABSOLUTE_FAIL` supersedes every other verdict | `TEST-AGG-002` | behavioural | P0 | Specified |
| — | Variance-stabilising transform fitted on train only, frozen | `TEST-STAT-009`, `TEST-DL-004` | behavioural | P1 | Specified |
| — | Isolation Forest never affects a verdict | `TEST-AGG-003` | adversarial | P1 | Specified |

## 3. Module B — drift (FR-301..FR-310)

| Req | Requirement | Test IDs | Category | P | Status |
|---|---|---|---|---|---|
| FR-301 | Feature allow-list enforced; schema equality asserted | `TEST-DL-001` | adversarial | P0 | Specified |
| FR-302 | Shape–Amplitude forecast; `Φ_g(24)=1`; group shape fitted on train | `TEST-DRIFT-001..003` | property | P0 | Specified |
| FR-303 | `INSUFFICIENT_DATA` when `v0` or `v24` missing; no imputation | `TEST-DRIFT-004`, `RT-009/1` | behavioural | P0 | Specified |
| FR-304 | Residual correction adopted only if it beats the shape model | `TEST-DRIFT-005` | behavioural | P1 | Specified |
| FR-305 | One-sided conformal upper bound drives the decision | `TEST-CONF-001..003` | known-answer + property | P0 | Specified |
| FR-306 | Safety slope derived from config; delta limit takes precedence | `TEST-SAFE-001..003` | known-answer | P0 | Specified |
| FR-307 | Mondrian grouping with the documented fallback ladder | `TEST-CONF-004` | behavioural | P0 | Specified |
| FR-308 | Censored `v24` handled in the conservative direction | `TEST-DRIFT-006`, `RT-009/6` | behavioural | P1 | Specified |
| FR-309 | Arrhenius AF → equivalent field hours, `Ea` reported | `TEST-PHYS-001` | known-answer | P1 | Specified |
| FR-310 | Band assignment from `Û168`, never from `V̂168` | `TEST-SAFE-004`, `RT-005` | adversarial | P0 | Specified |
| — | Linear baseline present in every payload | `TEST-DRIFT-007` | contract | P0 | Specified |
| — | Model reduces exactly to linear when `Φ(168)=7` | `TEST-DRIFT-008` | property | P1 | Specified |

## 4. Risk, explanation, disposition (FR-401..FR-410)

| Req | Requirement | Test IDs | Category | P | Status |
|---|---|---|---|---|---|
| FR-401 | Decomposable risk; components sum to total | `TEST-RISK-001` | differential | P0 | Specified |
| FR-402 | Weights from profile, versioned; cannot cross a band boundary | `TEST-RISK-002`, `RT-010` | adversarial | P0 | Specified |
| FR-403 | Attribution credit **reduces** risk | `TEST-RISK-003` | behavioural | P1 | Specified |
| FR-404 | `risk_index` never rendered as a probability/percentage | `TEST-RISK-004`, `RT-008` | adversarial | P0 | Specified |
| FR-405 | Lot PDA roll-up; both figures reported | `TEST-RISK-005` | known-answer | P0 | Specified |
| FR-406 | Recommendation mapping with its trigger text | `TEST-REC-001..007` | behavioural | P0 | Specified |
| FR-407 | Narrative from `TracedValue`s only; no literals in templates | `TEST-EXPL-001`, `RT-007` | adversarial | P0 | Specified |
| FR-408 | Formula registry; append-only; expression shipped in payload | `TEST-EXPL-002` | contract | P0 | Specified |
| FR-409 | `OVERRIDE` requires a non-empty reason | `TEST-DISP-001` | contract | P0 | Specified |
| FR-410 | Counterfactual thresholds computed by inversion | `TEST-EXPL-003` | differential | P1 | Specified |
| — | Disposition stores the exact payload shown | `TEST-DISP-002`, `TEST-PROV-005` | contract | P0 | Specified |

## 5. Frontend (FR-501..FR-510)

| Req | Requirement | Test IDs | Category | P | Status |
|---|---|---|---|---|---|
| FR-501 | Eight surfaces reachable and routable | `E2E-NAV-001` | contract | P0 | Specified |
| FR-502 | Verdict strip shows PAT and absolute verdicts separately | `E2E-S3-001`, `RT-012` | behavioural | P0 | Specified |
| FR-503 | Ledger drawer on every number, recursive | `E2E-S3-002` | behavioural | P0 | Specified |
| FR-504 | 500 × 6 virtualised table performance | `E2E-PERF-001` | measured | P1 | Specified |
| FR-505 | Loading / empty / error / degraded states all designed | `E2E-STATE-001..004` | behavioural | P0 | Specified |
| FR-506 | Design tokens only; no raw values | `TEST-FE-LINT-001` | contract | P1 | Specified |
| FR-507 | Keyboard + WCAG 2.1 AA; no colour-only encoding | `TEST-A11Y-001` | contract | P1 | Specified |
| FR-508 | Drift chart: observed, forecast, baseline, bound, limit, slope | `E2E-S4-001` | behavioural | P0 | Specified |
| FR-509 | `α` / `margin_fraction` controls recompute server-side | `E2E-S4-002`, `RT-003` | adversarial | P0 | Specified |
| FR-510 | No mock/fixture path in the production build | `TEST-FE-ARCH-001` | adversarial | P0 | Specified |

## 6. Backend & platform (FR-601..FR-608, NFR)

| Req | Requirement | Test IDs | Category | P | Status |
|---|---|---|---|---|---|
| FR-601 | OpenAPI 3.1; Zod generated, never hand-written | `TEST-API-001` | contract | P0 | Specified |
| FR-602 | `meta` envelope on every response | `TEST-API-002` | contract | P0 | Specified |
| FR-603 | Structured errors, closed enum, `remediation` on 4xx | `TEST-API-004` | contract | P0 | Specified |
| FR-604 | `TracedValue` on every decision-bearing field | `TEST-PROV-003` | contract | P0 | Specified |
| FR-605 | Model registry with manifests; `degraded` health when missing | `TEST-REG-001`, `TEST-HEALTH-001` | behavioural | P0 | Specified |
| FR-606 | DuckDB persistence; dispositions append-only | `TEST-DB-001`, `TEST-PROV-005` | contract | P0 | Specified |
| FR-607 | Profiles immutable once referenced | `TEST-PROF-001` | behavioural | P0 | Specified |
| FR-608 | HTML/PDF report with provenance appendix and banner | `TEST-REP-001`, `TEST-REP-002` | contract | P0 | Specified |
| NFR-01/02 | Latency targets | `E2E-PERF-001..003` | measured | P1 | Specified |
| NFR-07/INV-8 | Byte-identical reproducibility | `TEST-REPRO-001` + `scripts/verify_reproducibility.sh` | differential | P0 | Specified |
| NFR-08 | Fully offline at runtime | `TEST-OFFLINE-001` | adversarial | P0 | Specified |
| NFR-12 | Transactional ingest; no partial commit | `TEST-ING-009` | adversarial | P1 | Specified |
| INV-7/MLR-08 | `core` imports no `datagen`, no `app`, no I/O | `TEST-ARCH-001` | adversarial | P0 | Specified |

## 7. Dataset (DR-01..DR-10, DATASET_SPEC § 12)

| Req | Requirement | Test IDs | Category | P | Status |
|---|---|---|---|---|---|
| DR-03 | Every generator parameter carries a provenance tag | `TEST-GEN-001` | adversarial | P0 | Specified |
| DR-04 | `S1 ∪ S2` non-empty; **all** members inside all limits | `TEST-GEN-004` | adversarial | **P0 — release blocker** | Specified |
| DR-05 | Labels derived from rendered values, not intent | `TEST-GEN-005` | behavioural | P0 | Specified |
| DR-06 | `screening.parquet` contains no 96 h/168 h derivative | `TEST-DL-002`, `TEST-DL-003` | adversarial | P0 | Specified |
| DR-07 | Report provenance appendix + banner | `TEST-REP-002` | contract | P0 | Specified |
| DR-09 | `data_provenance` is a single-member enum | `TEST-PROV-004` | adversarial | P0 | Specified |
| DR-10 | Generator cannot import the model | `TEST-ARCH-001` | adversarial | P0 | Specified |
| — | Configured imperfections present at approximately their rates | `TEST-GEN-006` | behavioural | P1 | Specified |
| — | Prevalence within ±0.5 pp of configuration | `TEST-GEN-007` | behavioural | P1 | Specified |
| — | Achieved correlations measured and published | `TEST-GEN-008` | measured | P1 | Specified |

## 8. Cross-cutting invariants

| Invariant | Test IDs |
|---|---|
| INV-1 no fabricated numbers | `RT-008`, `TEST-EXPL-001`, `TEST-FE-LINT-001`, `scripts/check_no_fabricated_numbers.sh` |
| INV-2 no hard-coded decisions | `RT-004` |
| INV-3 synthetic labelled always | `TEST-PROV-004`, `TEST-REP-002`, `E2E-BADGE-001` |
| INV-4 no leakage | `TEST-DL-001..004`, `TEST-SPLIT-001` |
| INV-5 explanations from decision values | `RT-007`, `TEST-EXPL-004` |
| INV-6 tests never weakened | Process gate: `DECISIONS.md` entry + sign-off; `scripts/check_test_deltas.sh` flags weakened assertions in review |
| INV-7 no silent cross-ownership writes | Process gate: `agents/README.md` ownership table + handoff notes |
| INV-8 reproducibility | `TEST-REPRO-001`, `scripts/verify_reproducibility.sh` |
| INV-9 no unimplemented claims | Process gate: `FINAL_STATUS.md` status vocabulary audit by `red-team-auditor` |
| INV-10 no secrets | `scripts/check_secrets.sh` (pre-commit + CI) |

INV-6, INV-7 and INV-9 are **process gates, not automated tests**, and saying so plainly is more useful
than pretending a script enforces them. `scripts/check_test_deltas.sh` is a *heuristic aid* for reviewers —
it flags diffs that loosen a numeric tolerance or delete an assertion — not a proof.
