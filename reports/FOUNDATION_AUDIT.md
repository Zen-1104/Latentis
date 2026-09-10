# FOUNDATION_AUDIT.md — Phase 0 Audit of the Specification Set

Owned by `red-team-auditor`. Dated **2026-09-05**, at Phase 0, before any code exists.

## 0. Why this file is hand-authored when `reports/**` is script-written

`docs/AGENT_TOOLING.md § 6` states that `reports/**` is written by pipeline scripts and that a hand-authored
report is a fabricated one. This file is the single documented exception, named in
`.claude/agents/red-team-auditor.md` and in `agents/README.md § 2`: there is no pipeline yet, and the object under
audit is the specification set itself.

**Finding F-06 below is against that inconsistency**, because a stated exception that only appears in two of the
three places is exactly the kind of gap this charter exists to find — including when the gap is its own.

## 1. Method

Read the twenty-seven Phase 0 documents plus the ten charters and the shared-state files, and attempt to falsify
four claims: that the set is internally consistent; that each invariant in `CLAUDE.md § 1` has an enforcement
mechanism; that every forward reference resolves; and that nothing already over-claims.

No code was run, because none exists. `tests/tests.json` was machine-validated (valid JSON, 121 entries, no
duplicate IDs, uniform keys, seven categories) — that is the only mechanical check available at this phase.

## 2. The independence problem, stated first

**This audit is weak and the reason must be on the record.** It was produced by the same process that wrote the
documents it audits, in the same session, from the same context. An agent auditing its own output is not
auditing; it is proofreading with extra steps.

What that means concretely:

- Findings below are real (each names a specific file, line of reasoning, or contradiction), but the *absence* of
  a finding is worth very little. A shared blind spot produces a clean report.
- The genuine independence in this project arrives later and from three sources: the `RT-001`..`RT-012` suites
  running against *artifacts* rather than intentions, `HUMAN-005` (domain-expert review of the physics), and
  `HUMAN-008` (a human reading for proprietary-content and over-claiming risk).
- Until those run, **`FOUNDATION_AUDIT.md` is evidence that the specification set is self-consistent, and nothing
  more.** It is not evidence that the approach is correct.

Recording this is not modesty. A Phase 0 audit presented as independent verification would itself be the first
over-claim in the project.

## 3. Red-team suite status at Phase 0

Twelve rows, as required. `NOT_RUN` is reported with its reason and never omitted, because a missing row reads as
a pass.

| ID | Verdict | Reason |
|---|---|---|
| RT-001 | **FAIL** | Confirmed by inspection. See F-01. |
| RT-002 | NOT_RUN | No feature pipeline exists; the three probes require emitted artifacts. |
| RT-003 | NOT_RUN | No built bundle. |
| RT-004 | NOT_RUN | No decision path to permute identities through. |
| RT-005 | NOT_RUN | No implementation to mutate; corpus does not exist (see `BL-004`). |
| RT-006 | NOT_RUN | No attribution implementation; no injected confounds. |
| RT-007 | NOT_RUN | No payloads to re-derive. This is the flagship suite and its rate is currently undefined, not 1.0. |
| RT-008 | NOT_RUN | AST scan requires Python source. **Vacuously clean is not clean** — recorded as `NOT_RUN`, not `PASS`. |
| RT-009 | NOT_RUN | Fifteen degenerate inputs need an interface to submit them to. |
| RT-010 | NOT_RUN | No `risk_index` to sweep weights against. |
| RT-011 | NOT_RUN | No guard implementation; no shifted corpus. |
| RT-012 | NOT_RUN | No UI, no API, no PDF. |

Eleven `NOT_RUN` and one `FAIL` is the correct Phase 0 report. A Phase 0 audit showing passes would mean the
suites were written to be satisfiable by documents, which would make them worthless later.

---

## 4. Findings

Severity: **S1** blocks the tag · **S2** blocks a claim · **S3** should be fixed · **S4** noted.

### F-01 · S1 · `RT-001` fails: illustrative numbers are indistinguishable from results

**Confirmed.** The worked examples contain numbers that resolve to no `reports/` artifact, because no artifact
exists: `45.2 µA`, lot median `10.4`, `IQR 2.7`, robust σ `2.0`, DPAT limit `22.4`, `17.4 σ`, `D² = 41.7`, the
forecast triple `32.3 / 39.8 / 58.3`, `slope_ratio 0.67`, and `LER 0.94`. They appear in
`docs/EXPLAINABILITY_SPEC.md`, `models/anomaly/ANOMALY_SPEC.md`, `models/drift/DRIFT_SPEC.md`,
`models/RISK_SCORING_SPEC.md`, `docs/AGENT_TOOLING.md` and `tests/tests.json` oracle strings.

**Why this is S1 rather than cosmetic:** a reader cannot distinguish `17.4 σ` in a spec from `17.4 σ` as a
measurement, and `tests/tests.json` currently encodes `22.4` as a *known-answer oracle* — which is legitimate
(it is hand-computed arithmetic, `10.4 + 6 × (2.7 / 1.35) = 22.4`, and that is exactly what a known-answer test
should assert), but the same digits used illustratively three documents away are not.

**Required:** `T-703`. Each occurrence is either (a) replaced by a value read from a committed artifact,
(b) kept as arithmetic with the hand-computation shown inline — legitimate for known-answer oracles, or
(c) relabelled `ILLUSTRATIVE — not a measurement` at the point of use.
**Not acceptable:** an `RT-001` exemption. There are exactly three exemption kinds and "it is only an example" is
not one of them.

**Tracked:** `BL-002`.

### F-02 · S2 · The definition of done is unsatisfiable in Phase 0, and the register says `DONE` anyway

`CLAUDE.md § 2` requires, for `DONE`: a commit with a meaningful message (1), unit tests that run and pass (2),
reachability from the running application (3), and a commit hash in `TASKS.md` (4). Thirty-five Phase 0 rows are
marked `DONE`; none satisfies (1), (2), (3) or (4), and every `Commit` cell reads `—`.

This is **honestly disclosed** (`BL-003`, and the `TASKS.md` preamble says the repository is not initialised
rather than fabricating hashes), so it is not a fabrication finding. It is a definitional one: the register uses
`DONE` in a second sense that `CLAUDE.md` does not define.

**Recommended:** add a Phase 0 clause to `CLAUDE.md § 2` — for specification-only tasks, conditions 2 and 3 are
`n/a` and 1 and 4 are deferred to `T-036` — **or** introduce a distinct status `SPECIFIED` for these rows. The
second is cleaner, because a reader scanning the register for progress should not see thirty-five `DONE` rows and
conclude that anything works.
**Do not** resolve this by loosening `CLAUDE.md § 2` generally.

### F-03 · S2 · `QG-DOC-01`'s traceability claim has never been checked

`tests/TEST_MATRIX.md` asserts bidirectional requirement ↔ test coverage, and `tests/tests.json` carries 121
entries with `req` arrays. The check that they agree — `scripts/check_traceability.py` — does not exist (`T-106`).

Every traceability statement in the foundation is therefore **asserted by hand and unverified**. The `req` strings
were typed, not resolved: a requirement ID that does not exist in `PROJECT_MASTER_SPEC.md`, or a P0 requirement
with no test, would currently be invisible.

**Recommended:** promote `T-106` to run immediately after `T-101`, before any module work. It is a short script
and it audits a claim the whole test strategy rests on. Also have it fail on an *unknown* requirement ID, not
merely on an uncovered one — the typo direction is the one hand-review misses.

### F-04 · S3 · `HO-004` overstates `RT-008`'s reach

`INTEGRATION_STATUS.md § HO-004` requires `1.35` and `1.4826` to appear "**exactly once each** in the whole
repository". `RT-008` is an **AST scan of Python source** (`tests/RED_TEAM_PLAN.md § RT-008`) — it cannot see
Markdown, TypeScript, JSON or YAML.

Right now `1.35` appears in at least five documents (`ANOMALY_SPEC.md`, `DECISIONS.md § D-003`,
`PRESENTATION_SPEC.md § S05`, `HUMAN_ACTIONS.md § HUMAN-002`, this file), all legitimately, all as prose. Under
`HO-004`'s literal wording the repository is already in violation of a rule that its enforcing test does not
actually apply.

**Why it matters:** a rule whose stated scope exceeds its enforcement is worse than a narrower rule, because the
first agent to notice the gap learns that the rules here are approximate.

**Recommended:** amend `HO-004` to "exactly once in Python source under `backend/`, `datagen/` and `models/`",
which is what `RT-008` checks. Separately consider extending the AST scan to TypeScript — a hard-coded `1.35` in
`frontend/src/**` would be a real INV-1 violation and is currently outside every scan except `QG-FE-03`'s bundle
check.

### F-05 · S2 · Two fallback ladders interact and no document says which wins

`models/anomaly/ANOMALY_SPEC.md` defines a small-lot ladder for when a lot is below the DPAT robustness floor.
`models/CONFORMAL_SPEC.md § 3` defines a four-level Mondrian ladder for when a calibration group is thin. A part
in a small lot *and* a thin conformal group hits both, and neither spec states the precedence or what the combined
evidence marker should be.

This is not hypothetical: a small lot of an unusual technology is precisely the case that triggers both, and it is
also the case where an over-confident answer does the most damage.

**Recommended:** a `DECISIONS.md` entry fixing the precedence, the combined payload shape (both `dpat_fallback`
and `mondrian_level` present, independently), and the rule that the *weaker* of the two determines the
`--evidence-weak` marker. Add a test row to `tests/tests.json` for the combined case — the register currently has
`TEST-STAT-006` and `TEST-CONF-004` separately and nothing for their intersection.

### F-06 · S3 · The `reports/**` write rule is stated in three places with two different scopes

`docs/AGENT_TOOLING.md § 6`: `reports/**` is written by pipeline scripts; a hand-authored report is a fabricated
one — stated without exception. `agents/README.md § 2` and `.claude/agents/red-team-auditor.md`: the auditor owns
`reports/FOUNDATION_AUDIT.md` and `reports/RED_TEAM_<tag>.md`.

The exception is real and correct — an audit of the specification set cannot be script-generated — but
`AGENT_TOOLING § 6` is the document an agent is most likely to read first, and it says the opposite.

**Recommended:** amend `AGENT_TOOLING § 6` to name the two auditor files explicitly as the only exception, and
have `check_no_fabricated_numbers.sh` treat them as such rather than relying on an agent to remember. A rule with
an unstated exception gets discovered as a contradiction, and the discovering agent then has to guess which side
is authoritative.

### F-07 · S2 · "Escape Set non-empty" is too weak for a release blocker

`T-209` / `TEST-GEN-004` blocks the release on the Escape Set being **non-empty** and all members being inside all
absolute limits. A set of size 1 satisfies that, and Latent Escape Recall — the headline metric (`D-012`) — would
then be a one-of-one statistic reported as a rate.

`FINAL_STATUS.md § L-13` already acknowledges the small denominator and requires a Clopper–Pearson interval, which
is the right mitigation but not a floor. With `n = 1`, the 95 % interval on a perfect score runs from roughly 0.03
to 1.0, and printing "LER 1.00" beside it is technically honest and practically misleading.

**Recommended:** set a minimum Escape Set size in `data/DATASET_SPEC.md` chosen so the interval is narrow enough
to be worth quoting, make `TEST-GEN-004` assert that floor rather than non-emptiness, and state the floor on S09.
If the generator cannot produce it, that is a corpus-design finding, which is what the blocker should surface.

### F-08 · S2 · `bound: INFINITE` has a payload state and no UI state

`models/CONFORMAL_SPEC.md § 2` specifies that when `k > n_cal_g` the response carries `bound: INFINITE` with
`attainable_alpha`. `docs/UX_SPEC.md` specifies four states per surface — loading, empty, error, degraded.
`INFINITE` is none of them: it is a successful response containing a value that cannot be plotted, compared to a
limit, or formatted by `<Metric>`, whose prop type is `{ traced: TracedValue }` with a `float` value.

Left unspecified, the likely implementations are all wrong: `Infinity` through the formatter (renders `∞` or
`NaN`), a very large sentinel number (a fabricated value, INV-1), or falling back to the point forecast (silently
defeating `D-010`).

**Recommended:** specify it now, in `UX_SPEC.md` and `UI_DESIGN_SYSTEM.md`, as a distinct render — the bound cell
shows "no bound at α = 0.10 (n = 4; attainable α = 0.20)" with `--evidence-weak`, the forecast chart draws no
upper band, and the safety verdict reads `INSUFFICIENT_CALIBRATION` rather than any band. Add a row to
`tests/tests.json` and an `E2E-STATE-*` spec. `RT-009` row 3 is adjacent to this but tests for `NaN` on screen,
which would catch the symptom and not the cause.

### F-09 · S3 · `INV-6`, `INV-7` and `INV-9` have no automated enforcement, and one of them has no independent check at all

`tests/TEST_MATRIX.md` already discloses that these three are process gates rather than tests, and that
`scripts/check_test_deltas.sh` is "a heuristic aid for reviewers, not a proof". That disclosure is correct. The
residual finding is narrower:

- **INV-6** (tests never weakened) — the mechanism is a `DECISIONS.md` entry plus the Lead Orchestrator's
  sign-off. If the Lead Orchestrator is the one proposing the weakening, the mechanism has no counterparty. The
  written-objection requirement helps only if an agent objects.
- **INV-7** (no silent overwrite) — enforceable only by review; git history makes it *detectable* after the fact,
  which is the practical safeguard, and no document says so.
- **INV-9** (never claim an untested capability) — `QG-DOC-02` covers claims in `README.md`, `FINAL_STATUS.md` and
  `presentation/**`, and does not cover claims made in *spec documents*, which is where present-tense phrasing
  about unbuilt features naturally appears.

**Recommended:** for INV-6, require the objection to be recorded by a *named* charter other than the proposer, and
if none objects, record that explicitly ("no charter objected") — an empty field and an unanimous agreement should
not look identical. For INV-9, extend `QG-DOC-02`'s scan to `docs/**` and `models/**`.

### F-10 · S3 · Reproducibility will break on the PDF, for a legitimate reason

`INV-8` requires byte-identical output for the same seed, and `CLAUDE.md § 5` permits `datetime.now()` in
metadata. The PDF export contains a generation timestamp (metadata, therefore permitted), which means **PDF bytes
will differ between two otherwise identical runs**.

If `scripts/verify_reproducibility.sh` hashes the PDF, it fails on every run for a reason that is not a defect —
and the likely response under time pressure is to stop hashing the PDF, which quietly removes the check that the
*report content* is stable.

**Recommended:** state in `docs/PROVENANCE_SPEC.md` that reproducibility for the PDF is asserted over its
**extracted text with the timestamp line removed**, not its bytes, and have `verify_reproducibility.sh` implement
exactly that. Compare dataset and model artifacts byte-wise, as specified; compare the PDF semantically.
`RT-012`'s three-way agreement check is unaffected either way.

### F-11 · S4 · Present-tense phrasing in spec documents will read as implementation

Spec documents describe behaviour in the present indicative — "the guard fires", "the API returns", "the frontend
renders". That is normal specification prose and each file's header says it is a specification. But `RT-001` and
`QG-DOC-02` scan for *claims*, and a reader arriving mid-document cannot tell a specified behaviour from an
implemented one.

**Recommended:** no rewrite — the cost exceeds the benefit and rewriting twenty-seven documents into the
subjunctive would make them harder to read. Instead, require the one-line status banner already present in some
files to appear in **all** of them: `Status: Specified — no implementation exists as of <date>`. Cheap, and it
puts the disclaimer where a scanner and a human both find it.

---

## 5. Checks performed that found nothing

Reported because a finding list without them is uninterpretable — a reader cannot tell what was examined from what
was merely not mentioned.

| Check | Result |
|---|---|
| Every gate ID referenced in any document (`QG-*`) is defined in `tests/QUALITY_GATES.md` | 18 defined, all referenced IDs resolve |
| Every `RT-nnn` referenced anywhere is defined in `tests/RED_TEAM_PLAN.md` | RT-001..012, all resolve |
| Every `INV-n` referenced resolves to `CLAUDE.md § 1` | INV-1..10, all resolve |
| `tests/tests.json` structural validity | valid JSON, 121 entries, no duplicate IDs, uniform key sets, 7 categories |
| No `tests.json` entry declares "current output" as its oracle | none; the field definition also declares it invalid |
| Charter file-ownership sets are pairwise disjoint | disjoint; `frontend/src/api/generated/**` and `reports/**` deliberately unowned |
| No charter is assigned both implementation and audit of the same area | `red-team-auditor` has no implementation scope |
| Every `TASKS.md` dependency points to an existing row | all resolve; no cycles |
| Status vocabulary used consistently in `FINAL_STATUS.md` | 20 capabilities, all `Specified`, none over-stated |
| `HUMAN_ACTIONS.md` contains no credential, key, token or connection string | none present |
| Any phrasing implying ISRO operational data | none found in the twenty-seven documents |
| The word `validated` applied to the physics model | not present; `HUMAN-005` is open for exactly this |
| `accuracy` used for the screening task | not present; `D-012` and the banned list both cover it |
| Deck contains a result number at Phase 0 | S10 is a frame with paths and no digits, as specified |

## 6. What could not be checked at all

- **Whether the approach works.** Nothing in this audit bears on that. It is decided by `T-406` and reported
  whatever it says (`D-030`).
- **Whether the physics model is plausible.** `HUMAN-005`. An agent cannot substitute for a practitioner here and
  should not appear to.
- **Whether the AEC-Q001 formulas are as we read them.** `HUMAN-002` / `BL-001`. The citation stays MEDIUM.
- **Whether any number in a *figure*** resolves to an artifact. There are no figures yet, and when there are, the
  `RT-001` text scan cannot see inside an SVG's rendered text. `PRESENTATION_SPEC § 9` item 1 makes this a manual
  check; that is the weakest item on the pre-flight list and it should stay flagged as such.
- **Whether the eight-minute script fits.** `HUMAN-009`.

## 7. Verdict on Phase 0 exit

**Phase 0 exit: PASS, with one S1 and five S2 findings recorded.**

The specification set is internally consistent, every forward reference resolves, every invariant has a named
enforcement mechanism (three of them process-only, disclosed in F-09), and nothing in it claims a capability that
exists. `RT-001` fails, and that failure is scheduled (`T-703`, `BL-002`) rather than excused.

Phase 0 exit does not require any quality gate to pass — all eighteen are `NOT_RUN`, which
`INTEGRATION_STATUS.md` records explicitly rather than leaving blank.

### Required before Phase 1 work begins

1. **F-03** — bring `scripts/check_traceability.py` forward to immediately after `T-101`. The whole test strategy
   rests on a claim that has never been checked in either direction.
2. **F-04** — amend `HO-004` to match `RT-008`'s actual scope. A rule that overstates its enforcement teaches
   agents that the rules are approximate, and that lesson is expensive to un-teach.
3. **F-02** — resolve the `DONE`/`SPECIFIED` ambiguity before thirty-five more rows inherit it.

### Required before the tag

4. **F-01** (`T-703`), **F-05**, **F-06**, **F-07**, **F-08**, **F-10**. Each has a named recommendation above;
   none needs a decision that cannot be made now.

### Standing caveat

Re-read § 2. This audit's `PASS` means the documents agree with each other. The suites that mean something run
against artifacts, and they have not run.

---

**Signed:** `red-team-auditor` · 2026-09-05 · commit `—` (repository not yet initialised, `BL-003`)




