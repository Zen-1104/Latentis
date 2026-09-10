# INTEGRATION_STATUS.md — Gate State, Blockers, Handoffs

Owned by `integration-release-engineer`. Any agent may **add** a `Blocked` row or a `Handoff` row; only the
owning charter changes a gate verdict, and never for a gate that gates its own work
(`tests/QUALITY_GATES.md § 1`).

## Reading this file

- **`Evaluated at`** is the commit the evidence was produced at. If `HEAD` has moved past it in a way that
  touches the gated area, the verdict is **`STALE`**, and `STALE` counts as `NOT_PASSED` for release purposes.
  There is no partial credit for a gate that passed last week.
- **There is no `WAIVED`.** A gate that will not pass downgrades the dependent capability claim in
  `FINAL_STATUS.md` (`D-029`). Recording a failure is always available; excusing one is not.
- **`NOT_RUN` is a real state and is reported**, never omitted. An absent row reads as a pass, which is the
  easiest way for a status document to mislead.

**Phase:** 1 (toolchain and skeleton) · **Date of this snapshot:** 2026-09-08 · **Repository:** initialised at `5c54e2c` (checkpoint tag: `phase-0`)

---

## § Gate state

Every gate below is `NOT_RUN` because no code exists yet. This is the expected Phase 0 state, and the table is
present now so that no gate can be *discovered* late — the empty column is the schedule.

| Gate | What it proves | Authority | Verdict | Evidence path | Evaluated at |
|---|---|---|---|---|---|
| QG-DATA-01 | Dataset profile generated from the artifact, not written | data-ml-engineer | NOT_RUN | `reports/DATASET_PROFILE.md` | — |
| QG-DATA-02 | Splits are lot-disjoint and leak-free, verified from the files | data-ml-engineer + red-team-auditor | NOT_RUN | `reports/SPLIT_AUDIT.json` | — |
| QG-MODEL-01 | Ablation + model cards complete and machine-valid | data-ml-engineer | NOT_RUN | `reports/ABLATION_<tag>.md`, `models/**/MODEL_CARD.md` | — |
| QG-MODEL-02 | Test split scored exactly once, metrics committed | integration-release-engineer | NOT_RUN | `reports/METRICS_<tag>.json` | — |
| QG-FE-01 | Accessibility + badge/state contract on every surface | qa-playwright-engineer + product-ui-designer | NOT_RUN | `reports/A11Y_<tag>.json` | — |
| QG-FE-02 | Tokens come from the locked layer; no ad-hoc colour or spacing | product-ui-designer | NOT_RUN | `reports/TOKEN_AUDIT.json` | — |
| QG-FE-03 | No fabricated value and no mock path in the **built bundle** | red-team-auditor | NOT_RUN | `reports/BUNDLE_SCAN_<tag>.json` | — |
| QG-API-01 | OpenAPI committed; generated client has zero drift | backend-engineer | NOT_RUN | CI `full` job log + `frontend/src/api/generated/**` diff | — |
| QG-API-02 | Provenance appendix on every decision-bearing response | backend-engineer + red-team-auditor | NOT_RUN | `reports/PROVENANCE_AUDIT_<tag>.json` | — |
| QG-ARCH-01 | `core` imports no framework and no `datagen` | data-ml-engineer | NOT_RUN | `TEST-ARCH-001` result | — |
| QG-CORE-01 | Every public core function has a legitimate oracle | qa-playwright-engineer | NOT_RUN | `reports/COVERAGE_<tag>.md` + category review verdicts | — |
| QG-DOC-01 | Bidirectional requirement ↔ test traceability, no gaps at P0 | integration-release-engineer | PASS | `scripts/check_traceability.py` output | ba25712 |
| QG-DOC-02 | Every capability claim matches the status vocabulary | red-team-auditor | NOT_RUN | `reports/RED_TEAM_<tag>.md § vocabulary` | — |
| QG-REL-01 | Full suite green at the tagged commit | integration-release-engineer | NOT_RUN | CI `full` job at the tag | — |
| QG-REL-02 | Nightly suite (all E2E journeys) green at the tagged SHA | integration-release-engineer | NOT_RUN | CI `nightly` job at the tag | — |
| QG-REL-03 | Regeneration, retraining and re-scoring are byte-stable | integration-release-engineer | NOT_RUN | `reports/REPRODUCIBILITY_<tag>.txt` | — |
| QG-REL-04 | Twelve red-team rows, each `PASS` / `FAIL` / `NOT_RUN`+reason | red-team-auditor | NOT_RUN | `reports/RED_TEAM_<tag>.md` | — |
| QG-REL-05 | Fresh clone, network disabled, ending in a rendered PDF | integration-release-engineer | NOT_RUN | `reports/OFFLINE_BOOTSTRAP_<tag>.txt` | — |

**Phase 0 exit does not require any gate above.** It requires the specification set to exist and
`reports/FOUNDATION_AUDIT.md` to be complete, including its own failures.

---

## § Blocked

Format: `BL-nnn · <what is blocked> · <by what> · <owner> · <status>`. A row leaves this section only when the
blocker is resolved or the blocked work is formally dropped in `FINAL_STATUS.md` — never because it got stale.

### BL-001 · DPAT formula confidence · MEDIUM until the primary standard is read · research-scientist · OPEN

**Blocked:** upgrading the `AEC-Q001` citation in `research/DOMAIN_RESEARCH.md § 4` and
`models/anomaly/ANOMALY_SPEC.md § 2` from MEDIUM to HIGH confidence.
**By:** the primary document is not retrievable from this environment — `AEC_Q001_Rev_D.pdf` fails with
`error:10000410:SSL routines:OPENSSL_internal:SSLV3_ALERT_HANDSHAKE_FAILURE`; two alternative sources returned
marketing copy and a navigation shell respectively.
**Impact:** none on implementation. `D-001` and `D-003` proceed on the secondary source, tagged MEDIUM.
**Unblocks via:** `HUMAN-002`.
**Not doing:** presenting the formula as primary-sourced. `D-033` records why.

### BL-002 · `RT-001` · illustrative numbers in Phase 0 documents · lead-orchestrator · OPEN, EXPECTED

**Blocked:** `QG-DOC-02`, and therefore the `v1.0.0` tag.
**By:** the worked examples written before the pipeline existed contain numbers that no `reports/` artifact can
yet resolve — `45.2 µA`, `17.4 σ`, `D² = 41.7`, `LER 0.94`, the forecast triple `32.3 / 39.8 / 58.3`.
**Impact:** `RT-001` is **expected to FAIL** until `T-703` replaces each with a cited value or relabels it
explicitly as illustrative. This row exists so that the failure is scheduled rather than surprising.
**Unblocks via:** `T-703`.
**Note:** the correct resolution is reconciliation, not an `RT-001` exemption. There are exactly three exemption
kinds and "it is only an example" is not one of them (`tests/RED_TEAM_PLAN.md § RT-001`).

### BL-003 · every Phase 1+ row · the repository is not initialised · integration-release-engineer · RESOLVED

**Blocked:** `T-101` onward — all of them, transitively.
**By:** `T-036` (`git init`, first commit, `phase-0` tag).
**Resolution:** Resolved at commit `5c54e2c` with `phase-0` tag created. `T-101` completed at commit `6d5e4c7`.


### BL-004 · `RT-005` falsifiability · corpus may not contain the decisive case · data-ml-engineer · WATCH

**Blocked:** `RT-005`'s ability to return `PASS` rather than `NOT_RUN`.
**By:** the suite needs at least one part with `V̂168 < limit_high ≤ Û168` — a part the point forecast clears and
the bound does not. Whether the generated corpus contains one is not yet known.
**Impact:** if empty, `RT-005` reports `NOT_RUN` with that reason and requests a stratum that exercises it. A
claim that cannot be tested is not a verified claim.
**Unblocks via:** `T-206` (corpus search), then `T-203` if a stratum must be added.
**Status is `WATCH`, not `OPEN`:** nothing is blocked yet; this is a scheduled risk with a named response.

### BL-005 · T-406 single test-split scoring · exclusive owner + release protocol · integration-release-engineer · BLOCKED

**Blocked:** `T-406` (single test-split scoring → `reports/METRICS_<tag>.json`, gate `QG-MODEL-02`).
**By:** exclusive ownership and protocol, not technical readiness. `D-030`/`AG-5`
reserve scoring to integration-release-engineer alone, once per tag; the
release-tag flow that carries it does not exist yet. Filed by data-ml-engineer
per `D-041`; only the owning charter may clear it.
**Impact:** T-403–T-405 (ablation, sensitivity, cards) sequence behind the
evaluation block that T-406 closes. No `Measured` numbers may be published
until it clears — nothing is estimated in the meantime.
**Unblocks via:** the evaluation-phase scoring run by integration-release-engineer.
**Not doing:** implementing scoring, touching `test.parquet` for evaluation, or
advancing the `T-406` row from this charter (`TASKS.md` rules, INV-7).

---

## § Handoffs

A handoff is required whenever an agent needs a change in a file it does not own (INV-7). The requesting agent
writes the row; the owning agent implements and closes it. Format per `agents/README.md § 4`.

### HO-001 · lead-orchestrator → all charters · 2026-09-05
**File:** n/a — read acknowledgement.
**Need:** every charter confirms it has read `CLAUDE.md`, `agents/README.md § 3`, and its own file before its
first write in Phase 1.
**Why:** `CLAUDE.md § 8` read-order; also the re-read requirement after any context compaction.
**Blocking:** nothing yet; becomes blocking at `T-101`.
**Status:** OPEN

### HO-002 · qa-playwright-engineer → frontend-engineer · 2026-09-05
**File:** `frontend/src/**` (selector attributes).
**Need:** the `data-testid` contract `<surface>-<block>-<field>` applied from the first component, not
retrofitted.
**Why:** `tests/PLAYWRIGHT_STRATEGY.md § 4`. Retrofitting selectors after five surfaces exist means either a
large mechanical diff or CSS-class selectors, and the latter is banned.
**Blocking:** J1–J5 (`T-607`).
**Proposed shape:** `data-testid="s3-verdict-dpat-z"`.
**Status:** OPEN

### HO-003 · data-ml-engineer → backend-engineer · 2026-09-05
**File:** `backend/app/routers/components.py` (does not exist yet — the row is filed in advance).
**Need:** the `worst` object must include `mondrian_level` so S4 can render the fallback warning.
**Why:** `models/CONFORMAL_SPEC.md § 3` requires the level to be visible wherever a bound is displayed.
**Blocking:** FR-307 / `TEST-CONF-004` / `E2E-S4-001`.
**Proposed shape:** `worst.drift.conformal.mondrian_level: int` (0..3).
**Status:** OPEN

### HO-004 · red-team-auditor → data-ml-engineer · 2026-09-05
**File:** `backend/core/constants.py`.
**Need:** every numeric literal in the codebase declared here with a `source_ref`, and `1.35` / `1.4826`
appearing **exactly once each** in the whole repository.
**Why:** `RT-008` is an AST scan with an exhaustive permitted-literal list. A second occurrence anywhere is a
hard-coded statistic and fails the scan — which is the intended behaviour, so the constraint has to be known
before the code is written rather than discovered by the audit.
**Blocking:** `RT-008`, `QG-REL-04`.
**Status:** OPEN

### HO-005 · docs-ppt-engineer → integration-release-engineer · 2026-09-05
**File:** `reports/DEMO_PARTS_<tag>.json`, `reports/METRICS_<tag>.json`.
**Need:** both artifacts must exist before any slide containing a number can be finalised.
**Why:** `.claude/agents/docs-ppt-engineer.md` non-negotiable 1 — every number carries its source artifact path,
and a slide with a placeholder number becomes a fabricated result the moment someone forgets to replace it.
**Blocking:** `T-707`.
**Status:** OPEN

### HO-006 · backend-engineer → qa-playwright-engineer · 2026-09-10
**File:** `tests/tests.json` (register; matrix traceability at QA's discretion).
**Need:** register the three new T-501 test files under additive IDs (suggested: one ID for the
health/version envelope + determinism + OpenAPI-served integration file, one for the boundary
rederivation round-trip, one for the closed-enum/500-leak unit matrix) — or QA-chosen IDs.
**Why:** `TEST_STRATEGY.md § 1` hygiene: implemented-but-unregistered tests are invisible to the
register view of coverage. T-501's own gate `TEST-API-001` stays `Specified` until T-505 ships the
generated client; the new IDs must not be presented as satisfying it.
**Blocking:** nothing (`T-502` proceeds regardless).
**Proposed shape:** entries with status `Implemented` pointing at
`backend/tests/integration/test_system_api.py`, `backend/tests/unit/test_traced_schema.py`,
`backend/tests/unit/test_error_enum.py`.
**Status:** OPEN

---

## § Re-score requests

None. Any request to re-score the test split is recorded here with its date and requester, and declined
(`D-030`). The section is present at Phase 0 because an empty ledger that existed from the start is evidence;
one created on the day of the request is not.

## § Snapshot log

| Date | Phase | Gates passed | Gates failed | Blocked rows |
|---|---|---|---|---|
| 2026-09-05 | 0 | 0 of 18 (none applicable) | 0 | 3 OPEN, 1 WATCH |
| 2026-09-08 | 1 | 0 of 18 (none applicable) | 0 | 2 OPEN, 1 RESOLVED, 1 WATCH |



