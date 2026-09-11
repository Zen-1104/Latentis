# LATENTIS

A screening decision-support platform that catches latent defects in electronic components during burn-in testing — the ones that pass a static datasheet limit but are already behaving abnormally relative to their own production lot.

---

## The problem

Burn-in and screening tests compare each part against a fixed absolute limit. A part reading 45 µA of leakage against a 50 µA datasheet maximum is a **pass** — even if every other part in its lot is sitting at 8–12 µA, which would put that part 4–5 robust standard deviations outside its own cohort. Static limits can't see that. LATENTIS can.

## What it does

LATENTIS ingests parametric burn-in readings (0 h, 24 h, and onward) for a lot of components and evaluates each part through three independent lenses, plus a separate data-quality signal:

**Lens 1 — Anomaly.** Is this part statistically unusual *relative to its own lot*, right now? Combines lot-relative robust statistics (median ± a scaled IQR, in the spirit of AEC-Q001 Dynamic Part Average Testing), a multivariate Mahalanobis distance across parameters, and CUSUM drift-in-mean detection — with Isolation Forest available as a secondary, advisory-only check that can never independently produce a verdict.

**Lens 2 — Degradation.** Is the part's behavior drifting over time, independent of whether it has tripped a point-in-time anomaly threshold? Uses a Shape–Amplitude decomposition of the measurement trajectory so a smooth, progressive drift shows up even when no single reading looks abnormal.

**Lens 3 — Projected Risk.** Given the trend so far, will this part cross its safety envelope by the end of the burn-in window? Forecasts the 168-hour value from early readings and rejects on a **conformal prediction upper bound**, not a bare point estimate — so the reject rule carries a distribution-free, finite-sample guarantee rather than an assumed one. Risk is decomposed into interpretable, additive terms (safety margin, observed slope, projected slope, slope ratio) rather than delivered as a single opaque score. A Neyman–Pearson-style threshold selection process is used so the system can state, explicitly, what false-negative rate a given cutoff implies.

**Sensor Confidence.** A rule-based fault-detection pass over the incoming telemetry itself — flatlines, impossible values, out-of-range gaps. This never gets folded into the Anomaly, Degradation, or Risk scores; it travels alongside them as its own signal, all the way to the UI, so a sensor problem is never mistaken for a component problem.

All three lens scores, plus every intermediate number that feeds a disposition decision, are wrapped in a **traced value** — a structure that carries the value itself, its units, the formula version that produced it, and the exact inputs that went in. Every number shown to an inspector is re-derivable, not just displayed.

## Design principles

| # | Principle | Why it matters |
|---|---|---|
| 1 | Standard, defensible statistics (lot-relative DPAT-style limits) instead of an invented heuristic | Something a reliability engineer can actually check the math on |
| 2 | Conformal prediction drives the reject rule | A distribution-free guarantee on escapes, not a hand-tuned threshold |
| 3 | Explicit false-negative rate targeting | The failure mode that actually matters is missed escapes, not false alarms |
| 4 | Shape–Amplitude decomposition for two-point forecasting | Doesn't pretend to fit a nonlinear curve from two readings |
| 5 | A defined evaluation protocol (an escape set + a named recall metric) | Makes the core claim measurable, not just asserted |
| 6 | A provenance ledger behind every number | Click any figure, see the exact arithmetic that produced it |
| 7 | Sensor confidence never merges into a component verdict | A flaky sensor and a bad part are never conflated |
| 8 | Lot-level disposition against a percent-defective-allowed threshold | Mirrors how a real test floor actually dispositions a lot, not just one part |
| 9 | An exchangeability guard that can decline its own guarantee | The system says when its statistical assumptions no longer hold, instead of answering anyway |
| 10 | Counterfactual explanations ("would have passed if X ≤ value") | Gives an inspector something actionable, not just an attribution chart |

## Architecture

The project is two independently runnable services plus a shared scientific core:

**Backend** — FastAPI, with all decision-bearing computation isolated into a dependency-free scientific core (`backend/core`). The core is called once per computation; every route in `backend/app` reads the resulting traced value rather than recomputing anything, so the API, the on-screen numbers, and the generated reports can never quietly disagree. Storage is DuckDB over Parquet — a single embedded analytical engine rather than a networked database, since a burn-in dataset for a demo or a single test floor doesn't need one.

**Frontend** — React 18 with TypeScript, built with Vite and styled with Tailwind. A small custom design-token system backs the UI components rather than a third-party component library. State and data-fetching are handled through a typed API client generated directly from the backend's OpenAPI schema, so the frontend and backend contracts can't silently drift apart.

**Reporting** — Server-rendered HTML/PDF disposition reports (Jinja2) that carry the same traced values shown in the UI, including a provenance appendix that lists every formula actually used to produce that report.

## Project structure

```
latentis/
├── backend/
│   ├── core/            # The scientific core — DPAT, multivariate stats, CUSUM,
│   │                     shape-amplitude, conformal, safety/risk, attribution,
│   │                     traced-value wrapper, formula registry
│   ├── services/        # Ingest, calibration, investigation, provenance, reports
│   ├── db/               # DuckDB/Parquet persistence layer
│   ├── app/              # FastAPI routers, request/response envelope, error handling
│   ├── reporting/        # HTML/PDF report templates
│   └── tests/            # Unit, property-based, integration, and architecture tests
├── frontend/
│   └── src/
│       ├── api/          # Generated typed client
│       ├── design/       # Design tokens and shared UI primitives
│       ├── features/     # commandCenter, investigation, lot, forecast, disposition, ...
│       └── hooks/
├── datagen/               # Seeded synthetic burn-in data generator
├── docs/                  # Architecture, API, and design-system documentation
├── scripts/                # Dataset generation, reproducibility checks, client codegen
└── tests/                  # Cross-cutting checks (secrets, category coverage)
```

## API reference

The API is versioned under `/api/v1`. A representative slice:

| Endpoint | Description |
|---|---|
| `POST /api/v1/datasets` | Ingest a burn-in dataset |
| `GET /api/v1/components/{id}/investigation` | Full anomaly/degradation/risk investigation for one part |
| `GET /api/v1/components/{id}/explanation` | Attribution + counterfactual explanation for a part |
| `POST /api/v1/components/{id}/disposition` | Record an inspector's disposition decision |
| `GET /api/v1/lots/{lot_id}/statistics` | Lot-level summary statistics |
| `GET /api/v1/lots/{lot_id}/disposition` | Lot-level pass/fail/PDA disposition |
| `GET /api/v1/formulas` / `GET /api/v1/models` | The formula and model registry backing every traced value |
| `POST /api/v1/reports` / `GET /api/v1/reports/{id}/pdf` | Generate and retrieve a disposition report |

Every response is wrapped in a common envelope carrying a request ID, the dataset hash it was computed against, and the model/formula versions used — so any number returned by the API can be traced back to exactly how it was produced.

## Running locally

### Prerequisites
- Python 3.11+
- Node.js 18+

### Backend

```bash
pip install -e .
scripts/generate_demo_dataset.sh   # seeds a synthetic dataset to work against
uvicorn backend.app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.

### Tests

```bash
pytest backend/tests        # unit, property-based, integration, and architecture tests
cd frontend && npm test      # frontend unit tests
```

## Tech stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI |
| ASGI server | Uvicorn |
| Validation | Pydantic |
| Storage | DuckDB + Parquet |
| Data processing | Polars, NumPy, SciPy |
| Statistical/ML methods | scikit-learn (Isolation Forest, robust covariance) |
| Report rendering | Jinja2 (HTML → PDF) |
| Frontend framework | React 18 + TypeScript |
| Build tool | Vite |
| Styling | Tailwind CSS |
| Testing | pytest, Hypothesis (property-based), Vitest, Playwright (E2E) |

## Data honesty statement

No proprietary or real component test data is used anywhere in this project. All data is synthetic, generated by a documented, seeded simulator (`datagen/`). Every dataset file, API response, UI screen, and report artifact carries a non-removable synthetic-data marker, so it's never possible to mistake a demonstration result for a real measurement.

## Known limitations

- The forecast in Lens 3 is built from two early readings (0 h and 24 h); it is explicitly a linear/shape-based extrapolation, not a learned per-part trajectory model, and the conformal bound is what makes that honest rather than a curve-fit that overclaims precision.
- Isolation Forest, and any other benchmark model included for comparison, is advisory only and never permitted to independently produce or override a disposition verdict.
- The exchangeability guard can decline to issue a guaranteed bound when its statistical assumptions are violated (e.g., too few parts in a lot) — in that state the system reports reduced confidence rather than a number it can't stand behind.
