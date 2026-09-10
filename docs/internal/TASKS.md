# TASKS.md — Work Register

**Rules.** Any agent may append its own rows and update the `Status` / `Commit` of rows it owns.
**No agent may advance another agent's row** — including the Lead Orchestrator (`agents/README.md § 3.2`).
Long tasks update this file *incrementally*, so a context loss is resumable from here rather than from memory.

**Status values:** `TODO` · `IN_PROGRESS` · `BLOCKED` (with an `INTEGRATION_STATUS.md § Blocked` row) ·
`DONE`. `DONE` means all seven conditions in `CLAUDE.md § 2` hold — not "the file exists".

**Commit column:** the short SHA that completed the task. `—` means not yet committed. The repository is not
yet initialised, so every Phase 0 row below reads `—` rather than a fabricated hash.

---

## Phase 0 — Foundation (specification only, no code)

| ID | Task | Owner | Status | Commit |
|---|---|---|---|---|
| T-000 | `CLAUDE.md` — invariants, definition of done, vocabulary, conventions | lead-orchestrator | DONE | — |
| T-001 | `research/DOMAIN_RESEARCH.md` — standards, mechanisms, PDA, Arrhenius | research-scientist | DONE | — |
| T-002 | `research/ML_METHOD_RESEARCH.md` — methods adopted **and rejected**, with reasons | research-scientist | DONE | — |
| T-003 | `research/DATASET_RESEARCH.md` | research-scientist | DONE | — |
| T-004 | `research/EVALUATION_RESEARCH.md` — LER, NP rule, protocol | research-scientist | DONE | — |
| T-005 | `research/RECOMMENDATIONS.md` | research-scientist | DONE | — |
| T-006 | `PROJECT_MASTER_SPEC.md` — FR/NFR/MLR/XR/DR/TR with priorities | lead-orchestrator | DONE | — |
| T-007 | `ARCHITECTURE.md` | lead-orchestrator | DONE | — |
| T-008 | `data/DATASET_SPEC.md` — schema, strata S0–S5, splits, Escape Set | research-scientist | DONE | — |
| T-009 | `data/DATA_GENERATION_SPEC.md` — physical model, provenance tags, § 10 limits | research-scientist | DONE | — |
| T-010 | `models/anomaly/ANOMALY_SPEC.md` | data-ml-engineer | DONE | — |
| T-011 | `models/drift/DRIFT_SPEC.md` — Shape–Amplitude, safety slope, bands | data-ml-engineer | DONE | — |
| T-012 | `models/CONFORMAL_SPEC.md` — split conformal, Mondrian ladder, guard | data-ml-engineer | DONE | — |
| T-013 | `models/RISK_SCORING_SPEC.md` — decomposition, `sum_check`, credit term | data-ml-engineer | DONE | — |
| T-014 | `models/MODEL_CARD_TEMPLATE.md` — 13 sections, machine-validated | data-ml-engineer | DONE | — |
| T-015 | `docs/EXPLAINABILITY_SPEC.md` — four layers, formula registry, templates | data-ml-engineer | DONE | — |
| T-016 | `docs/PROVENANCE_SPEC.md` — P1–P4, `TracedValue`, appendix requirement | backend-engineer | DONE | — |
| T-017 | `docs/UX_SPEC.md` — eight surfaces, four states, journeys | product-ui-designer | DONE | — |
| T-018 | `docs/UI_DESIGN_SYSTEM.md` — token contract, severity encoding | product-ui-designer | DONE | — |
| T-019 | `docs/API_CONTRACT.md` — envelope, error enum, investigation payload | backend-engineer | DONE | — |
| T-020 | `docs/GLOSSARY.md` — bound vocabulary, banned words | lead-orchestrator | DONE | — |
| T-021 | `docs/GIT_WORKFLOW.md` | lead-orchestrator | DONE | — |
| T-022 | `docs/DEMO_SCENARIO.md` — five acts, predicate-selected parts | lead-orchestrator | DONE | — |
| T-023 | `docs/SIH_JUDGING_STRATEGY.md` | lead-orchestrator | DONE | — |
| T-024 | `docs/AGENT_TOOLING.md` — four tools, four exit gates | lead-orchestrator | DONE | — |
| T-025 | `tests/TEST_STRATEGY.md` — five oracles, property tier, coverage policy | qa-playwright-engineer | DONE | — |
| T-026 | `tests/TEST_MATRIX.md` — requirement ↔ test traceability | qa-playwright-engineer | DONE | — |
| T-027 | `tests/tests.json` — 121 registered entries | qa-playwright-engineer | DONE | — |
| T-028 | `tests/PLAYWRIGHT_STRATEGY.md` | qa-playwright-engineer | DONE | — |
| T-029 | `tests/RED_TEAM_PLAN.md` — RT-001..012 | red-team-auditor | DONE | — |
| T-030 | `tests/QUALITY_GATES.md` — QG-DATA/MODEL/FE/API/ARCH/CORE/DOC/REL | integration-release-engineer | DONE | — |
| T-031 | `agents/README.md` + ten charters in `.claude/agents/` | lead-orchestrator | DONE | — |
| T-032 | Root shared state: this file, `DECISIONS.md`, `INTEGRATION_STATUS.md`, `HUMAN_ACTIONS.md`, `CHANGELOG.md`, `FINAL_STATUS.md` | lead-orchestrator | DONE | — |
| T-033 | `presentation/PRESENTATION_SPEC.md` | docs-ppt-engineer | DONE | — |
| T-034 | `reports/FOUNDATION_AUDIT.md` — Phase 0 self-audit | red-team-auditor | DONE | — |
| T-035 | `scripts/README.md` — every script, its contract, its gate | integration-release-engineer | DONE | — |
| T-036 | `git init`, first commit, `phase-0` checkpoint tag | integration-release-engineer | DONE | 5c54e2c |

## Phase 1 — Toolchain and skeleton

| ID | Task | Owner | Depends | Status | Gate | Commit |
|---|---|---|---|---|---|---|
| T-101 | `uv` project, pinned deps, lockfile committed, `ruff`/`black`/`mypy` config | integration-release-engineer | T-036 | DONE | — | 6d5e4c7 |
| T-102 | Vite + React 18 + TS strict, Tailwind with the locked token layer | frontend-engineer | T-036 | DONE | — | 6999951 |
| T-103 | Pre-commit hooks incl. `check_secrets.sh` | integration-release-engineer | T-101 | DONE | INV-10 | 6cd4266 |
| T-104 | CI `fast` job | integration-release-engineer | T-101, T-102 | DONE | — | 268cbc5 |
| T-105 | `frontend/src/design/tokens/**` from `UI_DESIGN_SYSTEM.md` | product-ui-designer | T-102 | DONE | QG-FE-02 | 440780d |
| T-106 | `scripts/check_traceability.py`, `check_test_categories.py` | integration-release-engineer | T-027 | DONE | QG-DOC-01 | ba25712 |

## Phase 2 — Dataset

| ID | Task | Owner | Depends | Status | Gate | Commit |
|---|---|---|---|---|---|---|
| T-201 | `datagen/config/` schema with the provenance-tag requirement | data-ml-engineer | T-101 | DONE | TEST-GEN-001 | ffce335 |
| T-202 | Physical model: `v0` draw, `Φ_g`, per-part amplitude, thermal confound | data-ml-engineer | T-201 | DONE | — | 819a94c |
| T-203 | Strata `S0`–`S5`, including the decoys that must **not** be flagged | data-ml-engineer | T-202 | DONE | — | a7abc45 |
| T-204 | Imperfection injection (censoring, duplicates, missing, MSA noise) | data-ml-engineer | T-202 | DONE | TEST-GEN-006 | da8c5ae |
| T-205 | Label derivation **from rendered values**, not from intent | data-ml-engineer | T-203 | DONE | TEST-GEN-005 | da8c5ae |
| T-206 | Three physically separate artifacts; `screening.parquet` leak-free | data-ml-engineer | T-205 | DONE | TEST-DL-002/003 | — |
| T-207 | Lot-disjoint train/calib/test split, verified from the artifact | data-ml-engineer | T-206 | DONE | QG-DATA-02 | — |
| T-208 | `reports/DATASET_PROFILE.md` generated, not written | data-ml-engineer | T-207 | DONE | QG-DATA-01 | — |
| T-209 | **`TEST-GEN-004`** — Escape Set non-empty, all members inside all limits | data-ml-engineer | T-206 | DONE | **release blocker** | — |
| T-210 | `scripts/verify_reproducibility.sh` (dataset half) | integration-release-engineer | T-206 | DONE | QG-REL-03 | 740978e |

## Phase 3 — Core computation (`backend/core/**`, no I/O, no framework imports)

| ID | Task | Owner | Depends | Status | Gate | Commit |
|---|---|---|---|---|---|---|
| T-301 | `core/constants.py` — every numeric literal in the codebase, each with a source ref | data-ml-engineer | T-101 | DONE | RT-008 | 23ca654 |
| T-302 | `core/robust.py` — median, IQR (type-7), MAD, medcouple, Tukey fences | data-ml-engineer | T-301 | DONE | TEST-STAT-001..003 | 23ca654 |
| T-303 | `core/dpat.py` — DPAT limits, `z_robust`, small-lot fallback ladder | data-ml-engineer | T-302 | DONE | TEST-STAT-004..006 | 23ca654 |
| T-304 | `core/multivariate.py` — MinCovDet `D²` + exact additive decomposition | data-ml-engineer | T-302 | DONE | TEST-STAT-007..009 | 3d78bc1 |
| T-305 | `core/attribution.py` — part / socket / zone / tester attribution | data-ml-engineer | T-304 | DONE | TEST-ATTR-001..005 | cbe7abc |
| T-306 | `core/shape.py` — `Φ_g` estimation with the `Φ_g(24) ≡ 1` constraint enforced | data-ml-engineer | T-302 | DONE | TEST-DRIFT-001..003 | 071df9c |
| T-307 | `core/forecast.py` — `V̂168`, the linear baseline, both always emitted | data-ml-engineer | T-306 | DONE | TEST-DRIFT-004..006 | 071df9c |
| T-308 | `core/conformal.py` — split conformal, Mondrian ladder, `bound: INFINITE` | data-ml-engineer | T-307 | DONE | TEST-CONF-001..004 | 071df9c |
| T-309 | `core/guard.py` — the six-signal exchangeability guard | data-ml-engineer | T-308 | DONE | TEST-CONF-004 | 071df9c |
| T-310 | `core/safety.py` — `usable_margin`, `safety_slope`, `slope_ratio`, bands | data-ml-engineer | T-307 | DONE | TEST-SAFE-001..004 | 071df9c |
| T-311 | `core/risk.py` — decomposition, `sum_check`, band-invariance property test | data-ml-engineer | T-310 | DONE | TEST-RISK-001..005 | 6e4b755 |
| T-312 | `core/recommend.py` — the disposition rule table | data-ml-engineer | T-311 | DONE | TEST-REC-001..007 | 6e4b755 |
| T-313 | `core/formulas.py` — the formula registry; every `formula_id` resolvable | data-ml-engineer | T-301 | DONE | TEST-EXPL-001 | 6e4b755 |
| T-314 | `core/traced.py` — `TracedValue`, `display_precision`, unit propagation | backend-engineer | T-313 | DONE | TEST-PROV-001..005 | 6e4b755 |
| T-315 | `TEST-ARCH-001` — import-graph test: `core` imports no framework, no `datagen` | data-ml-engineer | T-301 | DONE | QG-ARCH-01 | 6e4b755 |
| T-316 | Property suite (Hypothesis) across `robust`, `dpat`, `risk`, `safety` | data-ml-engineer | T-311 | DONE | QG-CORE-01 | 6e4b755 |

## Phase 4 — Training, evaluation, model cards

| ID | Task | Owner | Depends | Status | Gate |
|---|---|---|---|---|---|
| T-401 | Fit pipeline on `train` **only**; artifact hashes recorded | data-ml-engineer | T-311, T-207 | TODO | TEST-DL-001 |
| T-402 | Calibration on `calib` only; `α` sweep; NP threshold selection | data-ml-engineer | T-401 | TODO | TEST-NP-001..002 |
| T-403 | `reports/ABLATION_<tag>.md` — each component removed in turn | data-ml-engineer | T-402 | TODO | QG-MODEL-01 |
| T-404 | `reports/SENSITIVITY.md` — `k`, `α`, `margin_fraction`, weights | data-ml-engineer | T-402 | TODO | — |
| T-405 | Model cards for both modules, `validate_model_card.py` passing | data-ml-engineer | T-402 | TODO | QG-MODEL-01 |
| T-406 | **Single** test-split scoring → `reports/METRICS_<tag>.json` | integration-release-engineer | T-405 | TODO | QG-MODEL-02 |
| T-407 | Isolation Forest cross-check wired as *advisory only*, proven unable to change a verdict | data-ml-engineer | T-402 | TODO | TEST-AGG-003 |

## Phase 4b — Hackathon intelligence extension (additive; T-401–T-407 unchanged)

Governance bridge: `D-038`. The rows below are hackathon-priority additions scoped by
`LATENTIS_Hackathon_Implementation_Plan.md`; they do not rename, repurpose, or reorder T-401–T-407,
and they do not alter Phase 3 scientific authority. New test IDs are registered additively in
`tests/tests.json`; no existing test meaning is changed.

| ID | Task | Owner | Depends | Status | Gate |
|---|---|---|---|---|---|
| T-408 | CUSUM persistent-shift evidence (`backend/core/cusum.py`), advisory only, proven unable to change a verdict | data-ml-engineer | T-301, T-315 | DONE | TEST-CUSUM-001..010 |
| T-409 | Sensor-quality / fault evidence (`backend/core/quality.py`): missing, flatline, non-finite, gaps, discontinuity; per-part score + lot roll-up feeding the existing `risk_quality` contract | data-ml-engineer | T-301, T-311 | DONE | TEST-QUAL-001..011 |
| T-410 | Minimal condition-aware context: inspect existing temperature/voltage/zone/attribution/shape-safety coverage first; implement only the missing interface/evidence, no new normalisation model | data-ml-engineer | T-305, T-310 | DONE | TEST-COND-001..003 |

## Phase 5 — API

| ID | Task | Owner | Depends | Status | Gate |
|---|---|---|---|---|---|
| T-501 | FastAPI app, envelope, error enum, `/healthz`, `/version` | backend-engineer | T-314 | DONE | TEST-API-001 |
| T-502 | DuckDB ingest with the four-class rejection report | backend-engineer | T-501 | DONE | TEST-ING-001..009 |
| T-503 | `/components`, `/components/{id}/investigation` incl. the `worst` object | backend-engineer | T-502, T-312 | DONE | TEST-API-002..004 |
| T-504 | `/lots/{id}/distribution`, `/posture`, `/export/{id}.pdf` | backend-engineer | T-503 | DONE | TEST-REP-001..002 |
| T-505 | OpenAPI committed; generated TS client; drift check in CI | backend-engineer | T-503 | DONE | QG-API-01 |
| T-506 | Provenance appendix on every decision-bearing response | backend-engineer | T-503 | DONE | QG-API-02 |
| T-510 | Phase 5 final independent audit and sealing | red-team-auditor | T-506 | DONE | QG-REL-04 | 5b4dc9a |

## Phase 6 — Frontend

| ID | Task | Owner | Depends | Status | Gate |
|---|---|---|---|---|---|
| T-601 | `<Metric>` with the single `{ traced: TracedValue }` prop | frontend-engineer | T-105, T-505 | TODO | QG-FE-02 |
| T-602 | S1 Fleet, S2 Lot, S3 Investigation, S4 Forecast | frontend-engineer | T-601 | TODO | TEST-FE-ARCH-001 |
| T-603 | S5 Posture, S6 Ingest, S7 Model Card, S8 Export | frontend-engineer | T-602 | TODO | — |
| T-604 | Four states on every surface (loading / empty / error / degraded) | frontend-engineer | T-602 | TODO | E2E-STATE-001..004 |
| T-605 | Chart table-fallbacks; `TEST-A11Y-001` clean | frontend-engineer | T-602 | TODO | QG-FE-01 |
| T-606 | `TEST-FE-LINT-001` — no arithmetic on decision values in `src/**` | frontend-engineer | T-601 | TODO | QG-FE-03 |
| T-607 | Journeys J1–J5 | qa-playwright-engineer | T-603 | TODO | QG-REL-02 |
| T-608 | `E2E-PERF-001..003` | qa-playwright-engineer | T-603 | TODO | — |

## Phase 7 — Audit, hardening, release

| ID | Task | Owner | Depends | Status | Gate |
|---|---|---|---|---|---|
| T-701 | `tests/red_team/rt_001..012` implemented | red-team-auditor | T-607 | TODO | QG-REL-04 |
| T-702 | `reports/RED_TEAM_<tag>.md` — twelve rows, verdicts and reasons | red-team-auditor | T-701 | TODO | QG-REL-04 |
| T-703 | RT-001 reconciliation: every illustrative number in the docs replaced by a cited one **or** relabelled | lead-orchestrator | T-702 | TODO | **QG-DOC-02** |
| T-704 | `scripts/bootstrap.sh` — fresh clone, network off, ending in a PDF | integration-release-engineer | T-603 | TODO | QG-REL-05 |
| T-705 | `verify_reproducibility.sh` full run, output committed | integration-release-engineer | T-406 | TODO | QG-REL-03 |
| T-706 | `FINAL_STATUS.md` reconciled with the gate table | lead-orchestrator | T-702, T-705 | TODO | QG-DOC-02 |
| T-707 | `README.md` + deck updated to the measured numbers | docs-ppt-engineer | T-706 | TODO | RT-001 |
| T-708 | Tag `v1.0.0` per the nine-step procedure | integration-release-engineer | T-706 | TODO | QG-REL-01..05 |

---

## Notes on rows that are commonly mis-scheduled

- **T-209 before T-401.** Training against a corpus with an empty Escape Set produces a model whose headline
  metric is meaningless, and the fault is invisible until the auditor finds it. The dataset proves the escape
  cases exist *before* anything is fitted.
- **T-315 early, not late.** The import-graph test is cheap on day one and expensive after twelve modules have
  quietly imported `pydantic` into `core`.
- **T-406 exactly once.** It is a single row on purpose. If it needs repeating, that is a new tag, not a re-run
  (`integration-release-engineer`, non-negotiable 1).
- **T-703 is not optional.** Phase 0 documents contain illustrative numbers written before the pipeline existed.
  `RT-001` is expected to fail until this row is `DONE`; that failure is the mechanism, not a nuisance.

