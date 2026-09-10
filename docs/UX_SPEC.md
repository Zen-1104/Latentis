# UX_SPEC.md — Surfaces, Journeys and Interaction Contract

**Owner:** Product/UI Designer + Frontend Engineer · Implements FR-501..FR-510, J1..J5, XR-03..XR-06

## 1. Design stance

This is a **QA instrument**, not a dashboard. The difference is concrete: a dashboard optimises for
"how are we doing?"; an instrument optimises for "what do I do with *this* part, and can I defend it?"

Four rules follow, and they drive every screen decision below:

1. **The primary object is a part, not a chart.** Aggregate views exist to route the user to a part.
2. **Every number is clickable and reveals its arithmetic.** No exceptions, no display-only maths
   (`ARCHITECTURE § 1`, `EXPLAINABILITY_SPEC § 3`).
3. **Disagreement is shown, never resolved for the user.** PAT vs. absolute, Module A vs. Module B,
   Isolation Forest vs. the ensemble — the divergence *is* the information (D-I-02).
4. **Uncertainty is a first-class visual element.** Bounds, cohort size warnings, `guarantee_status`,
   and censoring all have dedicated affordances. Hiding them to keep screens clean is a defect.

Anti-goal, stated so it cannot creep in: no gauge dials, no "AI confidence" rings, no animated
particle backgrounds, no dark-mode-only neon aesthetic. The visual reference is a calibrated
instrument panel and a lab notebook, not a crypto trading terminal.

## 2. The eight surfaces

| # | Surface | Route | Primary job | Priority |
|---|---|---|---|---|
| S1 | **Mission Control** | `/` | Fleet state: lots, flag counts, PDA status, data-quality, model/dataset identity | P0 |
| S2 | **Lot Explorer** | `/lots/:id` | Lot distribution with DPAT limits drawn on it; the part that sits outside them | P0 |
| S3 | **Component Investigation** | `/components/:id` | **The flagship.** Everything about one part, four explanation layers | P0 |
| S4 | **Drift Studio** | `/components/:id/drift` | Trajectory, forecast, conformal band, safety slope, baseline comparison | P0 |
| S5 | **Screening Profile** | `/profiles/:id` | Limits, `k`, `α`, `margin_fraction`, PDA — the config, editable and versioned | P1 |
| S6 | **Model Info** | `/models` | Cards, measured coverage, ablation table, fitted shape curves | P1 |
| S7 | **Ingest & Data Quality** | `/ingest` | Upload, validation findings itemised by row, manifest and hashes | P1 |
| S8 | **Disposition & Report** | `/components/:id/dispose` | CONCUR / OVERRIDE+reason / DEFER, then export | P0 |

S3 is the surface the demo lives on. If time is short, S3 and S4 are finished to a high standard and
S5–S7 stay functional-but-plain; a beautiful S1 with a thin S3 would be the wrong trade, because S3 is
where the explainability criterion is actually met.

## 3. S3 — Component Investigation, in detail

Layout, top to bottom, mapping directly onto the four explanation layers (`EXPLAINABILITY_SPEC § 2`):

```
┌─ Identity bar ──────────────────────────────────────────────────────────────┐
│ C-L2026-041-0137 · CMOS_LOGIC · Lot L-2026-041 · Board B-3 Socket S-14      │
│ Zone Z-2 · Tester T-01 · [SYNTHETIC DATA] · dataset 9f2c… · anomaly 1.0.0   │
├─ VERDICT STRIP  (L1) ───────────────────────────────────────────────────────┤
│  ┌───────────────────────┐ ┌───────────────────────┐ ┌────────────────────┐ │
│  │ DYNAMIC PAT           │ │ ABSOLUTE LIMIT        │ │ DRIFT BAND         │ │
│  │ ✗ FAIL                │ │ ✓ PASS  (9.6 % marg.) │ │ WATCH              │ │
│  │ 17.4 robust σ         │ │ 45.2 / 50.0 µA        │ │ ratio 0.67         │ │
│  └───────────────────────┘ └───────────────────────┘ └────────────────────┘ │
│  Recommendation: INVESTIGATE · Attribution: PART · Guarantee: VALID          │
├─ THE ARITHMETIC  (L2)  — always expanded on first load ─────────────────────┤
│  median 10.4 + 6 × (2.7 / 1.35) = 22.4 µA   ← DPAT upper limit              │
│  (45.2 − 10.4) / 2.0 = 17.4 σ               ← robust distance               │
│  every operand is a chip; click → ledger drawer                              │
├─ PARAMETER TABLE — 6 rows × read-points, sparkline + both verdicts per row ──┤
├─ COHORT VIEW — strip plot of 187 siblings, DPAT limits, this part marked ────┤
├─ ATTRIBUTION  (L3) — member firing table, D² contributions, socket/zone bars ┤
├─ COUNTERFACTUALS  (L4) — "flags at any k below 17.4"; α and limit sliders ───┤
└─ DISPOSITION — CONCUR / OVERRIDE (reason required) / DEFER ──────────────────┘
```

Decisions in that layout worth defending:

- **Three verdict cards, never one.** Two of them disagreeing is the entire problem statement rendered
  as UI. A merged verdict would destroy the demo's central moment.
- **The arithmetic panel is expanded by default**, not behind a disclosure triangle. Judges must not
  have to discover it. It is the answer to the explainability criterion, so it is above the fold.
- **The cohort strip plot beats a histogram** at `n = 187`: individual points are visible, the part
  under test can be marked, and the DPAT limits draw as vertical rules. Binning would hide the very
  point we are making.
- **`INSUFFICIENT_DATA` and guard states render as content**, not as an error toast. A part with a
  missing 24 h read shows a panel explaining which read-point is missing and why no forecast is
  offered — never a spinner that never resolves, never an imputed value.

## 4. S4 — Drift Studio, in detail

One chart, densely and carefully specified, because this is where the forecast is either credible or
not:

- **X:** elapsed hours 0 → 168 (linear; a log axis would flatter the sub-linear shape and is rejected).
- **Observed:** solid markers at 0 h and 24 h. These are the *only* observed points; the 96 h/168 h
  truth is **not** drawn (it is withheld — `DATASET_SPEC § 1`). In evaluation mode, and only there,
  truth may be overlaid with an explicit `EVALUATION MODE` badge.
- **Point forecast:** solid line 24 h → 168 h using the fitted `Φ_g`.
- **Naïve linear baseline:** dashed grey line to `Φ(168) = 7`. Always drawn. This is the single most
  persuasive element in the product — the visible gap between the two lines *is* the contribution, and
  labelling it costs nothing.
- **Conformal band:** shaded one-sided region to `Û168`, annotated `90 % upper bound (measured
  coverage 91.2 %)` pulled from the payload.
- **Absolute limit:** solid red horizontal rule at 50 µA.
- **Safety slope:** dotted line from `v0` at gradient `safety_slope`, labelled with its derivation
  `(50.0 − 12.1) × (1 − 0.20) / 168`. An inspector can read the criterion off the chart.
- **Band shading** on the right edge: SAFE / WATCH / EARLY_WARNING / REJECT zones.

Controls: the **Mission Risk Posture** dial (`α`), the `margin_fraction` input, and a horizon selector
(168 h screening vs. Arrhenius-converted mission hours). Every control **recomputes server-side** — the
frontend never re-derives a bound. Changing `α` and watching the band widen and the verdict flip is the
honest way to show the FP/FN trade-off instead of asserting it.

## 5. S1 — Mission Control

Not a KPI wall. Three regions:

1. **Provenance header** — dataset hash, row count, `SYNTHETIC` badge, model versions, profile
   version, formula-registry hash. It is the first thing on screen because *"is this connected to real
   computation?"* is the first thing a judge wonders.
2. **Lot table** (virtualised): lot, type, `n`, flagged count, `pda_pct` vs. limit with a verdict chip,
   `EARLY_WARNING` count as its own column, data-quality score, and a `reduced_power` badge for small
   lots. Sortable by `EARLY_WARNING` count — the column that exists only because we forecast.
3. **Escape spotlight** — up to five parts whose PAT verdict is FAIL while the absolute verdict is
   PASS, each a one-line summary and a deep link into S3. This is the worklist the product exists to
   produce, so it is on the landing screen rather than three clicks away.

## 6. Cross-cutting interaction contracts

### 6.1 The ledger drawer (FR-503)
Clicking any number opens a right-hand drawer showing: the formula expression, each operand with its
own value and unit and its own drill-down, the parameters in force with their profile provenance, the
`formula_id`, and the source reference (e.g. `D-CD-02`). Depth is unlimited; the drawer walks the DAG
of §3.1 in `PROVENANCE_SPEC`. `Esc` closes; the URL carries the open `formula_id` so a drawer state is
shareable — a small thing that matters when a judge asks *"can you show me that again?"*

### 6.2 Loading, empty, error and degraded (FR-505)
Four distinct states, all designed, none of them a bare spinner:
- **Loading:** skeleton matching the final layout's shape.
- **Empty:** what to do next, with the action inline (e.g. "no dataset ingested — ingest one").
- **Error:** the structured error `code`, `message`, `request_id` and the itemised `details` rows,
  copyable. Never "Something went wrong".
- **Degraded:** the specific model that failed to load, named, with the dependent panels disabled and
  labelled — not blank.

### 6.3 Warnings that cannot be dismissed
`reduced_power` (small cohort), `guarantee_status: VOID|DEGRADED`, `mondrian_level > 0`, `censored`,
`amplitude_clipped`, unit-validation findings, and the `SYNTHETIC` badge are **persistent**. There is
no close button. A dismissible warning is a warning that will be absent from the screenshot in the
report.

### 6.4 Keyboard and accessibility (FR-507)
Full keyboard reachability; `j`/`k` to move down/up the worklist, `Enter` to open a part, `d` to open
the ledger drawer, `?` for the shortcut sheet. WCAG 2.1 AA: 4.5:1 text contrast, visible focus rings,
`aria-live` on verdict changes, and — load-bearing for this domain — **verdicts are never encoded by
colour alone**; every band and verdict carries a glyph and a text label, because red/green is exactly
the pair most affected by common colour-vision deficiency.

### 6.5 Performance (FR-504, NFR-02)
500 parts × 6 parameters in a virtualised table at 60 fps; investigation payload rendered in < 300 ms
after response; charts on canvas via ECharts. Targets, measured in `reports/PERFORMANCE.md` by
Playwright traces — not asserted here.

## 7. What the UI is forbidden to do

| Forbidden | Reason |
|---|---|
| Compute a decision value in the browser | `ARCHITECTURE § 1`; lint-enforced (`QG-FE-03`) |
| Show a number without a reachable formula | INV-1 / XR-02 |
| Present `risk_index` as a percentage or probability | `RISK_SCORING_SPEC § 4` |
| Hide the absolute-limit verdict when PAT fails | The juxtaposition is the product |
| Draw 96 h/168 h truth outside evaluation mode | INV-4 — and it would be a leak in a screenshot |
| Ship a mock/fixture data path in the production build | JR-04; a demo that can silently run on fixtures is a demo nobody can trust |
| Round differently from the API's `display_precision` | `RT-012` |
| Say "may be defective" | Banned hedge vocabulary (`EXPLAINABILITY_SPEC § 6`) |

The mock-path ban is worth emphasising: `frontend/src` contains **no** fixture directory reachable at
runtime. Fixtures live in `frontend/tests/fixtures/` and are importable only from test files, asserted
by an import-graph check. The most common way a hackathon demo becomes dishonest is a `USE_MOCK` flag
that someone forgets to turn off.

## 8. Journey coverage

| Journey | Surfaces | Acceptance |
|---|---|---|
| J1 — Inspector triages a lot | S1 → S2 → S3 → S8 | Reaches a defensible disposition with the arithmetic visible, in under 2 minutes |
| J2 — Reliability engineer audits the method | S6 → S3 ledger → S4 | Can name the estimator, see measured coverage, and dispute the fitted shape curve |
| J3 — Test engineer investigates a socket | S1 → S2 → S3 attribution | Reaches `RETEST_DIFFERENT_SOCKET` on an `S4-decoy-sensor` part, i.e. the system protects a good part |
| J4 — Manager dispositions a lot | S1 → S2 → S8 | Sees both PDA figures (with and without `EARLY_WARNING`) and exports the report |
| J5 — Cold start | S7 → S1 | Clean machine to first flagged part in under 5 minutes, offline (DMR-01) |

Each journey has a Playwright spec (`tests/PLAYWRIGHT_STRATEGY.md`) that asserts the *numbers on
screen* against the API payload, not merely that elements rendered. A test that only checks for the
presence of a heading would pass on a fabricated UI, which makes it worse than no test.
