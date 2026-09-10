# API_CONTRACT.md — HTTP Surface

**Owner:** Backend Engineer · Implements FR-601..FR-608 · Base path `/api/v1`
**Source of truth:** the FastAPI-generated OpenAPI 3.1 document at `/api/v1/openapi.json`. This file is
the *narrative* contract and the design rationale; where the two disagree, the generated document is
authoritative and this file is a bug. Frontend Zod types are **generated** from that document, never
hand-written (`CLAUDE.md § 5`).

## 1. Conventions

| Concern | Rule |
|---|---|
| Case | `snake_case` everywhere in JSON — no per-layer renaming, because a rename layer is where field drift breeds |
| Numbers | Every decision-bearing number is a `TracedValue` object, never a bare float (`TEST-PROV-003`) |
| Units | Always explicit inside the `TracedValue`; never implied by a field name |
| Time | ISO-8601 UTC with `Z`; durations in hours as named fields (`elapsed_hours`) |
| IDs | Opaque strings. **No verdict may depend on an ID** (INV-2, `RT-004`) |
| Pagination | `?limit=&cursor=`; `next_cursor` in the envelope; stable sort keys always specified |
| Errors | Structured envelope, § 9. Never a `200` with an error inside |
| Idempotency | `POST` endpoints that create artifacts accept `Idempotency-Key`; replay returns the original result |
| Auth | **None.** Single-operator local tool (SR-09). Stated in the OpenAPI description and said out loud in the demo |

### 1.1 Envelope on every response

```json
{
  "data": { "...": "endpoint-specific" },
  "meta": {
    "request_id": "01J8Z…", "computed_at": "2026-09-14T09:31:02Z",
    "dataset_hash": "sha256:9f2c…", "profile_id": "mil_std_883_like", "profile_version": 2,
    "model_versions": {"anomaly": "1.0.0", "drift_shape": "1.0.0", "conformal": "1.0.0"},
    "data_provenance": "SYNTHETIC", "code_git_sha": "…", "duration_ms": 41
  }
}
```

`meta` is **not optional and not trimmable**. Its presence on every single response is what makes
provenance a property of the API rather than of individual endpoints, and `data_provenance` is a
single-member enum (`PROVENANCE_SPEC § 5`) so no code path can emit anything else.

## 2. Core schema — `TracedValue`

```json
{
  "value": 22.4, "unit": "uA", "formula_id": "dpat.limit_high",
  "expression": "median + k * (IQR / 1.35)",
  "inputs": {"median": 10.4, "k": 6, "IQR": 2.7},
  "parameters": {"divisor": 1.35, "profile_id": "mil_std_883_like@2"},
  "model_version": "anomaly-1.0.0", "dataset_hash": "sha256:9f2c…",
  "display_precision": 1, "source_ref": "D-CD-02"
}
```

`expression` is included in the payload — not merely a `formula_id` to look up — so a report or an
offline auditor holding only the JSON can recompute the value with nothing else. That single redundant
field is what makes `RT-007` runnable against a saved payload.

## 3. Health

`GET /health` → the full provenance picture (`PROVENANCE_SPEC § 8`). `200` with
`status: ok | degraded`; a `degraded` response names each missing or unloadable artifact. Never `500` —
a health endpoint that cannot report ill health is useless.

## 4. Ingest & datasets

| Method | Path | Notes |
|---|---|---|
| `POST` | `/datasets` | multipart CSV/Parquet. Returns `ingest_id`, `dataset_hash`, row counts and a full `DataQualityReport`. Transactional: no partial commit (NFR-12) |
| `GET` | `/datasets` | List with hashes, row counts, created-at |
| `GET` | `/datasets/{dataset_hash}` | Manifest: config hash, seed, generator SHA, per-file hashes |
| `POST` | `/datasets/{dataset_hash}/validate` | Re-runs the § 12 gates of `DATASET_SPEC`; itemised findings |

`DataQualityReport` is itemised, never a score alone:

```json
{
  "quality_score": {"value": 0.86, "unit": "ratio", "formula_id": "dq.score_v1", "...": "TracedValue"},
  "rows_total": 143928, "rows_accepted": 143511, "rows_rejected": 417,
  "findings": [
    {"code": "UNIT_MISMATCH", "severity": "ERROR", "count": 288,
     "column": "measurement_unit", "detail": "mA where uA expected for iddq_standby",
     "affected_lots": ["L-2026-017"], "sample_rows": [1042, 1043],
     "action": "rows rejected; lot flagged for unit review"},
    {"code": "CENSORED_READING", "severity": "WARNING", "count": 671,
     "detail": "BELOW_LOD retained as censored; not coerced to zero (FR-107)"},
    {"code": "DUPLICATE_KEY", "severity": "WARNING", "count": 43,
     "detail": "(component_id, parameter, elapsed_hours) duplicates; first retained, both recorded"}
  ]
}
```

The `action` field on every finding is deliberate: a validation report that states a problem without
stating what the system *did about it* leaves the operator unable to reason about the data they are now
looking at.

## 5. Profiles

| Method | Path | Notes |
|---|---|---|
| `GET` | `/profiles` | All profiles with versions |
| `GET` | `/profiles/{id}` | Limits per parameter, `k`, `α`, `margin_fraction`, `horizon_hours`, PDA limit, read-point grid, `Ea` per parameter, risk weights, transform choices — each with its provenance tag |
| `PUT` | `/profiles/{id}` | Creates a **new version**; existing versions are immutable |

Immutability is not a nicety. A disposition recorded against `mil_std_883_like@2` must be
reconstructable exactly (FR-607), so a `PUT` that mutated a referenced profile in place would silently
invalidate every historical decision.

## 6. Lots

| Method | Path | Notes |
|---|---|---|
| `GET` | `/lots` | `n_parts`, flagged count, `early_warning_count`, `pda_pct` + verdict, quality score, `reduced_power` |
| `GET` | `/lots/{id}/statistics` | Per parameter × read-point: `n`, median, Q1, Q3, IQR, robust σ, MAD, transform + λ, DPAT limits, guard states — all `TracedValue`s |
| `POST` | `/lots/{id}/anomaly` | Run Module A across the lot; returns per-part summaries + the run_id |
| `POST` | `/lots/{id}/drift` | Run Module B across the lot |
| `GET` | `/lots/{id}/disposition` | PDA roll-up, both figures (`RISK_SCORING_SPEC § 5`), lot verdict |

`GET /lots/{id}/statistics` returns statistics computed **leave-one-out per part** where a part-specific
limit is requested (`?for_component=`), and cohort-level otherwise. The two differ, and conflating them
is leakage risk LK-5 — so the response names which one it is in `cohort_mode`.

## 7. Components

| Method | Path | Returns |
|---|---|---|
| `GET` | `/components/{id}` | Static metadata + all read-points visible to screening (0 h, 24 h only) |
| `GET` | `/components/{id}/anomaly` | The `ANOMALY_SPEC § 8` contract |
| `GET` | `/components/{id}/drift` | The `DRIFT_SPEC § 8` contract |
| `GET` | `/components/{id}/investigation` | **Flagship composite** — anomaly + drift + risk + explanation in one payload |
| `GET` | `/components/{id}/explanation` | Narrative, attribution, counterfactuals |
| `POST` | `/components/{id}/disposition` | `CONCUR` / `OVERRIDE` (reason required) / `DEFER` |

### 7.1 `GET /components/{id}/investigation`

The single call behind surface S3, assembled by the 10-step flow in `ARCHITECTURE § 4`:

```json
{
  "data": {
    "component": {"component_id": "C-L2026-041-0137", "lot_id": "L-2026-041",
                  "component_type": "CMOS_LOGIC", "board_id": "B-3", "socket_id": "S-14",
                  "thermal_zone": "Z-2", "tester_id": "T-01"},
    "parameters": [
      {"parameter": "iddq_standby", "unit": "uA",
       "readings": [{"elapsed_hours": 0, "value": {"...": "TracedValue"}, "status": "OK"},
                    {"elapsed_hours": 24, "value": {"...": "TracedValue"}, "status": "OK"}],
       "anomaly": {"...": "ANOMALY_SPEC § 8"},
       "drift":   {"...": "DRIFT_SPEC § 8"}}
    ],
    "risk": {"...": "RISK_SCORING_SPEC § 7"},
    "explanation": {"narrative": "…", "layers": ["verdict", "arithmetic", "attribution",
                                                 "counterfactual"],
                    "counterfactuals": [{"kind": "k_sensitivity", "question": "At what k does the PAT verdict flip?",
                                         "answer": {"...": "TracedValue"},
                                         "sentence": "This part flags at any k below 17.4."}]},
    "guards": {"reduced_power": false, "insufficient_data": false, "censored": false,
               "exchangeability": "PASS", "mondrian_level": 0},
    "worst": {"parameter": "iddq_standby", "severity": "SEVERE", "band": "WATCH",
              "recommendation": "INVESTIGATE"}
  },
  "meta": {"...": "§ 1.1"}
}
```

Design notes:

- **One call, not six.** The frontend must not assemble a verdict from multiple responses, because that
  would put decision logic in the browser (`ARCHITECTURE § 1`).
- **`worst` is precomputed server-side**, so "which parameter is the problem" is not a client-side
  `max()` over parameters — again, no browser-side decision arithmetic.
- The payload is large (~40–80 KB for six parameters). Accepted deliberately: completeness is the point,
  and `?parameters=iddq_standby` narrows it when a caller wants less.

### 7.2 `POST /components/{id}/disposition`

```json
{"action": "OVERRIDE", "reason": "Retested in socket S-02; reading nominal at 11.1 uA.",
 "actor": "OP-04", "run_id": "01J8Z…"}
```

`reason` is mandatory and non-empty for `OVERRIDE` (FR-409) — `422` otherwise. The server stores
`system_output_snapshot`: the exact investigation payload the operator saw. The row is **append-only**
(`TEST-PROV-005`); a correction is a new row referencing the prior `disposition_id`, never an update.

## 8. Models, explanations, reports

| Method | Path | Notes |
|---|---|---|
| `GET` | `/models` | Registered artifacts, versions, card markdown, feature schemas, `loaded` state |
| `GET` | `/models/coverage` | Measured conformal coverage per Mondrian group with Clopper–Pearson CIs, widths, Winkler |
| `GET` | `/models/ablation` | The ablation table as data, sourced from the committed `reports/ABLATION_<tag>.md` run |
| `GET` | `/models/shape/{group}` | The fitted `Φ_g` curve as points, plus family, parameter, `Φ_g(168)`, fit quality |
| `GET` | `/formulas` · `/formulas/{formula_id}` | Registry entries: expression, description, operands, unit rule, `source_ref` |
| `POST` | `/reports` | `{scope: component|lot|evaluation, target_id, format: html|pdf}` → `report_id` |
| `GET` | `/reports/{id}` | Metadata + download URL; PDF generated via Playwright Chromium |

`GET /models/shape/{group}` exists so the fitted shape can be **plotted and disputed** by a reliability
engineer (`DRIFT_SPEC § 4.2`). Publishing the one number the whole forecast rests on, as a curve, is the
opposite of a black box — and it is a question we would rather be asked in the demo than after it.

## 9. Errors

```json
{
  "error": {
    "code": "INSUFFICIENT_COHORT",
    "message": "Lot L-2026-039 has 2 measurable parts for iddq_standby at 24 h; minimum is 3.",
    "details": [{"lot_id": "L-2026-039", "parameter": "iddq_standby", "n": 2, "n_min": 3}],
    "remediation": "Analysis deferred to absolute limits. Ingest more parts or accept limit-only screening.",
    "request_id": "01J8Z…"
  }
}
```

Closed enum, with the status each maps to:

| Code | Status | Meaning |
|---|---|---|
| `VALIDATION_FAILED` | 422 | Input rows rejected; `details` lists row/column/reason |
| `UNIT_MISMATCH` | 422 | Unit inconsistent with the profile |
| `UNKNOWN_COMPONENT` / `UNKNOWN_LOT` / `UNKNOWN_DATASET` / `UNKNOWN_PROFILE` | 404 | — |
| `INSUFFICIENT_COHORT` | 422 | `n < 3` (`ANOMALY_SPEC § 9`) |
| `INSUFFICIENT_DATA` | 422 | Required read-point missing; **no imputation** (FR-303) |
| `INSUFFICIENT_CALIBRATION` | 422 | `α` unattainable from `n_cal`; reports `attainable_alpha` (`CONFORMAL_SPEC § 2.1`) |
| `NO_VARIATION` | 422 | Zero IQR **and** zero MAD |
| `MODEL_UNAVAILABLE` | 503 | Artifact missing/corrupt; names the version |
| `PROFILE_IMMUTABLE` | 409 | Attempt to mutate a referenced profile version |
| `REASON_REQUIRED` | 422 | `OVERRIDE` without a reason |
| `INTERNAL_ERROR` | 500 | Genuine fault — **every occurrence in a test run is a P1 defect** |

`remediation` is present on every 4xx. An error that tells an operator what went wrong but not what to
do next converts a data problem into a support ticket.

## 10. Non-functional contract

| Endpoint class | Target (measured in `reports/PERFORMANCE.md`, not asserted here) |
|---|---|
| `GET /components/{id}/investigation` | p95 < 400 ms on the default 40-lot dataset |
| `POST /lots/{id}/anomaly` (500 parts × 6 params) | p95 < 8 s |
| `POST /datasets` (≈144 000 rows) | < 60 s, streaming, transactional |
| `POST /reports` (PDF) | < 15 s |

## 11. Contract testing

| Test | Asserts |
|---|---|
| `TEST-API-001` | Generated Zod types compile against the live OpenAPI document — no drift |
| `TEST-API-002` | Every endpoint returns the full `meta` envelope |
| `TEST-PROV-003` | No bare float on a decision-bearing field (OpenAPI schema walk) |
| `TEST-API-004` | Every error code in the enum is reachable by a real request, and no other code is emitted |
| `TEST-API-005` | No `5xx` anywhere in the full test corpus, including the degenerate-case suite |
| `RT-004` | ID permutation leaves every verdict and every payload number unchanged |
| `RT-012` | UI ↔ API ↔ PDF numeric agreement for a sampled part |

`TEST-API-004` running in both directions is the useful part: unreachable codes are dead documentation,
and codes emitted but not enumerated are exactly how a frontend ends up with an unhandled error state.

