# PROVENANCE_SPEC.md — The Provenance Ledger

**Owner:** Backend Engineer + Data + ML Engineer · Implements XR-02, DR-05..DR-09, FR-604..FR-607
**Enforced by INV-1, INV-3, INV-8 · Audited by `RT-007`, `RT-008`**

## 1. What the ledger is, and what problem it solves

The Provenance Ledger is not a logging feature. It is the mechanism that makes *"this number is real"*
a checkable property of the system rather than a promise in a slide.

The problem it solves is specific and it is the one that sinks demos: at judging time, nobody can tell
the difference between a chart drawn from a live computation and a chart drawn from an array of
plausible constants. Both look identical. The ledger removes the ambiguity by making every
decision-bearing number carry its own derivation, all the way to the exported PDF, so an auditor can
recompute it without access to our source code.

Design consequence, stated as a claim we can defend: **a hard-coded number cannot pass through this
system.** It has no `formula_id`, no operands, and no dataset hash, so it fails `RT-007` at the
boundary. This is why INV-1 is enforceable rather than aspirational.

## 2. Four levels of provenance

| Level | Scope | Answers |
|---|---|---|
| **P1 — Value** | One number | *Which formula, which operands, which parameters, which units?* |
| **P2 — Model** | One artifact | *Which version, which training lots, which config hash, which code SHA?* |
| **P3 — Dataset** | One dataset | *Which generator, which seed, which config, which file hashes, synthetic or not?* |
| **P4 — Decision** | One disposition | *What exactly did the human see when they concurred or overrode?* |

Most systems implement P2 and P3 (MLflow-style lineage). P1 and P4 are the unusual ones, and they are
the two that a QA audit actually needs.

## 3. P1 — the `TracedValue`

The single carrier for every decision-bearing quantity (`ARCHITECTURE § 5`):

```python
class TracedValue(BaseModel):
    value: float
    unit: str                            # "uA" | "ns" | "sigma" | "ratio" | "hours" | "index"
    formula_id: str                      # key into the append-only formula registry
    inputs: dict[str, float | str]       # every operand, named
    parameters: dict[str, float | str]   # k, alpha, divisor, Ea, margin_fraction, profile_id ...
    model_version: str | None
    dataset_hash: str
    display_precision: int
```

Rules, each with a test:

1. **`unit` is never absent and never `""`.** A dimensionless quantity uses `"ratio"`, `"sigma"` or
   `"index"` — an explicit name, so a unit-mixing bug cannot hide behind a blank
   (`CLAUDE.md § 5`, `TEST-PROV-001`).
2. **`inputs` contains every operand the formula needs**, named exactly as the registry declares. A
   missing or extra operand is a validation error at the Pydantic boundary (`TEST-PROV-002`).
3. **`display_precision` travels with the value**, so the UI, the PDF and the JSON round identically.
   Formatting is a property of the quantity, not of the surface rendering it (`RT-012`).
4. **Raw measurements are `TracedValue`s too**, with `formula_id = "raw.measurement"` and
   `inputs = {"source_row": "<ingest_id>:<row>"}`. An observation's provenance is its provenance in
   the file — which is exactly what makes it distinguishable from a computed value.
5. **No bare `float` crosses the API for a decision-bearing field.** `TEST-PROV-003` walks the OpenAPI
   schema and asserts it. Purely cosmetic fields (row counts, pagination) are exempt and listed
   explicitly in an allow-list, so the exemption cannot quietly grow.

### 3.1 Nesting

Composite quantities reference their children by `formula_id` + operand name, so the ledger forms a
DAG an auditor can walk downward: `risk_total` → `risk_drift` → `slope_ratio` →
`predicted_long_slope` → `V̂168_final` → `V̂168_shape` → `Φ_g(168)` → the fitted shape artifact. The
UI's ledger drawer renders exactly this walk, one level at a time, which is how an inspector reaches
the arithmetic without being shown a wall of JSON.

## 4. P2 — model provenance

Every response that used a model carries `model_versions` as a map, e.g.
`{"anomaly": "1.0.0", "drift_shape": "1.0.0", "conformal": "1.0.0"}`. Each registered artifact ships
with `manifest.json` alongside its `card.md`:

```json
{
  "name": "drift_shape", "version": "1.0.0",
  "trained_at": "2026-09-14T09:22:41Z",
  "code_git_sha": "<40-hex>", "dirty_worktree": false,
  "config_hash": "sha256:...", "dataset_hash": "sha256:...",
  "train_lot_ids_hash": "sha256:...", "calib_lot_ids_hash": "sha256:...",
  "splits_disjoint": true,
  "library_versions": {"python": "3.11.9", "numpy": "2.1.1", "scipy": "1.14.1",
                       "scikit-learn": "1.5.2"},
  "feature_schema": ["v0", "v24", "delta_24", "..."],
  "artifact_sha256": "sha256:..."
}
```

`dirty_worktree: true` is **fatal for a release artifact** — a model trained from uncommitted code is
not reproducible, so `QG-REL-02` blocks the tag. During development it is a warning that appears in
the health endpoint, so nobody is surprised at release time.

## 5. P3 — dataset provenance

`data/generated/<dataset_hash>/manifest.json` records the generator git SHA, the resolved config and
its SHA-256, the seed and per-part `SeedSequence` scheme, per-file SHA-256 for all three parquet
artifacts, row counts, library versions, and the generation timestamp (metadata only — never inside a
computation, `CLAUDE.md § 5`).

**Datasets are identified by content hash, never by filename** (`ARCHITECTURE § 7.2`). `data.parquet`
tells an auditor nothing; `sha256:9f2c…` tells them everything.

`data_provenance: "SYNTHETIC"` is a **const** in the Pydantic schema (DR-09), present on every
measurement row, every API response and every report page. It is not a boolean flag that a future
commit could flip to `false`; there is no code path that emits any other value, and `TEST-PROV-004`
asserts the enum has exactly one member. INV-3 says the label is unremovable, and this is how.

## 6. P4 — decision provenance (the unusual one)

When an inspector records `CONCUR` / `OVERRIDE` / `DEFER`, the append-only `dispositions` row stores
`system_output_snapshot`: the **exact payload** that was on screen, `TracedValue`s and all, plus
`profile_id@version`, all `model_versions`, the `dataset_hash`, and the `run_id`.

Why this matters, concretely. Two years later an audit asks: *"the inspector overrode a REJECT on this
part — was that reasonable?"* Without the snapshot, the honest answer is *"we cannot tell, the model
has changed since"*. With it, the exact evidence they saw is reconstructable, and the profile version
is immutable once referenced by a disposition (FR-607), so the limits and `k` in force at that moment
are recoverable too.

`OVERRIDE` requires a non-empty reason string (FR-409) — the one free-text field in the system, and it
is a *human's* text, never an explanation the system generated. That asymmetry is deliberate: the
machine's output must be derivable; the human's judgement need not be.

## 7. Report-level provenance (DR-07)

Every exported HTML/PDF report carries, on the first page and in the footer of every subsequent page:

- `SYNTHETIC DATA — NOT ISRO OPERATIONAL DATA` (INV-3, unremovable, in the template as static text
  and asserted by `TEST-REP-002`)
- dataset hash (short form), `profile_id@version`, every `model_version`
- generation timestamp and the `run_id`
- the `α`, `k`, `margin_fraction` and PDA limit in force
- a **Provenance appendix** listing every `formula_id` used in the report with its expression string

The appendix is what makes a printed page auditable offline: a reviewer with the PDF and nothing else
has the formulas, the operands and the numbers, and can recompute the verdict on paper. That is the
strongest possible form of the explainability claim, and it costs one Jinja2 loop over the registry
entries referenced by the report.

## 8. Health and readiness surfacing

`GET /api/v1/health` returns the whole provenance picture at a glance, because the first question in a
live demo is *"is this thing actually connected to anything?"*:

```json
{
  "status": "ok",
  "dataset": {"hash": "sha256:9f2c...", "rows": 143928, "provenance": "SYNTHETIC",
              "generated_at": "2026-09-14T08:01:03Z"},
  "models": [{"name": "anomaly", "version": "1.0.0", "loaded": true, "card": "/api/v1/models"},
             {"name": "drift_shape", "version": "1.0.0", "loaded": true},
             {"name": "conformal", "version": "1.0.0", "loaded": true}],
  "profile": {"id": "mil_std_883_like", "version": 2},
  "formula_registry": {"entries": 41, "hash": "sha256:..."},
  "code": {"git_sha": "<40-hex>", "dirty": false}
}
```

A missing or corrupt artifact yields `status: degraded`, names the missing version, and the endpoints
that need it return `503` while the UI **disables** those surfaces rather than rendering blanks
(`ARCHITECTURE § 9`). A greyed-out panel that says *"drift model not loaded"* is trustworthy; an empty
chart is not.

## 9. Audit obligations

| Test | Asserts |
|---|---|
| `RT-007` | Every decision-bearing field re-derives from its own payload |
| `RT-008` | Repository-wide scan: no numeric literal in UI code or docs that is presented as a *result* |
| `TEST-PROV-001` | Every `TracedValue` has a non-empty unit from the closed unit enum |
| `TEST-PROV-002` | `inputs` matches the registry's declared operands exactly, both directions |
| `TEST-PROV-003` | No bare `float` on a decision-bearing API field (OpenAPI schema walk) |
| `TEST-PROV-004` | `data_provenance` enum has exactly one member, `"SYNTHETIC"` |
| `TEST-PROV-005` | `dispositions` is append-only: no `UPDATE`/`DELETE` path exists to it |
| `TEST-REP-002` | The synthetic-data banner is present on page 1 and in every page footer |
| `RT-012` | UI, API and PDF agree on every displayed number for a sampled part |

`RT-008` is worth its own sentence, because it is the test that catches the most likely honest
mistake: a developer hard-coding `LER = 0.94` into a README table or a slide while the pipeline is
still being wired. The scan distinguishes *illustrative format examples* (permitted, and marked with
an explicit `<!-- illustrative -->` marker or fenced as JSON schema examples) from *asserted results*
(forbidden unless traceable to a `reports/` artifact). Any number presented as a measurement must
resolve to a committed artifact, or the build fails.
