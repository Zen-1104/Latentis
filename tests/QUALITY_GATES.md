# QUALITY_GATES.md — The Gates, Their Evidence, and Who May Pass Them

**Owner:** Integration & Release Engineer · Referenced by every charter in `.claude/agents/`

## 0. The three rules that make a gate a gate

1. **A gate is passed by evidence, not by assertion.** Each gate below names the artifact that proves it.
   No artifact ⇒ the gate is `NOT_PASSED`, regardless of anyone's confidence.
2. **A gate cannot be waived.** It can be *recorded as failed*, which downgrades the dependent claim in
   `FINAL_STATUS.md` (INV-9). "Waived for the demo" is not an available state, and this is deliberate: under
   deadline pressure a waiver mechanism is used exactly once and then always.
3. **Only the named authority may pass a gate**, and for release gates that authority is never the agent
   whose work is being gated (`AGENT_TOOLING § 3`, rule 5).

Gate state is recorded in `INTEGRATION_STATUS.md`, one row per gate, with the evidence path and the commit
it was evaluated at. A gate evaluated at an older commit is `STALE`, which counts as `NOT_PASSED` for a tag.

## 1. Data gates

### QG-DATA-01 — A dataset artifact is usable

| | |
|---|---|
| **Authority** | Data & ML Engineer |
| **Evidence** | `reports/DATASET_PROFILE.md` + the artifact's `manifest.json` |

- `TEST-GEN-001` passes: every generator parameter carries `cited` \| `derived` \| `assumed`.
- **`TEST-GEN-004` passes**: `S1 ∪ S2` is non-empty and **every** member is inside **every** absolute limit
  at every read-point. This is the release blocker of the whole project — if it fails, the flagship claim
  ("conventional screening ships this part") has no example, and no other work can compensate.
- `TEST-GEN-005` passes: labels re-derived from emitted values, independently of generator intent.
- `TEST-DL-002`, `TEST-DL-003`: no late-read-point column and no correlate of one in `screening.parquet`.
- `TEST-PROV-004`: `data_provenance` is a single-member enum.
- Achieved prevalence, imperfection rates and correlations are **measured and published**, not configured
  and assumed (`TEST-GEN-006..008`).

### QG-DATA-02 — Splits are trustworthy

| | |
|---|---|
| **Authority** | Data & ML Engineer, countersigned by Red-Team Auditor |
| **Evidence** | `reports/DATASET_PROFILE.md § Splits` |

- `TEST-SPLIT-001`: train / calib / test are lot-disjoint, verified **from the emitted artifact**, never from
  the script that wrote it.
- The `test` split's truth columns are readable by exactly one code path: the release scoring script (AG-5).
- Calibration set size per Mondrian group is published, with the `attainable_alpha` for each — so a group too
  small to support the configured `α` is visible before anyone quotes a coverage number.

## 2. Model gates

### QG-MODEL-01 — A model artifact is registrable

| | |
|---|---|
| **Authority** | Data & ML Engineer |
| **Evidence** | `models/registry/<name>/<version>/{manifest.json, MODEL_CARD.md}` |

An artifact that fails any item is **not registered**, which means the API reports `degraded` and the
dependent UI panels disable themselves. It does not mean "registered with a caveat".

1. `MODEL_CARD.md` present and passing `scripts/validate_model_card.py` (all 13 sections).
2. `manifest.json` with training data hash, config hash, code git SHA, library versions, seed, and
   `dirty_worktree: false` — a dirty worktree is **fatal for a release artifact**.
3. **Section 7 baseline comparison present.** An artifact with no baseline comparison is unregistrable, so
   "better than nothing" can never be the standing of a shipped model.
4. **Section 8 links the ablation row that justifies its existence** (AG-10). No row ⇒ the artifact is
   deleted, not kept.
5. Section 10 slice performance reported across `component_type`, `thermal_zone`, `socket_id`, `tester_id`,
   lot size and quality band.
6. Section 12 reproduction commands run, and the resulting artifact hash matches the asserted one.
7. Fitted on `train` only, verified by the instrumented loader (`TEST-DL-004`).

### QG-MODEL-02 — An evaluation number may be published

| | |
|---|---|
| **Authority** | Integration & Release Engineer, **exclusively** |
| **Evidence** | `reports/METRICS_<tag>.json` with the run's git SHA and dataset hash |

- The metric was produced by the real pipeline on generated data, and the run is reproducible
  (`Measured`, per `CLAUDE.md § 4`). A number computed in a notebook is not `Measured`.
- Every accuracy-style figure is published **beside** its counterpart: LER beside FPR and flag rate; MAE
  beside the naïve-linear baseline; coverage beside its Clopper–Pearson interval.
- The `test` split was scored **once** for this tag. A second scoring run after seeing the first is a
  protocol violation (AG-5) and invalidates the tag rather than replacing the number.
- Every figure quoted anywhere else resolves into this file (`RT-001`).

## 3. Frontend gates

### QG-FE-01 — A generated screen may leave `_generated_draft/`

| | |
|---|---|
| **Authority** | Frontend Engineer, countersigned by Product & UI Designer |
| **Evidence** | The promotion commit's diff + `TEST-FE-ARCH-001` |

This is the Stitch gate, and it is the highest-risk boundary in the repository
(`AGENT_TOOLING § 4`) because generated screens are filled with plausible numbers that look *more* credible
than real output.

1. **Real data.** Every value comes from a generated API client call. No inline array, no fixture, no
   `USE_MOCK`.
2. **Tokens.** Every colour, spacing and type value replaced with a `UI_DESIGN_SYSTEM` token.
3. **`<Metric>` everywhere.** Every displayed number routed through the primitive whose only prop is
   `{ traced: TracedValue }` — so this item is enforced by the type checker rather than by review.
4. **All four states** implemented: loading, empty, error, degraded.
5. **Accessibility.** `TEST-A11Y-001`: contrast, focus order, and no verdict encoded by colour alone.

A promoted screen still holding a literal where a `TracedValue` belongs is a **P0 blocker**, not a cosmetic
issue.

### QG-FE-02 — Token discipline

| | |
|---|---|
| **Authority** | Frontend Engineer |
| **Evidence** | `TEST-FE-LINT-001` in the `fast` CI job |

Raw hex colours, `rgb()`, and `px` literals outside the token layer are lint **errors**, not warnings. A
warning in a hurry is a warning ignored.

### QG-FE-03 — No fabricated value, no mock path

| | |
|---|---|
| **Authority** | Red-Team Auditor |
| **Evidence** | `RT-008` output + `TEST-FE-ARCH-001` run against the **built bundle** |

The bundle is the oracle, not the source tree: a fixture module can be imported through a path the source
scan misses, and only the build output settles what actually ships.

## 4. Backend, contract and architecture gates

### QG-API-01 — The contract is generated, not maintained

| | |
|---|---|
| **Authority** | Backend Engineer |
| **Evidence** | `TEST-API-001` — regenerate the client and diff against the committed one; a non-empty diff fails |

Hand-editing the generated client is impossible to do quietly, which is the point. Also required:
`TEST-API-002` (`meta` envelope on every route enumerated from the OpenAPI document),
`TEST-API-004` (closed error enum reachable in both directions, `remediation` on every 4xx), and
`TEST-API-005` (**no `5xx` anywhere in the adversarial corpus** — every one is a P1 defect).

### QG-API-02 — Provenance at the boundary

| | |
|---|---|
| **Authority** | Backend Engineer, countersigned by Red-Team Auditor |
| **Evidence** | `TEST-PROV-001..005` |

Unit never blank; `inputs` keys equal the registry's declared operands; **no bare float on any
decision-bearing response field**; single-member provenance enum; dispositions append-only. Item three is the
structural one — it is how INV-1 becomes a schema property instead of a rule people must remember.

### QG-ARCH-01 — Boundaries hold

| | |
|---|---|
| **Authority** | Red-Team Auditor |
| **Evidence** | `TEST-ARCH-001` static import graph, in the `full` CI job |

`backend/core` imports no `datagen`, no `app`, and no I/O module. `datagen` imports no model code (DR-10).
This gate is cheap and it is the one that keeps the "the generator was written against a frozen spec before
the detector" claim verifiable rather than historical.

### QG-CORE-01 — Every numeric function has a real oracle

| | |
|---|---|
| **Authority** | Data & ML Engineer |
| **Evidence** | `scripts/check_test_categories.py` reading `tests/tests.json` |

Every public function in `backend/core/**` is named by at least one test whose category is `known-answer`,
`property` or `differential`. Coverage floors (`TEST_STRATEGY § 7`) apply *in addition* — they are a floor,
and this gate is the actual requirement, because 100 % coverage by snapshot assertions would satisfy the
number and prove nothing.

## 5. Documentation and traceability gates

### QG-DOC-01 — Traceability is maintained

| | |
|---|---|
| **Authority** | QA & Playwright Engineer |
| **Evidence** | `scripts/check_traceability.py` |

Every **P0** requirement in `PROJECT_MASTER_SPEC.md` appears in `tests/TEST_MATRIX.md` with at least one test
ID, and every ID in the matrix exists in `tests/tests.json`. Bidirectional, so the matrix cannot rot into
decoration.

### QG-DOC-02 — Status vocabulary is honest

| | |
|---|---|
| **Authority** | Red-Team Auditor |
| **Evidence** | A written audit note in `reports/RED_TEAM_<tag>.md` |

Every capability claim in `README.md`, `FINAL_STATUS.md` and `presentation/**` is checked against the
vocabulary in `CLAUDE.md § 4`. A `Verified` claim must name its passing test; a `Measured` number must name
its artifact. This is a **process gate, not a script**, and saying so is more useful than pretending
otherwise.

## 6. Release gates

### QG-REL-01 — The suite is green on the tagged commit

Authority: Integration & Release Engineer. All unit, property, integration and contract tests pass; coverage
floors met; `QG-CORE-01`, `QG-ARCH-01`, `QG-DOC-01` passed at this commit.

### QG-REL-02 — The nightly suite has passed on this exact commit

Authority: Integration & Release Engineer. Evidence: the nightly job's run URL/log for the tagged SHA — all
five Playwright journeys, `TEST-A11Y-001`, `E2E-PERF-*`, PDF rendering, `RT-012`.

This gate is what makes it acceptable to keep the full E2E suite off the per-push job
(`PLAYWRIGHT_STRATEGY § 14`). Without it, that trade would quietly convert into missing coverage at release.

### QG-REL-03 — Reproducibility verified

Authority: Integration & Release Engineer. Evidence: `scripts/verify_reproducibility.sh` output committed
under `reports/`. Regenerate from the recorded seed and config, compare SHA-256; retrain, compare artifact
hashes; re-score, compare metrics (INV-8). **Any drift blocks the tag**, because a drift means every published
number belongs to a run nobody can reconstruct.

### QG-REL-04 — All twelve red-team suites reported

Authority: Red-Team Auditor. Evidence: `reports/RED_TEAM_<tag>.md` with twelve rows, each `PASS`, `FAIL` or
`NOT_RUN` **with its reason**. A missing row fails the gate — an absent row reads as a pass, which is the
easiest way for an audit to mislead. Release-blocking suites (`RED_TEAM_PLAN § 13`) must be `PASS`.

### QG-REL-05 — Offline from a clean clone

Authority: Integration & Release Engineer. Evidence: a transcript of `scripts/bootstrap.sh` on a fresh clone
with networking disabled, ending with a successful investigation request and a rendered PDF. This is the demo
condition (DMR-01), so it is verified rather than assumed.

## 7. Phase gate matrix

| Phase | Gates that must pass to exit |
|---|---|
| 1 — research & design | `QG-DOC-01` (matrix exists and resolves), design tokens frozen |
| 2 — dataset | `QG-DATA-01`, `QG-DATA-02` |
| 3 — core numerics + API skeleton | `QG-CORE-01`, `QG-ARCH-01`, `QG-API-01` |
| 4 — wiring | `QG-API-02`, `QG-MODEL-01` for every registered artifact |
| 5 — frontend | `QG-FE-01`, `QG-FE-02`, `QG-FE-03` |
| 6 — audit | `QG-REL-04`, `QG-DOC-02` |
| 7 — release | `QG-REL-01..05`, `QG-MODEL-02` |

## 8. The failure path

A gate that will not pass before the deadline has exactly one honest resolution: **the dependent claim is
downgraded**. `Verified` becomes `Implemented`; a measured number is removed rather than estimated; a feature
is described as `Specified` in `FINAL_STATUS.md` with the gate that blocked it named.

This is written down in advance because the decision is easy now and hard at 2 a.m. on 29 September. A
submission that says "this component is `Implemented`, not `Verified`, because `RT-006` row 5 fails and here
is the output" is stronger under expert judging than one that claims everything and folds under one question.


