# LATENTIS

Screening tool for making support decisions in the detection of hidden defects in electronic devices during burn-in testing, i.e., devices passing the limit based on static datasheet criteria but showing abnormal behavior within their lot.
---

## The problem

The burn-in and screening processes are based on comparing each unit to an absolute limit. If a certain unit displays 45 µA of leakage with a maximum value of 50 µA specified in the datasheet, it is considered a **pass**, regardless of the fact that all other units within the same batch are at 8–12 µA – 4–5 standard deviations away from their peers. LATENTIS does.
## What it does

LATENTIS processes parametric burn-in data (0 h, 24 h, and beyond) for many devices, and assesses each device based on three different perspectives, as well as another for quality of data:

**Lens 1 - Anomaly.** Is this component statistically abnormal *in relation to its own lot* at the current time? Utilizes lot-wise robust statistics (median ± scaled IQR, inspired by AEC-Q001 Dynamic Part Average Testing), Mahalanobis distance for multivariate parameter analysis, as well as CUSUM detection of drift-in-mean — with an optional Isolation Forest test used only for advisory purposes and unable to make its own determination.

**Lens 2 - Degradation**. Is there an evolution in the behavior of the part, regardless of the fact that it has triggered any threshold value for a point in time anomaly? The use of Shape–Amplitude decomposition for the measurements helps to reveal an evolving degradation despite no obvious anomalies.

**Lens 3 - Projected risk.** In light of the pattern established thus far, will the portion exceed its safety envelope by the time it finishes burning in? Predicts the 168-hour result based on preliminary data and rejects based on a **conformal upper prediction bound**, not a simple point prediction — hence the reject criterion comes with a distribution-free, finite sample validity instead of the other way around. The risk is expressed as a sum of easily understood, additive components (safety margin, slope, projected slope, slope ratio) instead of being presented in one opaque number.

**Sensor confidence.** A rule-based fault detection pass on the telemetry feed – flatlines, impossibles, gaps out of range. This is never incorporated into the Anomaly, Degradation, or Risk scores but travels separately from them to the UI so that any problems with the sensors can never be confused with problems with the components.

All three values for the lenses and all the numbers in between that go into the dispositions decision process come in a **traced value** package, meaning that the number itself is packaged along with its units, its formula version, and the exact input that generated it. All the numbers available to an inspector are re-derivable.

## Design principles

| # | Principle | Explanation |
|---|---|---|
| 1 | Defensible, established statistics (limits as per lot-based DPAT methodology) versus an invented heuristic | Something a reliability engineer can verify mathematically |
| 2 | Conformal prediction controls the reject decision | Distribution-free guarantee on escapes, not manually set threshold |
| 3 | Explicit false-negative target | What we care about is escapes, not false alarms |
| 4 | Shape-Amplitude decomposition for two-point prediction | Not pretending to fit a curve based on two data points |
| 5 | Defined methodology (escape set and recall metric) | Making the core claim verifiable |
| 6 | Provenance ledger behind each number | Click a figure, get the underlying computation |
| 7 | Confidence in the sensors does not bleed into the components | A flakey sensor cannot be confused with a bad part |
| 8 | Disposition at a lot level against a percent defective allowed limit | Like how a real factory dispositions a lot |
| 9 | An exchangeability test which may opt out of making a guarantee | When the statistical guarantees don't apply, the system knows and refuses to answer |
| 10 | Counterfactual explanations ("would have passed if X ≤ value") | Giving an inspector an actionable explanation rather than just attribution |

## Architecture

This project consists of two separate services, both of which use a common scientific core:

**Backend** — FastAPI, where all decisions are based on computation, and the computation logic is isolated to a dependency-free scientific core (`backend/core`). The core is invoked once per computation, and each endpoint in `backend/app` relies on the traced value from this core without any additional computation, thus ensuring that the API, screen values, and reports always agree. Storage uses DuckDB with Parquet storage — a single analytical engine embedded in the service itself instead of a networked database, because a burn-in dataset for a demo or a single test floor does not require that.

**Frontend** — React 18 with TypeScript, bundled using Vite and styled using Tailwind. The UI components use a small custom design tokens system as opposed to an external component library. Data fetching and state management are provided by an API client automatically generated from the backend's OpenAPI spec.

**Reporting** – Server-side HTML/PDF reports with Jinja2 templates that hold the same traceable values displayed on the UI, with an appendix of formulas used for generating that particular report.

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

Each answer is sent out enclosed in an envelope containing the Request ID, the hash of the dataset on which the answer was generated, and the versions of the model/formula used – such that all answers sent out by the API have provenance.

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

None of the proprietary or real components testing data are used in any part of the project. Data used in this project are all simulated data, produced through a known and seeded simulator (`datagen/`). All files containing dataset, API response, user interface screen shots, and reports have the non-removable synthetic data label.

## Known limitations

- The prediction in Lens 3 is derived from two initial readings (0 h and 24 h); this is clearly an extrapolation by shape/linearity, not a learned per-part trajectory model, and the conformal bound tells us so; otherwise we would have been doing something else that overpromises.
- The Isolation Forest, as well as any other model used for benchmarking purposes, acts purely in advisory capacity and is never allowed to independently make or overturn the disposition decision.
- The exchangeability guard is capable of withholding the guaranteed bound due to the violation of statistical assumptions (for example, too many parts per lot) – in such case the system expresses decreased confidence instead.
