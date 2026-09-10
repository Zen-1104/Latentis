# CHANGELOG

All notable changes to SIH26170 / LATENTIS. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning is [SemVer](https://semver.org/spec/v2.0.0.html). Owned by `integration-release-engineer`.

**Rule for this file:** an entry may describe what was *built*; it may not describe a *result*. A performance or
accuracy number appears here only after `reports/METRICS_<tag>.json` exists at that tag, and then it is quoted
with its artifact path. No number in this file has been measured yet, so no number appears in it.

---

## [Unreleased] — Phase 0, foundation

Specification and governance only. **No executable code exists.** Every capability below is `Specified` in the
sense of `CLAUDE.md § 4` — written down, not implemented, not verified, not measured.

### Added — problem framing and research

- `research/DOMAIN_RESEARCH.md` — MIL-STD-883 Method 1015 burn-in, PDA, MIL-PRF-38535 delta limits, AEC-Q001
  PAT/SPAT/DPAT, ECSS-Q-ST-60C, Arrhenius acceleration and the wear-out mechanisms (TDDB, NBTI, HCI,
  electromigration). Confidence markers per finding; the AEC-Q001 citation is MEDIUM (`D-033`, `HUMAN-002`).
- `research/ML_METHOD_RESEARCH.md` — methods adopted **and rejected**, each rejection with its reason.
- `research/DATASET_RESEARCH.md`, `research/EVALUATION_RESEARCH.md`, `research/RECOMMENDATIONS.md`.

### Added — specifications

- `PROJECT_MASTER_SPEC.md` — FR / NFR / MLR / XR / DR / TR with priorities.
- `ARCHITECTURE.md` — the four-layer split, and the rule that `core` imports no framework.
- `data/DATASET_SPEC.md`, `data/DATA_GENERATION_SPEC.md` — schema, strata `S0`–`S5`, the Escape Set, three
  physically separate split artifacts, provenance tags on every generator parameter.
- `models/anomaly/ANOMALY_SPEC.md`, `models/drift/DRIFT_SPEC.md`, `models/CONFORMAL_SPEC.md`,
  `models/RISK_SCORING_SPEC.md`, `models/MODEL_CARD_TEMPLATE.md`.
- `docs/EXPLAINABILITY_SPEC.md`, `docs/PROVENANCE_SPEC.md`, `docs/API_CONTRACT.md`, `docs/UX_SPEC.md`,
  `docs/UI_DESIGN_SYSTEM.md`, `docs/GLOSSARY.md`, `docs/GIT_WORKFLOW.md`, `docs/DEMO_SCENARIO.md`,
  `docs/SIH_JUDGING_STRATEGY.md`, `docs/AGENT_TOOLING.md`.

### Added — test and audit design

- `tests/TEST_STRATEGY.md` — the five legitimate oracles and the rule that "the current output" is not one.
- `tests/tests.json` — 121 registered entries, each with a declared oracle. Machine-validated: valid JSON, no
  duplicate IDs, uniform keys, seven categories.
- `tests/TEST_MATRIX.md` — bidirectional requirement ↔ test traceability, gated by `QG-DOC-01`.
- `tests/PLAYWRIGHT_STRATEGY.md` — the API-as-oracle rule, five journeys, chart table-fallback assertions.
- `tests/RED_TEAM_PLAN.md` — `RT-001`..`RT-012` with mandatory negative controls.
- `tests/QUALITY_GATES.md` — eighteen gates; no waiver state exists.

### Added — governance

- `CLAUDE.md` — ten invariants, the seven-condition definition of done, the status vocabulary.
- `agents/README.md` and ten charters under `.claude/agents/` with a disjoint file-ownership table.
- `TASKS.md` (Phase 0–7 register), `DECISIONS.md` (`D-001`..`D-033`), `INTEGRATION_STATUS.md` (gate table,
  four blocked rows, five handoffs), `HUMAN_ACTIONS.md` (`HUMAN-001`..`HUMAN-010`), `FINAL_STATUS.md`,
  `presentation/PRESENTATION_SPEC.md`, `reports/FOUNDATION_AUDIT.md`, `scripts/README.md`.

### Known at Phase 0 exit

- `RT-001` **fails** — Phase 0 documents contain illustrative numbers written before any pipeline existed
  (`BL-002`). Scheduled for reconciliation in `T-703`; the failure is the mechanism that forces it.
- Every one of the eighteen quality gates is `NOT_RUN`, because there is nothing to evaluate yet. Recorded
  explicitly in `INTEGRATION_STATUS.md` rather than left blank.
- The repository is not initialised (`T-036` / `HUMAN-001`), so every `TASKS.md` row reads `Commit: —`. Phase 0
  rows are therefore `DONE` against a definition of done whose first condition is not yet satisfiable; this
  inconsistency is logged as `BL-003` rather than resolved by inventing hashes.

### Not added, deliberately

- No `backend/`, `frontend/`, `datagen/` or `models/**/*.py`. The user's brief scoped this phase to the
  foundation, and a half-implemented module would make the specification look done when it is not.
- No `reports/` artifacts other than `FOUNDATION_AUDIT.md`. That directory is written by pipeline scripts; a
  hand-authored report is a fabricated one (`AGENT_TOOLING § 6`).

---

## Release history

None. `v1.0.0` requires the nine-step procedure in `docs/GIT_WORKFLOW.md` and all five `QG-REL-*` gates
evaluated at the tagged commit. A tag with failing gates is permitted — with an honest `FINAL_STATUS.md` that
names them (`D-029`). A tag that claims gates it did not run is not.
