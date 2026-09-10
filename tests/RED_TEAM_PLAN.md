# RED_TEAM_PLAN.md — Twelve Attacks on Our Own Claims

**Owner:** Red-Team Auditor · Implements TR-10, XR-01..XR-06 · Output: `reports/RED_TEAM_<tag>.md`

## 0. How this document is meant to be used

Each suite below names **a specific claim this project makes** and then tries to falsify it. The suites are
written from the outside: they consume the API, the built bundle, the emitted artifacts and the rendered PDF,
and they are allowed to know the specs but **not** to import internal helpers that the implementation also
uses. An audit that shares code with its subject is not an audit.

Two governance rules make this real rather than ceremonial:

1. **The Red-Team Auditor cannot be assigned implementation work** (`AGENT_TOOLING § 3`, rule 5). An agent
   auditing its own code is not auditing.
2. **A failing red-team suite is a P0 defect against the implementation.** It is recorded in
   `INTEGRATION_STATUS.md § Blocked`, and it cannot be resolved by amending the suite — that would need a
   `DECISIONS.md` entry and sign-off (INV-6), and the auditor is expected to refuse.

Every suite emits a verdict of `PASS`, `FAIL`, or `NOT_RUN` with the reason, and `reports/RED_TEAM_<tag>.md`
publishes all twelve. **`NOT_RUN` is reported, never omitted** — a missing row reads as a pass, which is the
single easiest way for an audit document to lie.

## 1. RT-001 — Every published number resolves to a committed artifact

**Claim under attack:** INV-1, at the level of documents rather than code — "any number in a slide or README
is traceable to a `Measured` artifact, or is absent" (`CLAUDE.md § 4`).

**Method.** Extract every numeric token from `README.md`, `FINAL_STATUS.md`, `presentation/**`,
`reports/*.md` and every spec's worked examples. For each token, attempt to resolve it to a key path inside
a committed `reports/METRICS_<tag>.json`, `ABLATION_<tag>.md`, `DATASET_PROFILE.md`, `SENSITIVITY.md` or
`PERFORMANCE.md`. Tokens are exempt only if they are (a) a configuration value present in a committed
profile, (b) a citation (a standard's clause number, a year, a page), or (c) explicitly inside a block marked
`<!-- illustrative: not a result -->`.

**Pass condition.** Zero unresolved tokens. Every exemption is one of the three declared kinds.

**Why the exemption mechanism is narrow on purpose.** The worked examples in `EXPLAINABILITY_SPEC` and
`DEMO_SCENARIO` contain numbers like `45.2 µA` and `17.4 σ` that were written *before* the pipeline existed.
They are illustrative, and they must be marked as such or replaced with measured values once the pipeline
runs. **This suite is expected to FAIL at Phase 0 and that is the correct behaviour** — it is the mechanism
that forces those placeholders to be reconciled before a tag, rather than shipping as if they were results.

## 2. RT-002 — No feature derived from a withheld observation

**Claim under attack:** INV-4. Module B sees 0 h and 24 h and nothing later.

**Method.** Three independent probes, because a name scan alone is defeated by a rename:

| Probe | What it does |
|---|---|
| Name scan | Any column or feature name containing `96`, `168`, `final`, `truth`, `label_value` in the model's fitted schema |
| Correlation probe | `|Spearman ρ| ≥ 0.95` between any model input and `value_168h` on the calibration split |
| Ablation probe | Delete `value_168h` from the on-disk artifact, re-run inference; the forecast must be **bit-identical**. If any number moves, something read it |

**Pass condition.** All three clean. The third probe is the one that would catch a leak the other two miss.

## 3. RT-003 — The browser computes no decision

**Claim under attack:** `UX_SPEC § 7` — every decision value is computed server-side; the client renders.

**Method.** Load S3 and S4 with a network trace. Change `α` from 0.10 to 0.02 and `margin_fraction` from
0.20 to 0.10. Then: (a) assert a request was issued for each change; (b) assert every changed on-screen
number appears verbatim in the *response body* of that request; (c) with the network blocked after load,
assert the controls **disable themselves** rather than producing a locally computed answer.

**Pass condition.** No displayed decision number is absent from a response payload. Test (c) is the sharp
one — a client-side fallback is exactly what a well-meaning implementer adds for "responsiveness", and it
would put unaudited arithmetic in front of a judge.

## 4. RT-004 — Verdicts are invariant to identity

**Claim under attack:** INV-2 — no verdict depends on `component_id`, row order, socket numbering, or any
identifier.

**Method.** Four permutations, each of which must leave every verdict, severity and `risk_index` unchanged
to `1e-12`:

1. Shuffle row order in the input file.
2. Replace every `component_id` with a fresh UUID via a bijection, keeping all values.
3. Renumber `socket_id` and `tester_id` through a bijection.
4. Reverse the lot ordering in the manifest.

Then one permutation that **must** change the answer: swap two parts' *values*. If that also leaves verdicts
unchanged, the pipeline is not reading the values it claims to — a negative control, without which the other
four could all pass on a stub.

**Pass condition.** Permutations 1–4 identical; the value swap changes the affected verdicts.

## 5. RT-005 — Rejection is driven by the bound, not the point estimate

**Claim under attack:** `FR-310` and `CONFORMAL_SPEC` — bands come from `Û168`, never from `V̂168`.

**Method.** Mutation testing, narrowly scoped. Patch the band assignment to read `V̂168` instead of `Û168`
and re-run the band suite. Then patch it to read `Û168` with the quantile forced to zero. Both mutants must
be **killed** — some test must fail.

**Pass condition.** Both mutants killed, and the suite names which test killed each. A surviving mutant means
the distinction we advertise as our strongest answer to "false negatives are catastrophic" is untested.

Second probe: search for any part in the corpus where `V̂168 < limit_high ≤ Û168`. At least one must exist,
and its band must be `REJECT`. If no such part exists in the dataset, the claim is unfalsifiable on this
corpus and the suite reports `NOT_RUN` with that reason rather than `PASS`.

## 6. RT-006 — Attribution survives a deliberate confound

**Claim under attack:** `FR-208` — PART / SOCKET / ZONE / TESTER attribution distinguishes a bad part from a
bad setup.

**Method.** Inject, into a copy of the dataset, four confounds one at a time:

| Injection | Required attribution |
|---|---|
| A fixed offset on one socket across many lots | `SOCKET` |
| A gradient across one thermal zone | `ZONE` |
| A scale error on one tester | `TESTER` |
| A single part shifted with a clean setup | `PART` |
| A socket offset **and** a genuinely bad part in that socket | `PART` (the part must not be excused) |

The fifth row is the one that matters. A system that credits setup evidence can be made to excuse a real
defect, and that failure mode would be invisible in the first four rows.

**Pass condition.** All five rows produce the required attribution, and row five's `risk_index` is **not**
reduced below its `INVESTIGATE` threshold by `credit_attribution`.

## 7. RT-007 — The re-derivation audit (the flagship suite)

**Claim under attack:** the one in `EXPLAINABILITY_SPEC § 1` — *every displayed number is recomputable from
its own payload alone.*

**Method.** For every part in a sampled set, save the `/components/{id}/investigation` payload to disk. Then,
in a **separate process with no access to `backend.core`**, walk every `TracedValue` in the file and:

1. Read its `expression` string and `operands`.
2. Bind the operands from the same payload — from `inputs` and `parameters` only.
3. Evaluate the expression with a restricted evaluator (arithmetic, `exp`, `log`, `sqrt`, comparison —
   no attribute access, no imports, no calls into project code).
4. Compare against the stated `value` at the value's own `display_precision`.
5. Re-derive the verdict from the re-derived quantities and the profile thresholds in the payload.

**Published metric.**

```
rederivation_rate = (# TracedValues reproduced) / (# TracedValues examined)
verdict_agreement = (# parts whose verdict re-derived correctly) / (# parts examined)
```

Both go into `reports/METRICS_<tag>.json`. **Target for both: 1.0.** This is the number quoted in the
judging conversation, so it is measured by an independent evaluator rather than asserted.

**Pass condition.** `rederivation_rate == 1.0` and `verdict_agreement == 1.0` on the sample.

**Why this makes fabrication structurally impossible rather than merely forbidden.** A hard-coded number has
no `formula_id`, no `operands` and no `inputs`. It cannot be re-derived, so it lowers a published metric the
moment it is added. The incentive points the right way without anyone policing it.

## 8. RT-008 — Static scan for fabricated values in source

**Claim under attack:** INV-1 at the level of code, complementing RT-001's document-level audit.

**Method.** AST scan (not regex — a regex cannot tell an array index from a threshold) over:

| Target | Rule |
|---|---|
| `frontend/src/**` excluding `_generated_draft/**` and the token layer | No numeric literal reaching a render path; no literal in a string template beside a unit symbol |
| `frontend/src/**` | No `USE_MOCK`, no `fixtures/`, no import from `_generated_draft` |
| `backend/core/**` | No numeric literal outside a named constant with a `source_ref`; the AEC-Q001 `1.35` and `1.4826` must appear **once each**, in the registry, with their citations |
| `backend/app/**` | No literal on a decision-bearing response field |
| Narrative templates | No digit outside a slot name (also `TEST-EXPL-001`) |

Permitted literals, exhaustively: `0`, `1`, `2` in arithmetic and indexing; array/tuple indices; loop bounds;
HTTP status codes; version strings; and any value inside `backend/core/constants.py`, where every entry
carries `source_ref` and a provenance tag.

**Pass condition.** Zero violations. The `constants.py` allow-list is itself audited: an entry tagged
`assumed` with no `DECISIONS.md` reference is a violation.

## 9. RT-009 — The degenerate-case table

**Claim under attack:** `ANOMALY_SPEC § 9` and `DRIFT_SPEC § 6` — *"breaks when a judge clicks something
unexpected"* is a scored failure mode, so the required behaviour for every pathological input is written down
in advance rather than discovered live.

Each row is a required behaviour. A `500` on any row is a failure of the row; so is a plausible-looking
number where a refusal is required.

| # | Input | Required behaviour |
|---|---|---|
| 1 | `v0` or `v24` missing | `INSUFFICIENT_DATA`; no forecast field populated; **no imputation** |
| 2 | Cohort `3 ≤ n < 20` | `reduced_power`, MAD estimator with `c(n)`, warning surfaced. `n < 3` ⇒ `INSUFFICIENT_COHORT`, defer to absolute limits |
| 3 | `IQR = 0` and `MAD = 0` (identical cohort) | `NO_VARIATION`; no division; no `inf` z-score; the part is judged on absolute limits only |
| 4 | Cohort of exactly 2, one an extreme outlier | `INSUFFICIENT_COHORT`. Masking is *reported*, never silently absorbed |
| 5 | Values at float extremes (`1e-30`, `1e30`) | Finite output or an explicit refusal. No `NaN`, no `inf`, anywhere in the payload |
| 6 | Censored reading (`<0.1`, `>1000`) | Retained as censored with its limit; never coerced to `0`, to the limit, or to a midpoint. Bound moves conservatively |
| 7 | `v24 == v0` exactly (zero amplitude) | Forecast equals `v0`; `slope_ratio = 0`; band `SAFE`; no division by the amplitude |
| 8 | Negative leakage current | Rejected at ingest with `VALIDATION_FAILED` and a `remediation` naming the physical constraint |
| 9 | Duplicate `(part, param, hours)` | Detected, reported with both row indices, and the ingest **refuses** rather than picking one |
| 10 | Unseen `component_type`, `tester_id`, or Mondrian group | Fallback ladder engages, `mondrian_level` reported, exchangeability guard raised to at least `WARN` |
| 11 | Lot with 1 part | `INSUFFICIENT_COHORT`; the lot page renders its empty state, not a crash |
| 12 | Non-monotonic timestamps | Accepted with a warning finding; ordering by nominal read-point, not by timestamp |
| 13 | 200-character Unicode `component_id` | Round-trips through API, UI and PDF without truncation or layout break |
| 14 | `margin_fraction = 0` or `1` | `0` ⇒ safety slope uses the full margin; `1` ⇒ `usable_margin = 0` and every drifting part is `REJECT`. Both are legal configurations and must not divide by zero |
| 15 | Profile with `k = 0` | Legal and degenerate: limits collapse to the median. Must be accepted and *reported as such*, not silently clamped |

**Pass condition.** Every row behaves as written. Rows 3, 5, 7 and 14 are the ones that would produce a
`NaN` on screen, which is the single most damaging thing that can happen during a live demo.

## 10. RT-010 — Risk weights cannot buy a verdict

**Claim under attack:** `RISK_SCORING_SPEC § 3` — the weights are presentation of evidence, not the decision.
If a weight could move a part across a band boundary, then tuning weights would tune the demo, and every
metric downstream would be negotiable.

**Method.** Sweep each of `w_A, w_B, w_M, w_Q, w_C` across its full admissible range on a grid, jointly where
the spec allows, and for every part in the corpus record `(anomaly_verdict, drift_band, recommendation)`.

**Pass condition.**

- `anomaly_verdict` and `drift_band` are **invariant** across the entire sweep.
- `risk_index` varies (otherwise the weights are decorative — a second negative control).
- `recommendation` may change only where the mapping table explicitly reads from `risk_index`, and every such
  transition must appear in `RISK_SCORING_SPEC § 4`.
- The `sum_check` adding-up property holds at every grid point to `1e-9`.

## 11. RT-011 — The exchangeability guard actually fires

**Claim under attack:** the honesty signal in `SIH_JUDGING_STRATEGY § 3.3` — *the system declares when its own
guarantee is void.* An unfired guard is a claim, not a feature.

**Method.** Six injections, one per declared signal, each into a copy of the calibration-time distribution:

| Injection | Required `guarantee_status` |
|---|---|
| Lot median shifted by 4 robust σ | `VOID` |
| A feature's PSI driven above 0.25 | at least `WARN` (`DEGRADED`) |
| KS test on `delta_24` at `p < 0.01` | at least `WARN` |
| Burn-in temperature outside the calibration range | `VOID` |
| A `tester_id` never seen in calibration | at least `WARN` |
| A Mondrian group never seen in calibration | `VOID` via `INSUFFICIENT_CALIBRATION` or the fallback ladder, with `mondrian_level` reported |

Plus two controls: an **unshifted** copy must yield `PASS` (a guard that always fires is useless), and a
`VOID` case must produce a **wider** bound than the same part under `PASS` — never narrower, never equal.

**Pass condition.** All six fire, the control passes, the bound widens, and the `VOID` banner appears in the
UI *and* in the exported PDF. The PDF half matters: a warning that vanishes on export is a warning that
vanishes exactly when the document outlives the conversation.

## 12. RT-012 — UI, API and PDF agree

**Claim under attack:** that the three surfaces a judge can inspect are views of one computation.

**Method.** For a sampled set of parts covering every stratum, collect three renderings of each
decision-bearing value: the API payload, the on-screen text, and the text extracted from the exported PDF.
Compare all three after formatting with the **imported** shared formatter
(`tests/PLAYWRIGHT_STRATEGY.md § 12`).

**Pass condition.** Three-way equality for every sampled value, including `risk_index`, both verdicts, the
forecast, the bound, the baseline, and the safety slope. Any disagreement is a P0 — it means at least one of
the three is lying, and we would not know which.

## 13. Severity, and what a failure blocks

| Suite | Fails ⇒ blocked | Reasoning |
|---|---|---|
| RT-001, RT-008 | **Release** | A fabricated number is the one defect that makes every other number worthless |
| RT-002 | **Release** | A leak invalidates every reported drift metric |
| RT-004 | **Release** | A verdict that depends on identity is not a measurement |
| RT-005, RT-011 | **Release** | These are the two claims we lead with; untested, they are marketing |
| RT-007 | **Release** | It is a published metric; a failing audit means the published figure is wrong |
| RT-009 | **Release** | Rows 3/5/7/14 put `NaN` in front of a judge |
| RT-012 | **Release** | Divergence between UI, API and PDF is unattributable |
| RT-003, RT-006, RT-010 | **Phase gate** | Serious, but each has a narrow blast radius and a documented interim workaround |

## 14. When a suite fails

1. Record it in `INTEGRATION_STATUS.md § Blocked` with the literal output — never a summary
   (`CLAUDE.md § 3`).
2. File the defect against the **implementation**. Amending the suite requires a `DECISIONS.md` entry, the
   Lead Orchestrator's sign-off, and the auditor's written objection if the auditor disagrees.
3. If the defect cannot be fixed before the tag, the *capability* is downgraded in `FINAL_STATUS.md` — from
   `Verified` to `Implemented`, with the failing suite named. The claim moves; the test does not.

That third step is the whole point of this document. A red-team plan whose only outcome is "we fixed it"
describes a project that never had a hard problem. This one is written so that the honest outcome —
**a claim withdrawn instead of a test weakened** — is a defined, available, and pre-authorised move.



