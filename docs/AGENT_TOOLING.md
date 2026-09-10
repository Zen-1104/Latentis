# AGENT_TOOLING.md — Antigravity, Maestri, Stitch, Playwright

**Owner:** Lead Orchestrator · Referenced by `CLAUDE.md § 7`

## 1. Principle: tools produce drafts, gates produce deliverables

Four tools sit in this pipeline. Each accelerates a phase, and each has a characteristic failure mode
that would violate an invariant if left ungated. So every tool has an explicit **exit gate** it must
clear before its output counts as anything better than `Implemented` in the `CLAUDE.md § 4` vocabulary.

| Tool | Role | Characteristic failure | Exit gate |
|---|---|---|---|
| **Antigravity** | Agentic IDE — the environment agents write code in | Confident edits across ownership boundaries | INV-7 ownership table + `git status` review before every commit |
| **Maestri** | Multi-agent orchestrator — schedules the ten charters | Parallel agents racing on shared files; a phase reported done that is not | Phase quality gates; `TASKS.md` status is only advanced by the owning agent |
| **Stitch** | AI UI generation | Beautiful screens filled with **fabricated numbers** | `QG-FE-01`, the five-item refactor checklist — this is the highest-risk tool in the stack for INV-1 |
| **Playwright** | Browser verification + PDF rendering | Tests that assert elements exist rather than values are correct | Specs must assert numbers against the API payload (`RT-012`) |

## 2. Antigravity — working agreements

- **One agent, one branch, one concern** (`docs/GIT_WORKFLOW.md § 2`).
- Stage explicit paths; never `git add -A` from the root. Agentic edits touch more files than intended
  more often than a human's do, and the ownership table is the only thing standing between that and INV-7.
- Before any commit: `git status --short`. A file you do not own in the list means stop and write a
  handoff note.
- Re-read `CLAUDE.md` after any context compaction. It is the first line of that file for this reason.
- Long tasks write progress to `TASKS.md` incrementally, not at the end. An agent that loses context
  mid-task should be resumable from the file, not from memory.

## 3. Maestri — orchestration model

Ten charters in `.claude/agents/`. Dependencies are the phase graph in `TASKS.md`; parallelism is allowed
only where ownership sets are disjoint.

```
Phase 1  research-scientist ∥ product-ui-designer            (no code, no conflicts)
Phase 2  data-ml-engineer (datagen)                          → dataset artifacts
Phase 3  data-ml-engineer (core numerics) ∥ backend-engineer (API skeleton, DuckDB)
Phase 4  backend-engineer (wire core → API) ; frontend-engineer (generated client)
Phase 5  frontend-engineer (S1–S4) ∥ qa-playwright-engineer (specs from UX_SPEC)
Phase 6  red-team-auditor (RT-001..RT-012) ∥ docs-ppt-engineer
Phase 7  integration-release-engineer (gates, single test-split scoring, tag)
```

Rules that keep concurrency honest:

1. **The evaluation harness is built in Phase 3, before the second model** (R-build-order). A metric you
   cannot measure is a metric you will guess.
2. **Only the Integration & Release Engineer scores the test split**, once per tag (AG-5).
3. **Only the owning agent advances its own `TASKS.md` status.** An orchestrator marking a task done on
   an agent's behalf is how "done" decouples from reality.
4. **A blocked agent writes to `INTEGRATION_STATUS.md § Blocked` and continues with unblocked work.** It
   does not downgrade the requirement (`CLAUDE.md § 3`).
5. **`red-team-auditor` cannot be assigned implementation work.** An agent auditing its own code is not an
   audit.

## 4. Stitch — the highest-risk tool, and its gate

Stitch generates polished React screens quickly. It also, by its nature, fills them with **plausible
numbers**: `45.2 µA`, `17.4σ`, `LER 0.94`. Those are exactly INV-1 violations, and they look *more*
convincing than real output, which is what makes this the most dangerous tool in the pipeline.

**Standing rule:** Stitch output lands in `frontend/src/_generated_draft/`, which is **excluded from the
production build by the bundler config**. Nothing reachable at runtime ever comes straight from Stitch.

The five-item refactor checklist (`QG-FE-01`) that must pass before a screen is promoted out of that
directory:

1. **Real data.** Every value comes from a generated API client call. No inline arrays, no fixtures, no
   `USE_MOCK` flag anywhere in the tree.
2. **Tokens.** Every colour, spacing and font value replaced with `docs/UI_DESIGN_SYSTEM.md` tokens. Raw
   values are a lint error.
3. **`<Metric>` everywhere.** Every displayed number routed through the primitive that takes a
   `TracedValue` and nothing else — which makes this checkable by the type system rather than by review.
4. **All four states** implemented: loading, empty, error, degraded (`UX_SPEC § 6.2`).
5. **Accessibility.** `TEST-A11Y-001`: contrast, focus order, and no verdict encoded by colour alone.

A generated screen still holding a literal number where a `TracedValue` belongs is a **P0 blocker**, not a
cosmetic issue. `RT-008`'s static scan runs over `frontend/src/**` for exactly this.

## 5. Playwright — two jobs

### 5.1 Verification (`qa-playwright-engineer`)

Specs derived from the journeys in `UX_SPEC § 8`. The binding rule:

> A Playwright assertion on a decision-bearing number must compare the **rendered text** against the
> value fetched from the **API payload** in the same test, not against a literal in the spec file.

```ts
// correct: the API is the oracle
const inv = await api.get(`/components/${id}/investigation`);
const expected = fmt(inv.data.parameters[0].anomaly.dpat.z);
await expect(page.getByTestId('dpat-z')).toHaveText(expected);

// wrong: a hard-coded expectation, and it silently freezes a fabricated value into the suite
await expect(page.getByTestId('dpat-z')).toHaveText('17.4');
```

A literal expectation is a hard-coded number in the *test* — INV-1 in the place it is least likely to be
noticed, and it would keep passing after the pipeline broke. `RT-012` extends this to a three-way
comparison: UI text, API payload, and the rendered PDF must agree for a sampled part.

Every chart carries an accessible `<table>` fallback (`UI_DESIGN_SYSTEM § 6`) partly so Playwright has
exact values to assert against instead of pixels.

### 5.2 PDF rendering (`backend/reporting/`)

Reports are Jinja2 → self-contained HTML → PDF via Playwright's Chromium. Chosen because it reuses a
dependency the project already has; WeasyPrint or LaTeX would add system packages that break the
offline-clean-machine constraint (DMR-01). The renderer runs headless, offline, with local fonts, and
`TEST-REP-002` asserts the synthetic-data banner is present on page 1 and in every page footer.

## 6. Tool-boundary rules

| Rule | Reason |
|---|---|
| No tool may write to `reports/` except the pipeline scripts | Reports are `Measured` artifacts; a tool-authored report is a fabricated one |
| No tool output is committed without the owning agent's review | INV-7 |
| Generated code is committed with `generated:` in the commit body and the generator version | Auditability of what a human/agent wrote vs. what a tool wrote |
| Zod types and the API client are **generated** from OpenAPI, never hand-edited | Hand-edits reintroduce contract drift, the exact class of bug the generation eliminates |
| No tool may add a dependency without a lockfile commit and a rationale | NFR-07, SR-07 |
| No tool runs with network access during the demo | NFR-08, DMR-01 |

## 7. What no tool is allowed to produce

- A number presented as a result that is not traceable to a `reports/` artifact (INV-1).
- An explanation string written before the values exist (INV-5).
- A test weakened to make code pass (INV-6).
- A UI that renders when its backing model is unavailable, instead of disabling itself (`ARCHITECTURE § 9`).
- A commit that mixes generated draft code with reviewed production code.

The single sentence worth carrying out of this document: **the tools make the project fast; the gates make
it true.** Removing a gate to move faster removes the only thing distinguishing this submission from a
convincing mockup.
