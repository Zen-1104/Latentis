# PROJECT_MASTER_SPEC.md — LATENTIS

**Single source of truth for SIH26170.** If any other document contradicts this one, this one wins
and the other document is a defect. Changes require a `DECISIONS.md` entry.

| Field | Value |
|---|---|
| Problem statement | SIH26170 — AI-Driven Anomaly Detection in Component Burn-In & Screening |
| Organisation | Indian Space Research Organisation (ISRO) |
| Category | Smart Automation · Software |
| Deadline | 30 September 2026 |
| System name | **LATENTIS** — LATENT-defect Inspection & Screening |
| Spec version | 1.0.0 |
| Phase | 0 — Foundation (specification complete, implementation not started) |

---

## 1. Problem statement

Environmental Stress Screening of electronic components for space payloads uses burn-in
(operation at elevated temperature, e.g. 125 °C, for 48–168 h) to precipitate latent defects
before flight. Disposition conventionally rests on **absolute parametric limits** measured at
read-points.

Absolute limits are blind to two things:

1. **Population context.** A part reading 45 µA against a 50 µA absolute maximum passes — even
   when its own lot sits at 10 µA. It is a ~17σ outlier by its lot's own robust statistics.
2. **Trajectory.** A part inside limits at every read-point may be degrading on a path that
   crosses the limit shortly after the screen ends.

Parts of either kind are **escapes**: they enter a payload carrying a defect the screen was
chartered to remove. Escapes are expensive in a way ordinary manufacturing defects are not —
they surface after integration, after launch, or never (as an unexplained on-orbit anomaly).

**LATENTIS detects escapes by judging each part against its own lot and against its own
trajectory, and by explaining every judgement in terms a QA inspector can verify by hand.**

### 1.1 Scope

**In scope.** Ingesting burn-in read-point data; validating it; computing lot-relative statistics;
detecting lot-relative parametric anomalies; forecasting 168 h values from 0 h + 24 h with
calibrated uncertainty; deriving a safety criterion from configuration; scoring and ranking risk;
generating verifiable explanations; part **and** lot disposition recommendation; an inspector
workstation UI; an exportable audit-grade report.

**Out of scope (stated, not hidden).** Controlling burn-in ovens or testers; replacing a qualified
screening flow or its authority; physical failure analysis (de-cap, SEM, curve trace); radiation
effects; any claim about a specific real device; autonomous rejection without human disposition.

### 1.2 What "success" means

A QA inspector, given a lot that passes conventional screening, can use LATENTIS to identify the
parts that should not fly, understand *why* in under 60 seconds each, disagree with the system
where warranted, and export a record that survives an audit three years later.

---

## 2. Users and personas

### P1 — QA Inspector (primary, highest-frequency user)

Reviews screening output shift by shift. Not a data scientist. Accountable for a signature on a
disposition. Needs: a prioritised work queue; the evidence behind each flag in one screen; the
ability to concur/override with a reason; a report artifact. **Fails us if:** the system shows a
score without evidence, changes its answer between refreshes, or takes more than a few seconds to
answer "why this part?".

### P2 — Reliability Engineer (deepest scrutiny)

Owns screening effectiveness and limit-setting. Will interrogate the statistics. Needs: DPAT limit
derivation visible and adjustable; the distribution plot with the part located on it; the drift
model's population shape; coverage reports; ablations; the sensitivity of outcomes to `k` and `α`.
**Fails us if:** a statistic is unexplained, a threshold is unjustified, or an uncertainty claim is
unmeasured. **This persona is the model for the hostile judge.**

### P3 — Test Engineer (data provider, artefact hunter)

Owns the burn-in boards, sockets and testers. Cares whether an anomaly is the *part* or the *setup*.
Needs: per-socket and per-zone views; the attribution verdict; retest recommendations; data-quality
diagnostics. **Fails us if:** the system condemns good parts sitting in a bad socket.

### P4 — Engineering Manager / Reviewer (throughput and accountability)

Needs lot-level disposition, yield and flag-rate impact, PDA status, override audit trail, and a
one-page summary. **Fails us if:** the system cannot say what it costs in scrapped good parts.

*(Secondary: **Auditor** — needs only the exported artifact to be complete and self-contained.)*

---

## 3. User journeys

### J1 — Shift review (P1, the core loop, target < 10 min per lot)

Open **Dashboard** → lots awaiting review, each with flag count and PDA status → open a lot →
**prioritised part queue** ordered by risk with the dominant reason as a one-line chip → open the
top part → **Investigation view**: the four read-points plotted with the lot band behind them, the
absolute limit, the DPAT limits, the forecast with its conformal bound, the safety boundary, the
plain-language reason, and the counterfactual → click any number → **"Show the arithmetic"** panel
re-derives it → decide `CONCUR` / `OVERRIDE + reason` / `DEFER FOR RETEST` → next part →
**Export report** for the lot.

### J2 — Method challenge (P2)

Open a flagged part → open **Lot Statistics** → see `n`, median, Q1, Q3, IQR, robust σ, the
computed limits, and the small-`n` guard state → change `k` from 6 to 4.5 in a scoped what-if →
see which parts change verdict and the FN/FP trade-off move on the NP-ROC → open **Model Info** →
population shape `Φ_g(t)`, coverage report per group, exchangeability-guard state, ablation table.
No change is persisted without an explicit save and a `DECISIONS`-style audit entry.

### J3 — Artefact triage (P3)

Open **Anomaly Analysis** → group by socket → a socket showing a coherent offset across all its
parts is surfaced as a **setup-attributed** cluster with parts marked *retest recommended, not
rejected* → export a retest list.

### J4 — Lot disposition (P4)

Open a lot → flagged fraction vs. PDA → if exceeded, lot escalation with the contributing modes →
review overrides → export the lot summary.

### J5 — Cold start (evaluator/judge, target < 5 min from clone to insight)

`scripts/bootstrap.sh` → generate the synthetic dataset from a seed → start backend and frontend →
land on a Dashboard populated with real computed values → run the demo scenario in
`docs/DEMO_SCENARIO.md`. Everything must work offline with no external service.

---

## 4. Functional requirements

IDs are stable and referenced by `tests/tests.json`. Priority: **P0** = release blocker,
**P1** = required for a complete submission, **P2** = valuable, **P3** = nice to have.

### 4.1 Ingestion & validation

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-101 | Ingest read-point data from CSV and Parquet, ≥ 100 000 rows, streaming (no full-file memory load) | P0 |
| FR-102 | Validate against a declared schema; reject the file with a **row-and-column-precise** error report; never partially commit | P0 |
| FR-103 | Detect and report: missing read-points, duplicate `(component_id, parameter, elapsed_hours)`, non-monotonic time, out-of-range values, unit mismatches, unknown `lot_id`, single-part lots | P0 |
| FR-104 | Compute and persist a **data-quality score** per lot with itemised deductions | P1 |
| FR-105 | Store an immutable ingest record: file SHA-256, row count, timestamp, schema version, validation outcome | P0 |
| FR-106 | Accept a `ScreeningProfile` (read-point grid, stress condition, absolute limits, delta limits, PDA, `k`, `α`) as data, not code | P0 |
| FR-107 | Support censored/flagged measurements (`<LOD`, `overrange`, `not_measured`) as first-class values, never as 0 or NaN silently | P1 |
| FR-108 | Reject any upload whose declared units disagree with the profile, with a fix suggestion | P1 |

### 4.2 Module A — dynamic outlier detection

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-201 | Compute DPAT limits `median ± k·(IQR/1.35)` per `(lot, component_type, parameter, read_point)`, **excluding the part under test** (leave-one-out) | P0 |
| FR-202 | Apply the `n < 20` guard: switch to `1.4826·MAD`, apply the finite-sample correction, and surface a reduced-power warning | P0 |
| FR-203 | Run the full ensemble: DPAT, MAD-z, Tukey bands, adjusted boxplot, robust Mahalanobis (MCD) | P0 |
| FR-204 | Run Isolation Forest as an explicitly-labelled cross-check that cannot alter the verdict | P2 |
| FR-205 | Aggregate by **max severity**, reporting which members fired and which did not | P0 |
| FR-206 | Emit per part: anomaly score, severity band, confidence, percentile rank in lot, contributing parameters with magnitudes, the lot statistics used, absolute-limit status, relative-risk status | P0 |
| FR-207 | Compute Zonal DPAT limits per `thermal_zone` when `n_zone ≥ n_min` | P1 |
| FR-208 | Attribute each anomaly to `PART` / `SOCKET` / `ZONE` / `INDETERMINATE` with the evidence for the attribution | P1 |
| FR-209 | Select the operating threshold by the Neyman–Pearson rule on `calib` for a chosen `α`; expose `α` as Mission Risk Posture | P1 |
| FR-210 | Never allow a part **outside** absolute limits to be reported as anything but a hard fail | P0 |

### 4.3 Module B — drift prediction

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-301 | Predict `Value_168h` using **only** features available at ≤ 24 h; enforce by an input allow-list | P0 |
| FR-302 | Implement the Shape–Amplitude model with a fitted, reported population shape `Φ_g(t)` | P0 |
| FR-303 | Report the naïve linear extrapolation as a labelled baseline in the same payload | P1 |
| FR-304 | Apply a residual correction model (ridge, and GBT if it beats ridge out-of-sample) | P1 |
| FR-305 | Produce a **one-sided upper conformal bound** `Û₁₆₈(1−α)`, Mondrian-conditioned on `component_type` | P0 |
| FR-306 | Compute observed early slope, predicted long-term slope, **safety slope**, distance to limit, predicted margin — all in physical units | P0 |
| FR-307 | Classify into `SAFE` / `WATCH` / `EARLY_WARNING` / `REJECT` using the **bound**, not the point estimate | P0 |
| FR-308 | Run the exchangeability guard; when it fires, mark the guarantee `VOID`, degrade conservatively, and say so in the UI | P1 |
| FR-309 | Express margin optionally in **equivalent field hours** via the Arrhenius AF, with `Ea` shown | P2 |
| FR-310 | Report measured conformal coverage per group in the model-info surface | P1 |

### 4.4 Risk, explanation, disposition

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-401 | Compute a **decomposable** risk score; the components must sum to the total exactly (float tolerance) | P0 |
| FR-402 | Generate an explanation from the same values the decision used; no template with invented numbers | P0 |
| FR-403 | Attach a **provenance record** to every displayed quantity: inputs, `formula_id`, parameters, model version, dataset hash | P0 |
| FR-404 | Provide a **counterfactual threshold** for each flagged part, on an inspector-observable input | P1 |
| FR-405 | Explanations are deterministic: identical input ⇒ byte-identical explanation | P0 |
| FR-406 | Record inspector disposition (`CONCUR` / `OVERRIDE` + reason / `DEFER`) with user, timestamp, and the exact system output at that moment | P0 |
| FR-407 | Compute lot disposition against PDA; escalate when exceeded | P1 |
| FR-408 | Export a self-contained report (HTML + PDF) containing every value, its provenance, the model versions, and the dataset hash | P0 |
| FR-409 | Mark every artifact `SYNTHETIC DATA` unremovably | P0 |
| FR-410 | Rank the work queue by risk, with the dominant reason as a one-line chip | P1 |

### 4.5 Frontend

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-501 | Eight surfaces: Dashboard, Lots, Components, Anomaly Analysis, Drift Forecast, Component Investigation, Reports, System & Model Info | P0 |
| FR-502 | **Every number rendered is fetched from the API.** No client-side recomputation of a decision, no mock data path in production build | P0 |
| FR-503 | "Show the arithmetic" panel available on every decision-bearing number | P0 |
| FR-504 | Handle 500-part lots × 6 parameters without perceptible lag (virtualised tables, canvas charts) | P1 |
| FR-505 | Explicit empty, loading, error, and partial-data states on every surface — no silent blanks | P0 |
| FR-506 | Keyboard-first navigation for the inspector loop (`j`/`k` queue, `c`/`o`/`d` disposition, `?` help) | P2 |
| FR-507 | WCAG 2.1 AA: contrast, focus order, labels, no colour-only status encoding | P1 |
| FR-508 | Persistent `SYNTHETIC DATA` banner that no interaction can dismiss | P0 |
| FR-509 | Deep-linkable URLs for every part and lot (audit and demo reliability) | P1 |
| FR-510 | Offline-capable: no CDN, no external font, no telemetry call | P0 |

### 4.6 Backend

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-601 | Typed REST API with a generated OpenAPI 3.1 document; the frontend's types are generated from it | P0 |
| FR-602 | Every response carries `model_version`, `dataset_hash`, `profile_id`, `computed_at`, `data_provenance: "SYNTHETIC"` | P0 |
| FR-603 | Structured errors: `{code, message, details, request_id}`; **no 500 for any malformed input** | P0 |
| FR-604 | Deterministic: same input + same versions ⇒ identical response body (metadata timestamps excluded) | P0 |
| FR-605 | Model registry with immutable versioned artifacts and their training manifests | P1 |
| FR-606 | Health endpoint reporting per-component readiness, loaded model versions, and dataset identity | P0 |
| FR-607 | Request/response audit log sufficient to reconstruct any past disposition | P1 |
| FR-608 | Runs fully offline on a laptop; single command start | P0 |

---

## 5. Non-functional requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | API p95 latency, per-part endpoints | < 200 ms |
| NFR-02 | Full lot analysis, 500 parts × 6 parameters | < 3 s |
| NFR-03 | Ingest throughput | ≥ 50 000 rows/s |
| NFR-04 | Memory ceiling, backend | < 1 GB for a 100 k-row dataset |
| NFR-05 | Cold start, both services | < 20 s |
| NFR-06 | Determinism | Byte-identical outputs for identical inputs |
| NFR-07 | Reproducibility | Seed ⇒ identical dataset hash, verified in CI |
| NFR-08 | Test coverage, core numeric modules | ≥ 90 % line, ≥ 80 % branch |
| NFR-09 | Zero external network dependency at runtime | Enforced by a test that blocks egress |
| NFR-10 | Accessibility | WCAG 2.1 AA on the four primary surfaces |
| NFR-11 | Portability | Linux + macOS, Python 3.11+, Node 20+ |
| NFR-12 | Recovery | Any interrupted ingest leaves no partial state |

## 6. ML requirements

| ID | Requirement |
|----|-------------|
| MLR-01 | No supervised learning inside the detector; labels are used for evaluation only |
| MLR-02 | All splits lot-disjoint; temporal split reported as a secondary protocol |
| MLR-03 | Three disjoint sets: `train` / `calib` / `test`; `test` scored once per release by the Integration agent |
| MLR-04 | Every model artifact ships a **model card** (`models/MODEL_CARD_TEMPLATE.md`) |
| MLR-05 | Every reported metric carries mean ± std over ≥ 5 dataset seeds |
| MLR-06 | Conformal coverage measured and inside the binomial band for the nominal level |
| MLR-07 | Ablation table published; components failing their ablation are **removed** |
| MLR-08 | No component may import the data generator |
| MLR-09 | Feature allow-list enforced in code for Module B |
| MLR-10 | All randomness seeded from config; no global RNG |

## 7. Explainability requirements

| ID | Requirement |
|----|-------------|
| XR-01 | Every decision-bearing number has a provenance record sufficient for independent recomputation |
| XR-02 | Re-derivation rate = 100 %, measured automatically by `RT-007` |
| XR-03 | Explanations deterministic and reproducible |
| XR-04 | Every explanation states: the observed value, the reference population, the distance in robust σ, the percentile, the absolute-limit status, and the forecast bound vs. the safety boundary — in physical units |
| XR-05 | A counterfactual threshold accompanies every flag |
| XR-06 | Multivariate contributions are exact (Mahalanobis decomposition), not sampled |
| XR-07 | The UI must never display a score without its decomposition reachable in one interaction |
| XR-08 | Uncertainty is always shown with the decision: bound, coverage level, and guard state |

## 8. Data requirements

| ID | Requirement |
|----|-------------|
| DR-01 | Synthetic dataset generated by a seeded, specified generator (`data/DATA_GENERATION_SPEC.md`) |
| DR-02 | Three physical artifacts: `screening`, `truth`, `full` (§ R11) |
| DR-03 | Every generator parameter tagged `cited` / `derived` / `assumed` with a rationale |
| DR-04 | Strata `S0..S5` present, with `S1` and `S2` non-empty |
| DR-05 | A documented subset is `absolute-limit PASS` + `lot-relative ANOMALOUS` + `forecast UNSAFE` |
| DR-06 | `manifest.json` per dataset with config hash, git SHA, versions, per-file SHA-256 |
| DR-07 | Realistic imperfections: missing values, censored readings, duplicates, unit errors, lot shifts |
| DR-08 | `reports/DATASET_PROFILE.md` generated from the data, never hand-written |
| DR-09 | Every row and every artifact carries `data_provenance = "SYNTHETIC"` |
| DR-10 | Generator authored against a frozen spec **before** the detector, and that ordering is visible in git history |

## 9. Testing requirements

| ID | Requirement |
|----|-------------|
| TR-01 | Unit tests for every numeric function, including **known-answer tests** computed by hand and written into the test file |
| TR-02 | Property-based tests (Hypothesis) for all statistics: scale/shift equivariance, permutation invariance, outlier-insensitivity of robust estimators |
| TR-03 | Leakage tests `TEST-DL-001..008` |
| TR-04 | API contract tests generated from the OpenAPI document |
| TR-05 | End-to-end Playwright tests against the real running application |
| TR-06 | Red-team suite `RT-001..RT-015` |
| TR-07 | Regression suite re-run after every fix; a fixed bug gains a permanent test |
| TR-08 | Performance tests asserting the NFR budgets |
| TR-09 | Determinism test: run twice, diff outputs byte-for-byte |
| TR-10 | **No test may be weakened to make an implementation pass** (INV-6) |

## 10. Security requirements

Scoped honestly to what a hackathon deliverable can actually guarantee.

| ID | Requirement |
|----|-------------|
| SR-01 | All input validated by Pydantic at the boundary; no `eval`, no `pickle` of untrusted data, no dynamic import from user input |
| SR-02 | Uploaded files: size cap, extension + magic-byte check, safe-path handling, CSV formula-injection neutralisation on export, zip/parquet bomb guards |
| SR-03 | Parameterised SQL only; no string-built queries |
| SR-04 | No secrets in the repository or in logs; config via environment |
| SR-05 | CORS restricted to the local frontend origin; no wildcard |
| SR-06 | Errors never leak stack traces or filesystem paths to the client |
| SR-07 | Dependencies pinned to exact versions; lockfiles committed; `pip-audit`/`npm audit` in CI |
| SR-08 | Report export sanitises all user-supplied strings (override reasons) against HTML/PDF injection |
| SR-09 | **Stated limitation:** the demo has no authentication. It is a single-operator local tool. Multi-user auth, RBAC, and signed audit trails are named in Future Scope, not claimed. |
| SR-10 | The audit log is append-only at the application layer; genuine tamper-evidence (hash chaining) is implemented if time permits and otherwise declared absent |

**SR-09 is deliberate and must be said out loud** — a network-exposed screening tool without
authentication would be a real defect, so we bound the deployment claim instead of pretending.

## 11. Demo requirements

| ID | Requirement |
|----|-------------|
| DMR-01 | Runs offline, from a clean clone, on a single laptop, in ≤ 5 minutes (`scripts/bootstrap.sh`) |
| DMR-02 | The flagship escape case is reachable in ≤ 3 clicks from the Dashboard |
| DMR-03 | Every number shown during the demo is live-computed and provably so via "Show the arithmetic" |
| DMR-04 | A deterministic demo seed produces the identical narrative every run |
| DMR-05 | Runs with no internet; no cloud dependency; no login |
| DMR-06 | A scripted fallback path exists for every step that could fail live (`docs/DEMO_SCENARIO.md § 8`) |
| DMR-07 | Total runtime of the scripted demo ≤ 6 minutes, with a 3-minute cut-down variant |
| DMR-08 | A judge may type an arbitrary component ID and get a real answer — nothing is pre-baked |

## 12. Judging requirements

Mapped in full in `docs/SIH_JUDGING_STRATEGY.md`. Binding here:

| ID | Requirement |
|----|-------------|
| JR-01 | Every slide metric traces to a committed artifact under `reports/` |
| JR-02 | The problem framing cites MIL-STD-883 Method 1015's stated purpose (D-A-01) |
| JR-03 | The method cites AEC-Q001 PAT as its baseline (D-CD-01/02) |
| JR-04 | The false-negative claim is expressed as a *bound*, not an accuracy figure |
| JR-05 | Synthetic data is declared on the dataset slide, unprompted |
| JR-06 | Limitations are presented by us before a judge finds them |
| JR-07 | The ablation table is in the appendix and offered proactively |

## 13. Acceptance criteria

The submission is acceptable only when **all** hold:

1. `scripts/bootstrap.sh` on a clean clone yields a working system with computed values.
2. All P0 functional requirements are `Verified` (per `CLAUDE.md § 4`).
3. `TEST-DL-001..008` pass — no leakage.
4. Measured conformal coverage lies inside the binomial band for the nominal level.
5. `LER(full system) > LER(DPAT only) > LER(static limits) = 0` on strata `S1`+`S2`, with the
   improvement exceeding the seed-to-seed spread.
6. Re-derivation rate = 100 % (`RT-007`).
7. Playwright suite green against the real application.
8. Red-team suite `RT-001..RT-015` shows no P0/P1 finding open.
9. Determinism test passes.
10. Ablation table published; every component justified or deleted.
11. No fabricated number anywhere; `reports/` artifacts exist for every quoted figure.
12. `FINAL_STATUS.md` lists zero open P0/P1 defects and an honest limitations section.

## 14. Data-honesty policy (binding, P0)

1. All data is synthetic. **No real ISRO data is used.**
2. Every dataset row, API response, UI surface, export, and slide carries a `SYNTHETIC` marker.
3. The marker cannot be disabled by configuration or interaction.
4. No claim is made that any value matches a real device, lot, process or mission.
5. What we *do* claim: the dataset reproduces the **structural phenomena** the problem statement
   describes, from a documented and seeded model.
6. If asked "is this real ISRO data?", the answer is a plain "no, it is synthetic, and here is the
   generator specification" — said before being asked, on the dataset slide.

Violating any of these is a **P0 release blocker** and, in the judging context, an integrity
failure. This clause outranks every other consideration in this document.

## 15. Known limitations (maintained honestly, expanded as we learn)

| ID | Limitation | Why we accept it |
|----|------------|------------------|
| KL-01 | Validated only on synthetic data | No public real dataset exists (`research/DATASET_RESEARCH.md § 1`); real validation is a named next step requiring an ISRO data-sharing arrangement |
| KL-02 | Conformal validity requires exchangeability | Detected and declared by the exchangeability guard rather than assumed |
| KL-03 | Two input read-points bound what is identifiable | Stated explicitly; a third early read-point would allow per-part curvature and is listed in Future Scope |
| KL-04 | `Ea`, delta limits, and PDA defaults are configuration, not device truth | Exposed, documented, and swept in sensitivity analysis |
| KL-05 | No authentication in the demo build | SR-09; scoped as a single-operator local tool |
| KL-06 | Socket/zone attribution presumes position metadata is recorded | Precondition documented (`DQ-04`); degrades to part-only analysis when absent |
| KL-07 | No physical failure analysis; the system infers from parametrics only | Out of scope by design; output is a *recommendation* for FA, not a substitute |
| KL-08 | Small lots (`n < 20`) have materially reduced statistical power | Guarded, warned in UI, never silently absorbed |



