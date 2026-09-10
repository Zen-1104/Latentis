# UI_DESIGN_SYSTEM.md — Token Contract and Component Primitives

**Owner:** Product/UI Designer · Consumed by Frontend Engineer · Implements FR-506..FR-510
**Rule:** tokens in this file are the contract. A raw colour, spacing or font-size value in a component
is a **lint error** (`QG-FE-02`), not a style preference.

## 1. Visual thesis

**A calibrated instrument, documented in a lab notebook.**

Restrained, dense, high-contrast, monospaced numerals, generous whitespace around *decisions* and tight
whitespace around *data*. The aesthetic reference is Bloomberg-terminal information density crossed with
scientific-publication typography — not a consumer SaaS dashboard.

Three consequences, each a real constraint on implementation:

1. **Numbers are typographically privileged.** Tabular monospace, aligned decimal points, unit always
   adjacent. A number is the smallest unit of trust in this product; it gets the best type treatment.
2. **Colour carries severity only, never decoration.** Five semantic severities and nothing else. No
   brand gradient, no accent colour used for mood.
3. **The chrome recedes.** No card shadows competing with data, no full-width hero, no icon that is not
   a state indicator.

## 2. Colour tokens

Semantic names only. A component never references a hex value or a Tailwind palette number directly.

```
--surface-0    #0B0F14   page background (dark, low-emission — the primary theme)
--surface-1    #11171F   panel
--surface-2    #18202B   raised panel / drawer
--surface-3    #202A38   input, table header
--border-1     #263241   hairline
--border-2     #33445A   emphasised border

--text-1       #E8EEF6   primary
--text-2       #A9B7C8   secondary
--text-3       #6F8095   tertiary / captions
--text-num     #F2F7FD   numeric (highest contrast — numbers are the point)

--sev-nominal  #3FA46A   NOMINAL / SAFE / PASS
--sev-elevated #C9A227   ELEVATED / WATCH
--sev-anomaly  #D97A25   ANOMALOUS / EARLY_WARNING
--sev-severe   #C8442E   SEVERE / REJECT / FAIL
--sev-critical #8E2B7A   ABSOLUTE_FAIL   (distinct hue — a different KIND of failure, not "more red")

--evidence-weak #5B7C9E  data-quality / reduced_power / censored  (BLUE family, never red)
--guard-void    #B0432A  guarantee VOID banner
--synthetic     #7A5CC4  the SYNTHETIC badge — one dedicated colour, used nowhere else

--baseline      #7C8899  the naive-linear comparison line (deliberately muted)
--bound-fill    rgba(63,164,106,0.14)   conformal band fill
```

Two of these deserve their reasoning stated:

- **`--sev-critical` is violet, not a deeper red.** An absolute-limit failure is categorically
  different from a lot-relative anomaly: it is a hard fail that supersedes everything (FR-210).
  Encoding it as "more red" implies a continuum where there is a discontinuity.
- **`--evidence-weak` is blue.** Data-quality problems mean *"we are not confident"*, not *"this part is
  bad"* (`RISK_SCORING_SPEC § 2.4`). Rendering weak evidence in the severity ramp would systematically
  mislead an inspector into treating missing data as a defect signal.

A light theme exists with the same token names and ≥ 4.5:1 contrast maintained, because reports print
and a projector in a bright room is a real demo risk. Both themes are contrast-audited by
`TEST-A11Y-001`.

## 3. Typography

| Token | Value | Use |
|---|---|---|
| `--font-sans` | Inter, system-ui | UI text |
| `--font-mono` | JetBrains Mono, ui-monospace | **all numerals**, formulas, IDs, hashes |
| `--fs-display` | 28px / 34px | Verdict card headline |
| `--fs-h1` | 20px / 28px | Surface title |
| `--fs-h2` | 16px / 24px | Panel title |
| `--fs-body` | 14px / 20px | Body |
| `--fs-num` | 15px / 20px, `tnum` `lnum` | Table numerals |
| `--fs-num-lg` | 22px / 26px, `tnum` | Verdict numerals |
| `--fs-caption` | 12px / 16px | Units, provenance, captions |
| `--fs-formula` | 13px / 22px mono | The arithmetic panel |

`font-variant-numeric: tabular-nums lining-nums` is mandatory on every numeric cell. Without it,
columns of measurements visibly jitter as values update, which reads as instability in the *data*.

Fonts are **vendored locally** (`frontend/public/fonts/`), never fetched from a CDN — the demo is
offline-first (NFR-08, DMR-01), and a font that fails to load mid-demo is an avoidable humiliation.

## 4. Spacing, radius, elevation

4px base scale: `--sp-1: 4px` … `--sp-8: 32px`, `--sp-12: 48px`.
Radius: `--r-sm: 3px`, `--r-md: 5px`, `--r-lg: 8px`. Nothing more rounded — this is instrumentation.
Elevation: exactly two shadows, `--sh-drawer` and `--sh-popover`. Panels use borders, not shadows.

## 5. Component primitives

Every primitive lives in `frontend/src/design/` and is the **only** permitted way to render its
concept. A one-off `<div>` reimplementing one is a review rejection.

| Primitive | Contract |
|---|---|
| `<Metric>` | Takes a `TracedValue`. Renders value + unit at `display_precision` from the payload, and is **always** clickable to the ledger drawer. **Cannot be given a bare number** — the TS type forbids it, which is how "no display-only arithmetic" becomes compile-time |
| `<VerdictCard>` | Title, verdict enum, supporting metric, glyph + text label (never colour alone) |
| `<SeverityChip>` | The five severities; glyph + text + token colour |
| `<FormulaPanel>` | Renders a registry expression with operands substituted; each operand a clickable chip |
| `<LedgerDrawer>` | Recursive provenance walk; `Esc` to close; URL-addressable |
| `<CohortStrip>` | Strip plot of cohort values, DPAT limits as rules, part-under-test marked |
| `<DriftChart>` | The § 4 spec of `UX_SPEC` — observed, forecast, baseline, bound, limit, safety slope, band shading |
| `<GuardBanner>` | Non-dismissible; variants for VOID/DEGRADED, `reduced_power`, censored, unit findings |
| `<SyntheticBadge>` | Fixed, non-dismissible, present on every surface and in every export |
| `<DataTable>` | TanStack Table + virtualiser; numeric columns get `--fs-num`; sortable; keyboard-navigable |
| `<StateBlock>` | The four states of `UX_SPEC § 6.2` — loading / empty / error / degraded |
| `<ProvenanceHeader>` | Dataset hash, model versions, profile version, registry hash |

`<Metric>`'s type signature is the load-bearing design decision in this document:

```ts
type Metric = { traced: TracedValue };        // and nothing else — no `value: number` overload
```

A developer who wants to display a number they computed in the browser has no way to do it through the
design system. That is intentional, and it converts INV-1 from a rule people must remember into a
constraint the compiler enforces.

## 6. Charts

ECharts on canvas, with a locked theme file mapping ECharts options to the tokens above. Rules:

- Axes always labelled with **units**. An unlabelled axis is a review rejection.
- The naïve-linear baseline is drawn in `--baseline`, dashed, and **always present** on drift charts.
- Conformal bands use `--bound-fill` with a solid upper edge — a fill without a visible edge reads as
  decoration rather than a bound.
- No animation on data entry beyond 150 ms opacity. Motion on measurement data implies change that did
  not happen.
- Every chart has an accessible `<table>` fallback rendering the same values, which serves screen
  readers **and** gives Playwright something exact to assert against (`RT-012`).

## 7. Stitch integration rule (from `CLAUDE.md § 7`)

Stitch-generated UI is a **starting point, not a deliverable**. Before any generated screen counts as
`Implemented` it must:

1. consume real backend endpoints — no fixtures, no inline arrays;
2. replace every raw colour/spacing/font value with tokens from this file;
3. route every displayed number through `<Metric>` with a real `TracedValue`;
4. implement all four `<StateBlock>` states;
5. pass `TEST-A11Y-001` (contrast, focus order, non-colour-only encoding).

`QG-FE-01` is a checklist gate on exactly those five items. Generated markup that still contains a
literal number where a `TracedValue` belongs is the single most likely route to an INV-1 violation in
this project, which is why the gate is explicit rather than assumed.

## 8. Iconography and glyphs

A small fixed set, text-labelled in every use: `✓` pass, `✗` fail, `▲` rising trend, `▼` falling,
`◆` absolute fail, `!` guard warning, `≈` weak evidence, `⌕` investigate, `↻` retest. Lucide icons for
navigation affordances only. No icon ever carries meaning alone (FR-507).

## 9. Density modes

Two: **Comfortable** (default, 40px table rows) and **Compact** (28px, for 500-part lots). Both audited
for the same contrast and hit-target minimums. Persisted in local storage — a presentation-only
preference, therefore explicitly *not* part of any payload or computation.
