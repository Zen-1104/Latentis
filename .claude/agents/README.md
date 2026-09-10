# agents/README.md — Roster, Ownership, and Handoffs

**Owner:** Lead Orchestrator · Implements INV-7 · Charters live in `.claude/agents/`

## 1. Why this file is load-bearing

INV-7 says no agent silently overwrites another agent's owned file. That invariant needs a table to point at,
and this is it. An agentic IDE edits more files than a human intends — confidently, and with a plausible
rationale in the commit message. The ownership table plus `git status --short` before every commit is the only
thing between that tendency and a repository where nobody can tell who broke what.

## 2. The ten agents

| Charter | Role in one line | Phase |
|---|---|---|
| `lead-orchestrator` | Owns the specs, the vocabulary, and the sequencing. Signs off on `DECISIONS.md`. | all |
| `research-scientist` | Grounds every method claim in a citation; owns `research/**` and the dataset specs. | 1 |
| `product-ui-designer` | Owns tokens, surfaces, states, and the Stitch draft directory. | 1, 5 |
| `data-ml-engineer` | Owns the generator, the numeric core, and every model artifact. | 2, 3 |
| `backend-engineer` | Owns the API, persistence, provenance plumbing, and the report renderer. | 3, 4 |
| `frontend-engineer` | Owns the application shell and every production component. | 4, 5 |
| `qa-playwright-engineer` | Owns the test strategy, the traceability register, and the E2E suite. | 3–5 |
| `red-team-auditor` | Attacks the project's own claims. **Never assigned implementation work.** | 6 |
| `docs-ppt-engineer` | Owns `README.md` and `presentation/**`; every number carries its artifact path. | 6 |
| `integration-release-engineer` | Owns CI, scripts, gates, and the single scoring of the test split. | 7 |

## 3. File ownership

**Reading is unrestricted.** Writing is not. "Owner" means: may create, modify and delete without a handoff.
Anyone else needs § 4.

| Path | Owner | Notes |
|---|---|---|
| `CLAUDE.md`, `PROJECT_MASTER_SPEC.md`, `ARCHITECTURE.md` | `lead-orchestrator` | Changing an invariant requires a `DECISIONS.md` entry |
| `docs/GLOSSARY.md`, `docs/GIT_WORKFLOW.md`, `docs/AGENT_TOOLING.md`, `docs/DEMO_SCENARIO.md`, `docs/SIH_JUDGING_STRATEGY.md` | `lead-orchestrator` | |
| `agents/**`, `.claude/agents/**` | `lead-orchestrator` | An agent may not widen its own charter |
| `research/**`, `data/DATASET_SPEC.md`, `data/DATA_GENERATION_SPEC.md` | `research-scientist` | Specs frozen at end of Phase 1; later edits are handoffs |
| `docs/UX_SPEC.md`, `docs/UI_DESIGN_SYSTEM.md`, `frontend/src/design/tokens/**`, `frontend/src/_generated_draft/**` | `product-ui-designer` | The draft directory is excluded from the production bundle |
| `datagen/**`, `backend/core/**`, `models/*.md`, `models/registry/**`, `docs/EXPLAINABILITY_SPEC.md` | `data-ml-engineer` | Includes `ANOMALY_SPEC`, `DRIFT_SPEC`, `CONFORMAL_SPEC`, `RISK_SCORING_SPEC`, `MODEL_CARD_TEMPLATE` |
| `backend/app/**`, `backend/services/**`, `backend/db/**`, `backend/reporting/**`, `docs/API_CONTRACT.md`, `docs/PROVENANCE_SPEC.md` | `backend-engineer` | |
| `frontend/src/**` except the designer's paths | `frontend-engineer` | |
| `frontend/src/api/generated/**` | **nobody** | Generated from OpenAPI. Hand-editing fails `TEST-API-001` |
| `tests/*.md`, `tests/tests.json`, `frontend/tests/**` | `qa-playwright-engineer` | Owns the register; does not own the unit tests themselves (§ 3.1) |
| `tests/red_team/**`, `reports/FOUNDATION_AUDIT.md`, `reports/RED_TEAM_*.md` | `red-team-auditor` | |
| `README.md`, `presentation/**` | `docs-ppt-engineer` | Every number resolves to a `reports/` artifact (`RT-001`) |
| `scripts/**`, `.github/workflows/**`, `CHANGELOG.md`, `INTEGRATION_STATUS.md` | `integration-release-engineer` | |
| `reports/**` (all other files) | **no agent** | Written **only** by pipeline scripts. A hand-authored report is a fabricated one |
| `TASKS.md` | shared, row-scoped (§ 3.2) | |
| `DECISIONS.md`, `FINAL_STATUS.md`, `HUMAN_ACTIONS.md` | `lead-orchestrator` | Others append proposals; the lead resolves |

### 3.1 Tests are written by the implementer, governed by QA

Splitting these two roles is the usual mistake in either direction, so it is settled here:

| Artifact | Written by | Governed by |
|---|---|---|
| `backend/tests/unit/**`, `backend/tests/property/**` | the agent who owns the code under test | `qa-playwright-engineer` reviews category and oracle |
| `backend/tests/integration/**`, `backend/tests/arch/**` | `backend-engineer` (`arch`: with the auditor) | `qa-playwright-engineer` |
| `frontend/tests/**` | `qa-playwright-engineer` | — |
| `tests/red_team/**` | `red-team-auditor` | nobody (an audit reviewed by its subject is not an audit) |
| `tests/tests.json`, `tests/TEST_MATRIX.md` | `qa-playwright-engineer` | `QG-DOC-01` |

Rationale: an implementer who does not write the test does not internalise the oracle, and a QA engineer who
writes every unit test becomes a bottleneck at exactly the phase where the numeric core is moving fastest.
QA's leverage is the **register and the category rule** — "this test's oracle is the current output" is a
review rejection, and that judgement is where the value is.

### 3.2 `TASKS.md` is row-scoped

Any agent may append its own rows and update the status and commit hash of rows it owns. **No agent may
advance another agent's row** — including the orchestrator (`AGENT_TOOLING § 3`, rule 3). That single rule is
what keeps "done" attached to reality, because the only person who can mark a task done is the one who would
have to fix it if it isn't.

## 4. Handoff protocol

When an agent needs a change in a file it does not own:

1. **Do not edit it.** Not even a one-line fix, and not even if the fix is obviously correct — the cost of the
   rule is a few minutes of latency, and the cost of breaking it is that ownership stops meaning anything.
2. Append a handoff note to `INTEGRATION_STATUS.md § Handoffs`:

```markdown
### HO-014 · data-ml-engineer → backend-engineer · 2026-09-14
**File:** backend/app/routers/components.py
**Need:** `worst` object must include `mondrian_level` so S4 can render the fallback warning.
**Why:** CONFORMAL_SPEC § 3 requires the level to be visible wherever a bound is displayed.
**Blocking:** FR-307 / TEST-CONF-004 / E2E-S4-001
**Proposed shape:** `worst.drift.conformal.mondrian_level: int`  (0..3)
**Status:** OPEN
```

3. The owner implements it, references `HO-014` in the commit body, and sets the note to `DONE` with the
   commit hash.
4. If the owner disagrees, the note becomes a `DECISIONS.md` entry marked `PROPOSED` and the Lead Orchestrator
   resolves it. Neither agent implements a compromise in the meantime.

**Exception, narrowly drawn.** A handoff may be skipped only for a change that is *purely mechanical and
generated* — regenerating `frontend/src/api/generated/**` after an OpenAPI change. Even then the commit body
carries `generated:` and the generator version (`AGENT_TOOLING § 6`).

## 5. Phase graph

```
Phase 1  research-scientist ∥ product-ui-designer            (no code, disjoint outputs)
Phase 2  data-ml-engineer  (datagen)                         → dataset artifacts + QG-DATA-01/02
Phase 3  data-ml-engineer  (core numerics)
         ∥ backend-engineer (API skeleton, DuckDB)
         ∥ qa-playwright-engineer (register, matrix, harness)
Phase 4  backend-engineer  (wire core → API) → frontend-engineer (generated client)
Phase 5  frontend-engineer (S1–S8) ∥ qa-playwright-engineer (E2E from UX_SPEC)
Phase 6  red-team-auditor (RT-001..012) ∥ docs-ppt-engineer
Phase 7  integration-release-engineer (gates, single test-split scoring, tag)
```

Parallelism is permitted **only** where ownership sets are disjoint — which is why the table above is
specific about directories rather than about modules.

## 6. Behaviour every charter inherits

These do not need restating in each charter; they apply to all ten.

- Read `CLAUDE.md` first, and again after any context compaction.
- Report failures literally, with the actual output. Never "mostly working".
- Blocked ⇒ write to `INTEGRATION_STATUS.md § Blocked` **and continue with unblocked work**. Never downgrade a
  requirement to unblock yourself.
- Spec appears wrong ⇒ `DECISIONS.md` as `PROPOSED`; implement the spec-conformant version or stop. Never
  quietly implement something else.
- Write progress to `TASKS.md` incrementally, so a context loss is resumable from the file rather than from
  memory.
- Stage explicit paths. `git add -A` from the repo root is prohibited (`GIT_WORKFLOW.md`).
- A failing test is fixed in the implementation (INV-6).

## 7. Adding an agent

A new charter needs: a disjoint ownership set carved from the table above by the Lead Orchestrator, a
`DECISIONS.md` entry recording why the existing ten were insufficient, and a phase assignment. Adding an agent
whose ownership overlaps an existing one is how a repository acquires two conflicting sources of truth for the
same file, so the disjointness requirement is not negotiable.

