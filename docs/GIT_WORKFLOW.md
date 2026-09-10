# GIT_WORKFLOW.md — Branching, Commits and Safety Rules

**Owner:** Integration & Release Engineer · Implements `CLAUDE.md § 6` · Binding on every agent

## 1. Why this file is strict

Ten agents write to one repository. Most repository damage in that setting is not malice — it is a
well-meaning agent running `git checkout .` to "clean up" and deleting another agent's uncommitted work.
So the rules below are phrased as **prohibitions on specific commands**, not as principles, because a
principle does not stop a command.

## 2. Branch model

```
main            always green: tests pass, app runs, no known P0
  └─ phase/<n>-<name>          integration branch per phase (e.g. phase/2-core-numerics)
       └─ feat/<agent>/<slug>  one agent, one concern
       └─ fix/<agent>/<slug>
       └─ docs/<agent>/<slug>
       └─ test/<agent>/<slug>
```

- Agents work on `feat|fix|docs|test/<agent>/<slug>`, **never** directly on `main` or on another agent's
  branch.
- Merge direction is always upward: agent branch → phase branch → `main`.
- Phase branches are merged to `main` by the Integration & Release Engineer only, after the phase's
  quality gates pass (`tests/QUALITY_GATES.md`).
- Checkpoint tag after every phase: `v0.<phase>.0`.

## 3. Commits

Conventional Commits, imperative mood, one concern per commit:

```
feat(core/lotstats): leave-one-out robust cohort statistics with zero-IQR guard

Implements FR-201..FR-203. Cohort excludes the part under test (LK-5).
IQR=0 falls back to MAD; IQR=0 and MAD=0 returns NO_VARIATION.

Tests: TEST-STAT-001 (hand-computed quartiles), TEST-STAT-002 (LOO), RT-009 rows 3-4.
Refs: ANOMALY_SPEC.md § 4.1, § 9
```

Types: `feat` `fix` `docs` `test` `refactor` `perf` `chore` `data` `model`.
Scopes follow the module tree: `core/lotstats`, `core/drift`, `api/routers`, `datagen`, `fe/features`,
`reports`, `agents`.

**Required in the body when applicable:** the FR/NFR IDs implemented, the test IDs added, and the spec
section. A commit that implements a requirement without naming it makes the traceability matrix in
`tests/TEST_MATRIX.md` unmaintainable by hand.

## 4. Prohibited commands — no exceptions without explicit human approval

| Command | Why |
|---|---|
| `git push --force` / `--force-with-lease` on a shared branch | Rewrites history other agents have based work on |
| `git reset --hard` on anything not authored by you in this session | Destroys uncommitted work you cannot see |
| `git checkout .` / `git restore .` | Same, and it is the most common accidental data loss |
| `git clean -fd` | Deletes untracked files — including another agent's in-progress work |
| `git rebase` on a pushed shared branch | History rewrite |
| `git branch -D` on a branch you did not create | — |
| `git filter-branch` / `filter-repo` | Only via `HUMAN_ACTIONS.md` |
| `git commit --amend` on a pushed commit | — |
| `git add -A` from the repository root | Sweeps up other agents' files; stage explicit paths |

`git add -A` is on this list for a reason specific to multi-agent work: it silently commits files owned
by other agents, violating INV-7, and the resulting commit is hard to unpick because the diff mixes
concerns.

## 5. Required practices

1. **Stage explicit paths.** `git add backend/core/lotstats/ tests/unit/test_lotstats.py`.
2. **Verify before commit:** `git status --short` and `git diff --cached --stat`. If a file you do not own
   appears, stop and write a handoff note (`agents/README.md`).
3. **Pull with rebase on your own branch** (`git pull --rebase`), merge upward with `--no-ff` so the phase
   history shows what came from where.
4. **Never commit** generated datasets (`data/generated/**`), model binaries (`models/registry/**/*.joblib`),
   `node_modules`, `__pycache__`, `.venv`, or PDFs — except the small committed artifacts named in
   `.gitignore`'s allow-list comments. Manifests, cards and `reports/*.md` **are** committed; the binaries
   they describe are not.
5. **Lockfiles are committed** (`uv.lock`, `package-lock.json`). A lockfile change is its own commit with
   the reason in the body.
6. **Secrets: never** (INV-10). `scripts/check_secrets.sh` runs in the pre-commit hook and in CI.

## 6. Ownership and cross-boundary edits (INV-7)

The ownership table in `agents/README.md` is authoritative. To change a file you do not own:

1. Do not edit it.
2. Append a handoff note to `INTEGRATION_STATUS.md § Handoffs` naming the file, the change, the reason and
   the requesting agent.
3. Continue with unblocked work.
4. The owning agent (or the Lead Orchestrator) makes the change and references the handoff note in the
   commit body.

The exceptions — files any agent may append to, never rewrite — are `TASKS.md`, `DECISIONS.md`,
`INTEGRATION_STATUS.md`, `HUMAN_ACTIONS.md` and `CHANGELOG.md`. "Append" means adding a new entry;
rewriting or deleting another agent's entry in those files is an INV-7 violation like any other.

## 7. Pre-commit hooks

```
ruff check --fix · black · mypy (backend) · eslint · tsc --noEmit (frontend)
pytest -m "fast"          (unit tests only; the full suite runs in CI)
scripts/check_secrets.sh
scripts/check_no_fabricated_numbers.sh     # RT-008 static scan
```

Hooks are **never** bypassed. `--no-verify` is prohibited; if a hook is wrong, fix the hook in its own
commit. A bypassed hook is how a hard-coded metric reaches `main`, which is the exact failure INV-1
exists to prevent.

## 8. Release procedure

Performed only by the Integration & Release Engineer:

```
1  All quality gates green (tests/QUALITY_GATES.md)
2  scripts/verify_reproducibility.sh passes           # INV-8
3  Regenerate dataset, retrain, re-register models; all manifests show dirty_worktree: false
4  Score the test split ONCE; write reports/METRICS_<tag>.json, ABLATION_<tag>.md, COVERAGE_<tag>.md
5  Run the red-team suite; write reports/RED_TEAM_<tag>.md
6  Update CHANGELOG.md, FINAL_STATUS.md, INTEGRATION_STATUS.md
7  Merge phase branch to main with --no-ff
8  Tag v0.<phase>.0, annotated, message = the CHANGELOG section
9  Verify: fresh clone → scripts/bootstrap.sh → demo path works offline
```

Step 4's "once" is a scientific commitment, not a convenience: the test split is scored one time per
release tag, by one agent, and the number that comes out is the number reported (AG-5). Re-scoring after
a tweak and reporting the better figure is the definition of test-set overfitting, and it is the failure
mode most likely to make our headline metric a lie.

Step 9 is non-negotiable because a release that only works in the developer's tree is not a release, and
the demo runs from a clean checkout on an unfamiliar machine (DMR-01).

## 9. If something goes wrong

| Situation | Correct action |
|---|---|
| Committed a secret | Stop. `HUMAN_ACTIONS.md` entry. Rotate the credential first, then history surgery with human approval |
| Committed to the wrong branch | `git cherry-pick` onto the right branch; leave the wrong-branch commit for the owner to revert |
| Broke `main` | Revert commit (never a force push), then fix forward on a branch |
| Merge conflict in a file you do not own | Do not resolve it. Handoff note; the owner resolves |
| Uncommitted work from another agent in your worktree | Do not clean it. Stash nothing, delete nothing, report it in `INTEGRATION_STATUS.md` |
| A test fails | Fix the implementation (INV-6). Changing a test requires a `DECISIONS.md` entry and sign-off |

The last row is the one that matters most and is the easiest to violate under time pressure. Weakening
an assertion is the fastest possible way to a green build and the fastest possible way to a product that
does not do what its documentation says.
