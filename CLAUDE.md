# CLAUDE.md — Agent Operating Rules for SIH26170 / LATENTIS

Every autonomous agent working in this repository MUST read this file before its first action
and MUST re-read it after any context compaction.

---

## 1. Non-negotiable invariants

These are **P0 release blockers**. Violating any one of them fails the build regardless of
test results.

| ID | Invariant |
|----|-----------|
| INV-1 | **No fabricated numbers.** Every metric, score, threshold, statistic, or chart value rendered anywhere must be computed at runtime from data on disk. No literal numeric results in UI code, README tables, or slides. |
| INV-2 | **No hard-coded decisions.** A component's verdict must never depend on its `component_id`, row index, or any identifier. Enforced by test `RT-004` (ID-permutation invariance). |
| INV-3 | **Synthetic data is labelled synthetic**, always, everywhere, unremovably. Never present it as ISRO operational data. |
| INV-4 | **No data leakage.** Anything derived from 96 h or 168 h observations is forbidden as a Module B input feature. Enforced by `TEST-DL-*`. |
| INV-5 | **Explanations are generated from the same values used for the decision** — never from a template with plausible-looking numbers pasted in. Enforced by `RT-007`. |
| INV-6 | **Tests are never weakened to make code pass.** If a test fails, fix the implementation. Changing a test requires a `DECISIONS.md` entry with justification and the Lead Orchestrator's sign-off. |
| INV-7 | **No agent silently overwrites another agent's owned file.** See `agents/README.md` for the ownership table. Cross-boundary changes go through a handoff note. |
| INV-8 | **Reproducibility.** Same seed + same config ⇒ byte-identical dataset and identical metrics. Enforced by `scripts/verify_reproducibility.sh`. |
| INV-9 | **Never claim a capability that is not implemented and tested.** Use the vocabulary in § 4. |
| INV-10 | **No secrets in the repository.** No keys, tokens, passwords — including in `HUMAN_ACTIONS.md`. |

## 2. Definition of "done" for any task

A task is done when *all* of the following hold:

1. Code is written and committed with a meaningful message.
2. Unit tests exist, run, and pass — including at least one adversarial/property test.
3. The change is reachable from the running application (not dead code).
4. `TASKS.md` is updated with the status and the commit hash.
5. Any new decision is recorded in `DECISIONS.md`.
6. Any new limitation is recorded in `FINAL_STATUS.md § Known Limitations`.
7. Nothing in § 1 is violated.

"I wrote the file" is not done. "The tests pass" is not done unless the tests are meaningful.

## 3. Reporting rules

- Report failures immediately and literally, with the actual output. Never summarise a failing
  test as "mostly working".
- If you cannot complete a task, write why in `INTEGRATION_STATUS.md § Blocked` and continue
  with unblocked work. Do not silently downgrade a requirement.
- If you discover the specification is wrong, do **not** quietly implement something else.
  Raise it in `DECISIONS.md` as `PROPOSED`, implement the spec-conformant version or stop, and
  flag it to the Lead Orchestrator.

## 4. Required vocabulary (prevents accidental over-claiming)

| Term | Means |
|------|-------|
| **Specified** | Written in a spec document. No code exists. |
| **Implemented** | Code exists and runs. Not necessarily correct. |
| **Verified** | Implemented + covered by a passing meaningful test. |
| **Measured** | A number was produced by running the real pipeline on real generated data; the run is reproducible and the artifact is committed under `reports/`. |
| **Target** | A goal we have not yet met. Must be written as "target", never as a result. |

Any number in a slide or README must be traceable to a `Measured` artifact, or be absent.

## 5. Conventions

- **Python** 3.11+, `ruff` + `black` (line length 100), full type hints, `pydantic` v2 models
  at every boundary. No bare `except`. No `print` — use the structured logger.
- **TypeScript** strict mode, no `any`, no `@ts-ignore`. Zod schemas generated from the backend
  OpenAPI document — never hand-written duplicates.
- **Units are explicit.** Every measurement value travels with its unit. Never store or compare
  a bare float across parameters. Amperes internally; display units are a presentation concern.
- **Naming.** `snake_case` in Python and in all API JSON payloads; `camelCase` only inside
  frontend component-local state. Domain terms come from `docs/GLOSSARY.md` — do not invent
  synonyms ("outlier score" vs "anomaly score" vs "risk" are three different things here).
- **Determinism.** Every RNG is seeded from config. No `random.random()`, no unseeded `numpy`,
  no `datetime.now()` inside a computation path (only in metadata).

## 6. Git rules

Small, meaningful commits. Conventional-commit prefixes. Checkpoint tag after every phase.
Never `push --force`, never `reset --hard` on someone else's work, never delete untracked
files you did not create. Full rules in `docs/GIT_WORKFLOW.md`.

## 7. Toolchain notes

This project is developed with an agentic IDE (Antigravity), a multi-agent orchestrator
(Maestri), an AI UI generation step (Stitch), and Playwright for browser verification.
See `docs/AGENT_TOOLING.md`. Key rule: **UI generated by Stitch is a starting point, not a
deliverable** — it must be refactored to consume real backend APIs and to satisfy
`docs/UI_DESIGN_SYSTEM.md` before it counts as `Implemented`.

## 8. Read-order for a new agent

`CLAUDE.md` → `PROJECT_MASTER_SPEC.md` → `ARCHITECTURE.md` → your own charter in
`.claude/agents/<you>.md` → the spec for your module → `TASKS.md` → `DECISIONS.md`.
