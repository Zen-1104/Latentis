# scripts/ — Inventory, Contracts, Gates

Owned by `integration-release-engineer`. Every script that exists is listed here with its contract. A script not
in this table does not belong in `scripts/`.

**Status: Specified — no implementation exists as of 2026-09-05.** This file is the contract the scripts will be
written against (`T-101`, `T-106`, `T-210`, `T-704`, `T-705`).

## Conventions, binding on every script here

1. **Exit code is the verdict.** `0` pass, non-zero fail. No script prints `WARNING` and exits `0` for a condition
   that should block — a warning that blocks nothing is a warning nobody reads.
2. **Deterministic.** No unseeded randomness, no `date` inside a comparison, no network. The one exception is
   `bootstrap.sh --online`, which is explicitly flagged and is not what `QG-REL-05` runs.
3. **No script writes outside its declared outputs**, and no script writes to `reports/**` unless the table below
   says it does. The two auditor-authored files under `reports/` are the documented exception
   (`FOUNDATION_AUDIT.md § F-06`).
4. **Every script is runnable standalone**, from the repository root, with no arguments beyond those documented.
   A script that only works inside CI is a CI step, not a script.
5. **Failure output is the actual output.** Print the offending file, line, value and expectation — never
   "validation failed". The reader is an agent or a human at 2 a.m.; both need the specifics.
6. **`--help` on every script**, and it lists the gate the script serves.

---

## Gate-enforcing checks

### `check_secrets.sh` · INV-10 · pre-commit + `fast` + `full`

- **Contract:** scan the working tree for credential patterns — private keys, `AWS`/cloud key shapes, bearer
  tokens, `password=`, `.env` contents, connection strings with embedded credentials.
- **Explicitly includes `HUMAN_ACTIONS.md`**, which is the file most likely to attract a pasted credential
  because its whole purpose is "a human must act".
- **Inputs:** tracked files plus staged changes. **Outputs:** stdout only.
- **Exit:** non-zero on any match, printing file and line number but **not** the matched value.
- **Never bypassed.** `--no-verify` is prohibited (`docs/GIT_WORKFLOW.md`); a hook that can be skipped is a hook
  that will be.

### `check_traceability.py` · `QG-DOC-01` · `fast`

- **Contract:** verify `tests/TEST_MATRIX.md`, `tests/tests.json` and `PROJECT_MASTER_SPEC.md` agree **in both
  directions**: every requirement ID in `tests.json` exists in the master spec; every P0 requirement has at least
  one test; every test in the matrix appears in the register with the same requirement set.
- **The unknown-ID direction is the important one.** A typo'd requirement ID currently reads as coverage, and hand
  review does not catch it (`FOUNDATION_AUDIT § F-03`). Fail on unknown IDs, not only on uncovered requirements.
- **Inputs:** the three files. **Outputs:** stdout; a machine-readable summary on `--json`.
- **Exit:** non-zero on any mismatch, listing each with its direction.
- **Priority:** brought forward to immediately after `T-101` per `FOUNDATION_AUDIT § 7.1`.

### `check_test_categories.py` · `QG-CORE-01` · `fast`

- **Contract:** every entry in `tests/tests.json` declares one of the five legitimate oracles; the declared `path`
  resolves to a real test once tests exist; no entry's oracle string is empty or contains "current output",
  "existing behaviour", "as implemented", or a snapshot reference for a numeric assertion.
- **Inputs:** `tests/tests.json`, plus the test tree for path resolution. **Outputs:** stdout.
- **Exit:** non-zero on any invalid oracle or unresolvable path.
- **Note:** this checks the *declaration*. Whether the oracle is honest is a review judgement
  (`qa-playwright-engineer`), and the script does not pretend otherwise.

### `check_no_fabricated_numbers.sh` · `RT-001` aid · `full`

- **Contract:** scan `README.md`, `presentation/**`, `FINAL_STATUS.md` and `docs/**` for numeric literals and
  resolve each against `reports/**`. Report every unresolved number with its file and line.
- **Exemptions:** exactly the three kinds in `tests/RED_TEAM_PLAN.md § RT-001`, declared inline at the point of
  use. "It is only an example" is not one of them.
- **Known blind spot, stated:** it cannot see text rendered inside an SVG or an image. `PRESENTATION_SPEC § 9`
  item 1 covers that by eye and is the weakest item on that checklist.
- **Exit:** non-zero on any unresolved number.
- **This script is an aid to `RT-001`, not `RT-001`.** The suite is owned by `red-team-auditor` and runs
  independently; this one exists so a developer finds the problem before the audit does.

### `check_test_deltas.sh` · INV-6 heuristic aid · pre-commit (advisory)

- **Contract:** in a commit that touches both a test file and the implementation it covers, print the test diff and
  ask the author to confirm a `DECISIONS.md` entry exists. Also flag assertions that became weaker in shape —
  a removed `assert`, a widened tolerance, an added `pytest.mark.skip`, a changed expected value.
- **Exit:** `0` always in advisory mode; non-zero with `--strict` in the `full` job when a test file changed in the
  same commit as its implementation *and* no `DECISIONS.md` entry was added.
- **Stated plainly:** this is a **heuristic aid for reviewers, not a proof.** A determined weakening passes it. INV-6
  is a process gate and this script does not convert it into an automated one
  (`tests/TEST_MATRIX.md`, closing section; `FOUNDATION_AUDIT § F-09`).

### `validate_model_card.py` · `QG-MODEL-01` · `full`

- **Contract:** every model card has all thirteen sections from `models/MODEL_CARD_TEMPLATE.md`, no section is
  empty or contains a template placeholder, every metric cited resolves to `reports/METRICS_<tag>.json`, and the
  intended-use and limitations sections are non-empty.
- **Inputs:** `models/**/MODEL_CARD.md`, `reports/METRICS_<tag>.json`. **Outputs:** stdout.
- **Exit:** non-zero on any missing section, placeholder, or unresolvable metric.

### `generate_openapi.py` · `QG-API-01` · `fast` (via `api-contract`)

- **Contract:** dump the served OpenAPI 3.1 document to
  `frontend/src/api/generated/openapi.json` (generated, never hand-edited).
  `--check` exits non-zero on any diff against the committed file.
- **Inputs:** the live FastAPI app (throwaway store, never the demo file).
- **Note:** importing the app module builds its default state, so the script
  points `LATENTIS_DB_PATH` at a scratch database first.

### `generate_ts_client.py` · `QG-API-01` · `fast` (via `api-contract`)

- **Contract:** render `frontend/src/api/generated/client.ts` (interfaces +
  route table) deterministically from the committed `openapi.json` using
  stdlib only. `--check` exits non-zero on any diff. Output passes the
  frontend's strict `tsc` and `eslint` clean.
- **Variance:** TypeScript interfaces, not Zod — the frontend ships no zod
  dependency (D-046; adding one is a frontend-engineer call).

### `check_api_drift.py` · `QG-API-01` · `api-contract` CI job

- **Contract:** run both generators with `--check`; any diff fails the
  build in either direction (backend change without regeneration, or hand
  edit to a generated file). Negative-controlled in T-505.
- **Exit:** non-zero on any drift, naming the stale artifact.

---

## Pipeline scripts

These are the only scripts permitted to write `reports/**`.

### `generate_demo_dataset.sh` · `T-206` · `full`, `nightly`, `bootstrap`

- **Contract:** generate the full corpus from `datagen/config/` at the committed seed, emitting `train.parquet`,
  `calib.parquet`, `test.parquet`, `screening.parquet` and `reports/DATASET_PROFILE.md`. Print the SHA-256 of each
  artifact.
- **Refuses to run** if the config's provenance tags are incomplete — every generator parameter must be `cited`,
  `derived` or `assumed` with the required backing (`TEST-GEN-001`).
- **Refuses to emit** if the Escape Set is below its floor (`TEST-GEN-004`, and see `FOUNDATION_AUDIT § F-07`:
  the floor is a count, not merely non-emptiness). This is a **release blocker** and the script is where it bites.
- **Outputs:** the four artifacts, `reports/DATASET_PROFILE.md`, `reports/SPLIT_AUDIT.json`.
- **Exit:** non-zero on any provenance gap, any split overlap, or an under-floor Escape Set.

### `select_demo_parts.py` · `DEMO_SCENARIO § 2` · `full`, `nightly`, `bootstrap`

- **Contract:** resolve each demo part **by its stated predicate** into `reports/DEMO_PARTS_<tag>.json`. Predicates
  are declared in the script, printed on every run, and reproduced in the demo document — e.g. "an `S1` part with
  `dpat.verdict == FAIL` and `absolute.verdict == PASS` and attribution `PART`".
- **Why a predicate and not an ID:** a seed change re-selects automatically instead of breaking the demo an hour
  before the presentation, and the team can say truthfully that nothing was cherry-picked because the predicate is
  published and anyone can re-run it (`D-031`).
- **Exit:** non-zero if any predicate matches nothing. That is a real finding about the corpus and must be loud —
  it is also how `BL-004` surfaces if the `RT-005` case does not exist.
- **Consumed by:** the deck, `docs/DEMO_SCENARIO.md`, and the Playwright `demoPart` fixture. All three read the
  file; none hard-codes an ID.

### `make_figures.py` · `PRESENTATION_SPEC § 4` · `full`

- **Contract:** render the seven specified SVGs into `reports/figures/` from committed artifacts only, at a given
  tag. Every figure carries `SYNTHETIC DATA` in its own footer so the label survives being screenshotted out of the
  deck (INV-3).
- **Exit:** non-zero if any required artifact is missing. It never draws an empty axis with a caption — a plausible
  empty chart in a deck is worse than a missing one.

### `gen_coverage_report.py` · `QG-CORE-01` · `full`

- **Contract:** emit `reports/COVERAGE_<tag>.md` — line and branch coverage for `backend/core/**`, plus the count
  of public core functions with and without a registered test, joined from `tests/tests.json`.
- **Note:** the interesting column is the second one. High line coverage with a snapshot oracle is the failure mode
  `QG-CORE-01` exists to catch, so the report shows oracle categories per module rather than a single percentage.

---

## Release scripts

### `verify_reproducibility.sh` · `QG-REL-03` · `nightly`, pre-release

- **Contract:** three comparisons, in order.
  1. Regenerate the dataset from the seed; compare **SHA-256 byte-wise** against the committed artifacts.
  2. Retrain; compare model artifact hashes byte-wise.
  3. Re-score the *calibration* split; compare metrics exactly.
- **The PDF is compared semantically, not byte-wise.** Its generation timestamp is permitted metadata
  (`CLAUDE.md § 5`), so its bytes differ between identical runs. The comparison is over **extracted text with the
  timestamp line removed** (`FOUNDATION_AUDIT § F-10`). Hashing the PDF would fail on every run for a non-defect,
  and the predictable response — dropping the check — would remove the only test that the report content is stable.
- **Step 3 uses `calib`, never `test`.** The test split is scored exactly once per tag by `T-406` (`D-030`), and a
  reproducibility script that re-scores it would violate that rule while appearing to verify it.
- **Outputs:** `reports/REPRODUCIBILITY_<tag>.txt`, committed.
- **Exit:** non-zero on any drift. **A drift blocks the tag.** It means every published number belongs to a run
  nobody can reconstruct, and it also breaks INV-8 — so it is a real defect with an unseeded path behind it, not a
  tolerance to widen.

### `bootstrap.sh` · `QG-REL-05` · pre-release, and the demo condition

- **Contract:** from a **fresh clone with the network disabled**: install from the committed lockfiles, generate the
  dataset, train, start the backend on `:8000` and the frontend on `:5173`, and render one disposition PDF. Print
  each step's duration.
- **`--online` exists for first-time setup only** (it is what `HUMAN-004` runs to pre-cache the Playwright browser
  and fonts). `QG-REL-05` runs the default, offline path, because that is the demo condition (DMR-01) and it is
  verified rather than assumed.
- **Security note:** the backend binds to `127.0.0.1` and has **no authentication** (`FINAL_STATUS § L-12`). It is
  a single-user localhost application. Exposing that port on a network would expose every endpoint, including
  ingest, to anyone who can reach it — do not change the bind address for convenience.
- **Outputs:** `reports/OFFLINE_BOOTSTRAP_<tag>.txt` with the step timings and the rendered PDF path.
- **Exit:** non-zero if any step needs the network, or if the PDF is not produced. The PDF renderer's interceptor
  aborts and raises on any external URL (`D-028`), so a missing font fails loudly here rather than substituting
  silently at the presentation.

---

## Where each script runs

| Script | pre-commit | `fast` | `full` | `nightly` | pre-release |
|---|---|---|---|---|---|
| `check_secrets.sh` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `check_traceability.py` | — | ✅ | ✅ | ✅ | ✅ |
| `check_test_categories.py` | — | ✅ | ✅ | ✅ | ✅ |
| `check_test_deltas.sh` | ✅ advisory | — | ✅ `--strict` | ✅ | ✅ |
| `check_no_fabricated_numbers.sh` | — | — | ✅ | ✅ | ✅ |
| `validate_model_card.py` | — | — | ✅ | ✅ | ✅ |
| `generate_demo_dataset.sh` | — | — | ✅ 2 lots | ✅ full | ✅ full |
| `select_demo_parts.py` | — | — | ✅ | ✅ | ✅ |
| `make_figures.py` | — | — | ✅ | ✅ | ✅ |
| `gen_coverage_report.py` | — | — | ✅ | ✅ | ✅ |
| `verify_reproducibility.sh` | — | — | — | ✅ | ✅ |
| `bootstrap.sh` (offline) | — | — | — | — | ✅ |
| `generate_openapi.py` (`--check` via `api-contract` job) | — | — | — | — | — |
| `generate_ts_client.py` (`--check` via `api-contract` job) | — | — | — | — | — |
| `check_api_drift.py` (`api-contract` job) | — | — | — | — | — |

`fast` is the pre-push job and must stay under a couple of minutes, so it holds only the checks that need no
dataset. `full` runs on a 2-lot fixture. `nightly` runs everything on the full corpus.

**A red CI job is fixed, never disabled** (`.claude/agents/integration-release-engineer.md`). A disabled job is a
removed gate, and removing a gate to move faster removes the only thing that distinguishes this submission from a
convincing mockup.


