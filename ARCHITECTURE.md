# ARCHITECTURE.md — LATENTIS System Architecture

**Owner:** Backend Engineer + Lead Orchestrator · Conforms to `PROJECT_MASTER_SPEC.md v1.0.0`

## 1. Architectural principles

1. **One computation path.** The number in the UI, the number in the API, and the number in the
   exported report are produced by the *same* function call. There is no display-only arithmetic
   anywhere in the frontend. This is what makes INV-1 enforceable instead of aspirational.
2. **Provenance travels with the value.** A quantity is never transported as a bare float; it is a
   `TracedValue` carrying its inputs, formula identity and versions.
3. **Pure numeric core.** All statistics and models live in a framework-free, I/O-free package that
   can be tested and reasoned about in isolation. FastAPI, DuckDB and React are *adapters* around it.
4. **Configuration is data.** Limits, `k`, `α`, PDA, read-point grids and `Ea` live in profile files,
   never in code. No magic numbers.
5. **Determinism by construction.** Seeded RNG threaded explicitly; no wall-clock in computation;
   stable sort orders everywhere.
6. **Fail loudly, never silently.** No default-on-error, no `try/except: pass`, no NaN coercion.
7. **Offline first.** Nothing at runtime requires the network.

## 2. Layered view

```
┌──────────────────────────────────────────────────────────────────────────┐
│  PRESENTATION — React 18 + TypeScript (strict) + Vite                    │
│  8 surfaces · TanStack Query/Table · ECharts (canvas) · Tailwind tokens   │
│  Zod types GENERATED from OpenAPI. No mock path in the production build.  │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ HTTP/JSON (snake_case), typed
┌───────────────────────────────▼──────────────────────────────────────────┐
│  API — FastAPI + Pydantic v2 · OpenAPI 3.1 · structured errors           │
│  Every response: model_version, dataset_hash, profile_id, computed_at,    │
│                  data_provenance="SYNTHETIC", request_id                 │
└───────────────────────────────┬──────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────┐
│  ORCHESTRATION — use-case services (one per user journey)                │
│  ingest · analyse_lot · investigate_component · dispose · export_report   │
└───────────────────────────────┬──────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────┐
│  VALIDATION & DATA-QUALITY — schema, ranges, duplicates, monotonicity,   │
│  units, censoring, lot integrity → DataQualityReport (itemised)          │
└───────────────────────────────┬──────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────┐
│  NUMERIC CORE  (pure Python + numpy/scipy/sklearn; NO I/O, NO framework) │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────┐ ┌─────────┐ │
│  │ lotstats   │ │ anomaly    │ │ drift      │ │ conformal │ │ risk    │ │
│  │ DPAT/MAD/  │ │ ensemble + │ │ Shape–Amp  │ │ split/CQR │ │ decomp- │ │
│  │ IQR/MCD    │ │ attribution│ │ + residual │ │ Mondrian  │ │ osable  │ │
│  └────────────┘ └────────────┘ └────────────┘ └───────────┘ └─────────┘ │
│  ┌──────────────────────────────────────────────────────────────────────┐│
│  │ explain — TracedValue, formula registry, counterfactuals, narrative  ││
│  └──────────────────────────────────────────────────────────────────────┘│
└───────────────────────────────┬──────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────┐
│  MODEL REGISTRY — immutable versioned artifacts + training manifests     │
│  models/registry/<name>/<semver>/{model.joblib, manifest.json, card.md}  │
└───────────────────────────────┬──────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────┐
│  PERSISTENCE — DuckDB (analytics + measurements) · Parquet (datasets)    │
│  append-only dispositions & ingest_records · no ORM in the numeric path  │
└───────────────────────────────┬──────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────┐
│  REPORTING — Jinja2 → self-contained HTML → PDF via Playwright Chromium  │
└──────────────────────────────────────────────────────────────────────────┘
```

## 3. Technology choices and the reason for each

| Layer | Choice | Why this, not the alternative |
|---|---|---|
| Language (core) | **Python 3.11** | The statistical stack lives here; the team's velocity is here |
| API | **FastAPI + Pydantic v2** | Typed boundary, OpenAPI 3.1 for free, and the frontend types are *generated* rather than duplicated — eliminating an entire class of drift bug |
| Store | **DuckDB** + Parquet | Embedded columnar OLAP: no server to start in a demo (DMR-01), fast group-by over hundreds of thousands of read-points, and real SQL for lot analytics. Postgres would add an ops dependency for zero benefit at this scale; SQLite would be slow on the analytical queries that dominate. |
| Dataframes | **Polars** (ingest) / numpy (core) | Streaming CSV/Parquet ingest with a lazy API; numpy in the core keeps it dependency-light and testable |
| ML | **scikit-learn + scipy** | `MinCovDet`, `HistGradientBoostingRegressor`, `QuantileRegressor`, `IsolationForest` — everything needed, all deterministic under a seed. **No deep-learning framework**, deliberately (`research/ML_METHOD_RESEARCH.md § 1.1`) |
| Frontend | **React 18 + TS strict + Vite** | Fast HMR for an agentic loop; strict TS catches contract drift at compile time |
| Data fetching | **TanStack Query** | Cache/invalidation for a read-heavy console; makes loading/error states explicit (FR-505) |
| Tables | **TanStack Table + virtualiser** | 500 × 6 rows with sorting/filtering at 60 fps (FR-504) |
| Charts | **ECharts** (canvas) + hand-rolled SVG for sparklines | Canvas handles dense scatter/quantile plots; small inline charts stay SVG for crispness and testability |
| Styling | **Tailwind with a locked token layer** | Tokens in `docs/UI_DESIGN_SYSTEM.md` are the contract; raw colour values in components are a lint error |
| Tests | **pytest + Hypothesis + Vitest + Playwright** | Hypothesis is the key one: property tests on robust statistics are how we prove correctness rather than assert it |
| Reports | Jinja2 → HTML → **Playwright Chromium** for PDF | Reuses a dependency we already have. WeasyPrint/LaTeX would add system packages that break DMR-01. |
| Packaging | `uv` (Python) + `npm` (Node), exact pins, lockfiles committed | Reproducibility (NFR-07) and SR-07 |

## 4. Request flow — the flagship path

`GET /api/v1/components/{id}/investigation`

```
 1  API validates the id, resolves active profile + model versions
 2  Repository loads: the part's read-points (0 h, 24 h) and its lot cohort
 3  lotstats  → leave-one-out median, Q1, Q3, IQR, robust σ, n, small-n guard state
 4  anomaly   → per-member scores, max-severity aggregate, percentile, contributions,
               PART/SOCKET/ZONE attribution
 5  drift     → Φ_g(168) lookup → point forecast → residual correction
 6  conformal → one-sided upper bound Û(1−α) for the part's Mondrian group,
               plus the exchangeability-guard verdict
 7  safety    → safety slope, distance to limit, predicted margin, band
               (SAFE/WATCH/EARLY_WARNING/REJECT) computed from Û, not from V̂
 8  risk      → decomposed components; asserted to sum to the total
 9  explain   → narrative from the TracedValues above + counterfactual threshold
10  Response  → InvestigationResponse, every field a TracedValue with provenance
```

Steps 3–9 are **pure functions of their inputs**. That is what makes step 10's provenance claim
true rather than decorative, and it is what lets `RT-007` recompute every number independently.

## 5. The `TracedValue` — the central data structure

Every decision-bearing quantity crossing the API is this shape:

```python
class TracedValue(BaseModel):
    value: float
    unit: str                       # "uA", "ns", "sigma", "ratio", "hours" — never absent
    formula_id: str                 # key into the immutable formula registry
    inputs: dict[str, float | str]  # every operand, named
    parameters: dict[str, float | str]  # k, alpha, Ea, divisor, n, profile_id ...
    model_version: str | None
    dataset_hash: str
    display_precision: int
```

The **formula registry** (`core/explain/formulas.py`) maps `formula_id` → a human-readable
expression string *and* the callable that evaluates it. A single registry entry serves three
consumers: the numeric core computes with the callable, the API ships the expression, and the UI's
"Show the arithmetic" panel renders the expression with the inputs substituted. `RT-007` closes the
loop by evaluating the expression from the payload and asserting it reproduces `value`.

Consequence: **a fabricated number is not merely against policy, it is structurally impossible to
ship** — a hard-coded value has no formula and no inputs, so the auditor fails it immediately.

## 6. Module boundaries and ownership

```
backend/
  app/                    API layer            — Backend Engineer
    routers/  schemas/  deps/  errors/
  services/               use-cases            — Backend Engineer
  core/                   NUMERIC CORE         — Data + ML Engineer  (framework-free)
    lotstats/  anomaly/  drift/  conformal/  risk/  explain/  profiles/
  data/                   repositories, DuckDB — Backend Engineer
  reporting/              Jinja2 + PDF         — Backend Engineer
datagen/                  synthetic generator  — Data + ML Engineer  (MUST NOT be imported by core)
frontend/src/
  api/      generated client + Zod             — Frontend Engineer
  features/ one folder per surface             — Frontend Engineer
  design/   tokens, primitives                 — Product/UI Designer owns tokens
```

**Hard rule (INV-7 + MLR-08):** `backend/core/**` may not import `datagen/**`, `backend/app/**`, or
any I/O module. Enforced by `TEST-ARCH-001`, an import-graph assertion.

## 7. API surface

Full request/response schemas in `docs/API_CONTRACT.md`. Overview:

| Group | Endpoint | Purpose |
|---|---|---|
| Health | `GET /api/v1/health` | Per-component readiness, model versions, dataset identity |
| Ingest | `POST /api/v1/datasets` | Upload CSV/Parquet; returns `ingest_id` + DataQualityReport |
| | `GET /api/v1/datasets/{id}` | Manifest, hashes, row counts, provenance |
| | `POST /api/v1/datasets/{id}/validate` | Re-run validation, itemised findings |
| Profiles | `GET/PUT /api/v1/profiles/{id}` | ScreeningProfile CRUD (limits, k, α, PDA, grid, Ea) |
| Lots | `GET /api/v1/lots` | Lots with flag counts, PDA status, quality score |
| | `GET /api/v1/lots/{id}/statistics` | Per-parameter DPAT limits + robust statistics + guard state |
| | `GET /api/v1/lots/{id}/disposition` | Lot-level recommendation vs. PDA |
| Anomaly | `POST /api/v1/lots/{id}/anomaly` | Run Module A over a lot |
| | `GET /api/v1/components/{id}/anomaly` | Per-part detail: members, contributions, attribution |
| Drift | `POST /api/v1/lots/{id}/drift` | Run Module B over a lot |
| | `GET /api/v1/components/{id}/drift` | Forecast, bound, slopes, margin, band |
| Investigate | `GET /api/v1/components/{id}/investigation` | **The composite flagship payload (§ 4)** |
| Explain | `GET /api/v1/components/{id}/explanation` | Narrative + contributions + counterfactual |
| | `GET /api/v1/formulas/{formula_id}` | Registry entry: expression + description |
| Disposition | `POST /api/v1/components/{id}/disposition` | CONCUR / OVERRIDE+reason / DEFER |
| Reports | `POST /api/v1/reports` → `GET /api/v1/reports/{id}` | Generate and fetch HTML/PDF artifact |
| Model info | `GET /api/v1/models` | Versions, cards, coverage reports, ablation table |
| | `GET /api/v1/models/coverage` | Measured conformal coverage per group |

### 7.1 Error contract

```json
{ "error": { "code": "VALIDATION_FAILED", "message": "3 rows rejected",
             "details": [{ "row": 42, "column": "leakage_ua", "reason": "value 1.2e9 exceeds plausible range" }],
             "request_id": "01J..." } }
```

Codes are a closed enum. `4xx` for anything caused by input — malformed file, unknown id, unit
mismatch, insufficient lot size, missing read-point. `5xx` only for genuine internal faults, and
every `5xx` in a test run is a **P1 defect**. Never a 200 with an error inside the body.

### 7.2 Versioning

- **API:** `/api/v1`; breaking change ⇒ `/api/v2`.
- **Models:** semver per artifact; `model_version` in every response that used it.
- **Profiles:** versioned and immutable once referenced by a persisted disposition — so a
  three-year-old disposition can be reconstructed exactly (FR-607).
- **Datasets:** identified by content hash, never by filename.
- **Formulas:** registry entries are append-only; changing an expression means a new `formula_id`,
  because an old disposition's explanation must still be reproducible.

## 8. Persistence schema (DuckDB)

```
lots(lot_id PK, component_type, lot_start_date, n_parts, profile_id, quality_score, data_provenance)
components(component_id PK, lot_id FK, component_type, board_id, socket_id, thermal_zone)
measurements(component_id FK, parameter, elapsed_hours, value, unit, temperature_c, voltage_v,
             status, ingest_id FK)              -- PK(component_id, parameter, elapsed_hours)
ingest_records(ingest_id PK, file_sha256, row_count, schema_version, created_at, outcome)
analysis_runs(run_id PK, lot_id FK, profile_id, model_versions JSON, dataset_hash, created_at)
part_results(run_id FK, component_id FK, anomaly JSON, drift JSON, risk JSON, verdict)
dispositions(disposition_id PK, component_id FK, run_id FK, action, reason, actor, created_at,
             system_output_snapshot JSON)        -- APPEND ONLY
```

`dispositions.system_output_snapshot` stores the exact payload the inspector saw. Without it, an
audit cannot distinguish "the inspector overrode a correct flag" from "the model changed since".
This is a small column with large audit value.

## 9. Failure modes and behaviour

| Failure | Behaviour |
|---|---|
| Lot has `n < n_min` | Analysis proceeds with the MAD path, `reduced_power: true`, explicit UI warning; never silently applies `IQR/1.35` |
| Missing 24 h read-point | Module B returns `INSUFFICIENT_DATA` with the reason; **no imputation of a decision input** |
| Missing a non-critical covariate | Imputed with the method named in the response's provenance |
| Exchangeability guard fires | `guarantee_status: VOID`, conservative fallback rule, banner in UI, recorded in the report |
| Model artifact missing/corrupt | Health endpoint `degraded`; endpoints needing it return `503` with the missing version named; UI disables those surfaces rather than showing blanks |
| Ingest interrupted | Transactional; no partial commit (NFR-12) |
| Two parameters disagree about a part | Reported as disagreement, **not** averaged away; drives `INDETERMINATE` attribution |

## 10. Deployment

Single machine, offline. `scripts/bootstrap.sh` → create venv, install pinned deps, generate the
seeded dataset, train and register models, start backend (`:8000`) and frontend (`:5173`).
Docker Compose is provided as an alternative but is **not** the demo path — a container runtime is
one more thing to fail in front of judges.

