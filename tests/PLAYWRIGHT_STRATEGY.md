# PLAYWRIGHT_STRATEGY.md — Browser Verification and PDF Rendering

**Owner:** QA & Playwright Engineer · Implements TR-07, TR-08 · Policy parent: `tests/TEST_STRATEGY.md`

## 1. Two jobs, deliberately separated

| Job | Location | Ships in production? |
|---|---|---|
| UI verification | `frontend/tests/e2e/**` | No |
| Report rendering (HTML → PDF) | `backend/reporting/render.py` | **Yes** |

Same browser binary, separate lifecycles. They are kept apart because a rendering regression should not
turn the UI suite red, and because one of them is a *test harness* while the other is a *product
dependency* — conflating them would put test code on the release path.

## 2. The oracle rule (binding)

> An assertion on a decision-bearing number compares the **rendered text** against the value fetched from
> the **API payload in the same test**, formatted with the **imported** shared formatter — never against a
> literal in the spec file, and never against a number the test computed itself.

Three failure modes this closes at once: a literal freezes a fabricated value into the suite (INV-1 in the
least visible place); a test-local recomputation lets a rounding bug agree with itself; and a payload
fetched in a different test can drift from the one rendered.

```ts
const inv = await api.components.investigation(partId);        // generated client
const expected = fmtMetric(inv.data.worst.anomaly.dpat.z);      // imported from src/format
await expect(page.getByTestId('s3-verdict-dpat-z')).toHaveText(expected);
```

## 3. Selector contract

`data-testid` attributes are **part of the component contract**, owned by the Frontend Engineer and listed
per surface in `docs/UX_SPEC.md`. Renaming one is a breaking change and goes through a handoff note
(INV-7). Naming: `<surface>-<block>-<field>` — `s3-verdict-dpat-z`, `s3-arith-iqr`, `s4-chart-bound`.

Selector priority:

1. `getByRole` / `getByLabel` — accessibility work doubles as selector work, so `TEST-A11Y-001` and the
   E2E suite reinforce each other rather than competing for effort.
2. `getByTestId` for numeric readouts, where visible text is ambiguous by design (three cards can all
   read `PASS`).
3. **Never** a CSS class selector. Classes follow the token layer and change for cosmetic reasons; a suite
   pinned to them fails on a colour edit and teaches the team to distrust it.

## 4. Fixtures and the test dataset

The E2E dataset is `seed=20260930`, 6 lots, generated in CI by `scripts/generate_demo_dataset.sh`. It is
**never committed as a binary** — a committed dataset drifts from the generator and then nobody knows which
is authoritative.

| Fixture | Provides | Why it exists |
|---|---|---|
| `api` | A typed client built from the **generated** OpenAPI client — the same module the app imports | A contract break fails the E2E suite too, instead of only the unit contract test |
| `demoPart` | Component IDs resolved from `reports/DEMO_PARTS_<tag>.json` **by predicate** | If parts were hard-coded, a seed change would break the suite and the cheapest repair would be pinning a literal — the exact thing § 2 forbids |
| `freshDb` | A DuckDB file restored before each state-mutating spec | Lets disposition and profile specs run without ordering assumptions |

## 5. The five journeys

| ID | Journey | Surfaces | What a silent regression here would cost |
|---|---|---|---|
| **J1** | Escape investigation | S1 → S3 | The flagship claim. A part inside absolute limits, failed by DPAT, with its arithmetic |
| **J2** | Forecast and posture dial | S4 | The `α` control recomputing **server-side**; the naïve baseline still drawn |
| **J3** | The protected part | S3 attribution | `SOCKET` verdict, `RETEST_DIFFERENT_SOCKET`, `risk_index` going *down* |
| **J4** | Ingest a broken file | S7 | Row-itemised findings with an `action` on each; no `5xx` |
| **J5** | Disposition and export | S8 → PDF | Stored snapshot equals what was shown; banner on every page |

J1 and J3 together are the demo's argument (`docs/DEMO_SCENARIO.md` Acts II and IV). J3 is the one most
suites in this space do not have, so it gets the same weight as J1 rather than being treated as an edge case.

## 6. Charts: assert the table, never the pixels

Every chart renders an accessible `<table>` fallback (`UI_DESIGN_SYSTEM § 6`). Playwright asserts against
that table. Rationale: an ECharts canvas is opaque to the DOM, so the only pixel-level check available is a
screenshot diff — which **fails on font hinting and passes on a wrong number**. That is precisely backwards
for this project, and it is why the accessible fallback is a testability requirement as much as an
accessibility one.

## 7. Visual regression policy

- **Allowed:** full-page structure snapshots with every numeric locator passed to `mask:`.
- **Banned:** any snapshot as the *sole* assertion for a numeric value (`TEST_STRATEGY § 1`).
- `--update-snapshots` in CI is prohibited. A snapshot change is reviewed by a human looking at the diff,
  because an auto-updated baseline records whatever the bug produced.

## 8. The four states, provoked at the network layer

`E2E-STATE-001..004` drive each surface's designed states with `page.route` interception — **not** with a
build flag, because a build flag reachable at runtime is exactly the mock path that `FR-510` forbids.

| State | How it is provoked |
|---|---|
| loading | Fulfil after a delay; assert skeleton, then assert the resolved value |
| empty | Valid response with an empty collection; assert the designed empty copy, not a blank region |
| error | Structured error body from the closed enum; assert the `remediation` string is displayed |
| degraded | `/health` with one model artifact absent; assert the dependent panels **disable themselves and name the missing artifact** |

Standing constraint: interception provokes **states**, never supplies **numbers**. A spec that intercepts a
payload and then asserts the intercepted value is testing its own fixture, which is worse than no test
because it reads as coverage.

## 9. Determinism

- No arbitrary waits. Auto-waiting and `expect.poll` only; a `waitForTimeout` in a spec is a review
  rejection.
- Viewport pinned to **1920×1080** (the projector), with a second 1440×900 pass for layout-sensitive specs.
- `timezoneId: 'UTC'`, `locale: 'en-IN'`, `colorScheme: 'light'`, and `reducedMotion: 'reduce'` pinned in
  the project config so number, date and animation rendering are stable across machines.
- State-mutating specs (ingest, disposition, profile) run with `workers: 1`; read-only specs run parallel.
- `trace: 'on-first-retry'`, `video: 'retain-on-failure'`, both uploaded as CI artifacts.
- `retries: 1` in CI, `0` locally. A spec that passes only on retry is filed as a **P1 defect against the
  application** (`TEST_STRATEGY § 6`), not left green — in a numeric pipeline flakiness usually means an
  unseeded path, which would also break INV-8.

## 10. Chromium only, stated as a limitation

Firefox and WebKit are out of scope: DMR-01 is a single-machine offline demo on a browser we control. The
honest consequence — **we do not know whether the application works in Safari** — is recorded in
`FINAL_STATUS.md § Known Limitations` rather than left for a judge to discover.

## 11. PDF rendering (production path)

Jinja2 → self-contained HTML → Chromium `page.pdf()`. Constraints, each with a reason:

| Constraint | Reason |
|---|---|
| Fonts vendored locally; images inlined as base64 | NFR-08: the renderer must work with the network off |
| A request interceptor **aborts and raises** on any external URL | Turns "it happened to be cached" into a hard failure |
| `@media print` stylesheet; explicit page size and margins | Otherwise pagination differs between machines |
| Footer template carries the synthetic banner and `page/total` | `TEST-REP-002` asserts it on page 1 and in every footer |
| Provenance appendix generated from the payload's `formula_id`s | `TEST-REP-001`: a reviewer holding only the PDF can recompute on paper |

## 12. RT-012 — the three-way agreement

For a sampled set of parts: fetch the API payload, read the UI text, extract the PDF text, and assert all
three are equal **after formatting with the imported shared formatter**. Importing rather than
reimplementing the formatter is the load-bearing detail; a reimplementation would let a rounding bug agree
with itself in all three places.

## 13. Anti-patterns

| Anti-pattern | Why it is banned | Instead |
|---|---|---|
| `toHaveText('17.4')` | Freezes a fabricated value; keeps passing after the pipeline breaks | Compare to the payload (§ 2) |
| `toBeVisible()` as the only assertion | Passes on an empty element | Assert the text content |
| `waitForTimeout` | Flake that gets "fixed" by increasing the number | Auto-wait / `expect.poll` |
| Class-based selectors | Break on cosmetic token edits | Role, label, or `data-testid` |
| Chart canvas snapshots | Fail on fonts, pass on wrong numbers | The accessible table fallback |
| Intercept then assert the intercepted number | Tests the fixture | Intercept for states only (§ 8) |
| `test.skip` with no reference | Silent coverage loss | A skip requires a `TASKS.md` row and an owner |

## 14. CI placement

| Job | Playwright content |
|---|---|
| `fast` (pre-commit) | none — E2E is too slow to gate a commit |
| `full` (per push) | **J1 and J4 only**, on a 2-lot dataset — a smoke pass |
| `nightly` / pre-release | All five journeys, `TEST-A11Y-001`, `E2E-PERF-*`, `RT-012`, PDF rendering |

Keeping the full suite off the per-push job is a deliberate trade for iteration speed. The compensating
control is `QG-REL-02`: **a tag cannot be cut unless the nightly suite has passed on that exact commit**, so
the trade costs latency in feedback, not coverage at release.


