LATENTIS

Final Prototype Blueprint

AI-Driven Anomaly Detection in Component Burn-In & Screening
SIH26170 • Indian Space Research Organisation (ISRO)

## 1. Executive Summary

SIH26170 asks for an AI-driven screening system for high-reliability electronic components undergoing burn-in/ESS. The central problem is that an absolute pass/fail limit can miss a component that is technically inside the datasheet limit but behaves abnormally compared with its lot, or is drifting toward an unsafe future state.

LATENTIS expands the two required modules into an engineer-facing command center. It does not replace the engineer. It produces evidence, uncertainty, recommendation and a complete calculation trail so an engineer can accept, investigate or reject a component or lot.

## 2. What Our Problem Statement (PS) Is

PS: SIH26170 — AI-Driven Anomaly Detection in Component Burn-In & Screening. Organization: Indian Space Research Organisation (ISRO), Department of Space. Category: Software. Theme: Smart Automation.

In plain English: space-grade electronics are stressed during burn-in/ESS so weak parts can be found before they become mission failures. Traditional screening asks whether a measurement crossed an absolute limit. The PS asks for a smarter system that also asks whether the component is abnormal relative to its lot and whether its trajectory is likely to become unsafe later.

The PS does not provide a participant-accessible dataset. The core demo therefore uses reproducible controlled synthetic data. Any NASA/public electronics-aging data is treated only as external proxy/benchmark data, never as ISRO hardware validation.

## 3. Why This Problem Matters

Static limits catch obvious failures, but latent defects can remain below the absolute limit while being extreme relative to the lot.

A component can look acceptable now but have a trajectory becoming unsafe.

A bad sensor, socket, tester channel or chamber condition can create an apparent component anomaly.

A reliability engineer needs evidence, not a mysterious score.

Because missed defects are more dangerous here, evaluation must focus on escape detection and future safety, not generic accuracy.

Example:
Lot average leakage = 10 µA
Absolute maximum = 50 µA
Component = 45 µA

Absolute-limit result: PASS
Lot-relative result: STRONGLY ABNORMAL

## 4. What LATENTIS Does

## 5. Who Uses It

QA/reliability inspector: investigates flagged components and decides disposition.

Burn-in/test engineer: watches chamber/run health, sensor quality and emerging patterns.

Reliability engineer: reviews lot patterns, safety margins and model behaviour.

Judge/reviewer: follows a reproducible scenario and sees evidence rather than only a dashboard score.

Future integration owner: connects qualified real telemetry through a defined backend boundary.

## 6. How the Final Prototype Works: End-to-End

TELEMETRY / REPLAY
      ↓
DATA QUALITY
  missing / flatline / impossible / gaps
      ↓
SENSOR CONFIDENCE + CONDITION CONTEXT
      ↓
PEER / LOT BASELINE
      ↓
┌─────────────────────────────────────────────┐
│ LENS 1 — ANOMALY                            │
│ robust lot statistics + CUSUM               │
│ + optional Isolation Forest advisory        │
└─────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────┐
│ LENS 2 — DEGRADATION                        │
│ temporal drift + Shape–Amplitude            │
│ + optional LSTM-AE benchmark                │
└─────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────┐
│ LENS 3 — PROJECTED RISK                     │
│ 168 h forecast + conformal uncertainty      │
│ + safety margin / slope / risk decomposition│
└─────────────────────────────────────────────┘
      ↓
ATTRIBUTION + EXPLANATION + PROVENANCE
      ↓
RECOMMENDATION
      ↓
ENGINEER DECISION
      ↓
AUDIT / LOT DISPOSITION

The three lenses can disagree. 'Unusual now', 'drifting over time' and 'likely to become unsafe' are different engineering questions. A disagreement is information, not automatically an error.

## 7. The Three-Lens Intelligence Engine

### Lens 1 — Anomaly: Is it unusual right now?

The component is compared with an appropriate peer/lot population. Robust statistics reduce the influence of extreme values. CUSUM detects persistent shifts; Isolation Forest can add a multivariate advisory view.

Lot-relative robust z-score: distance from a robust peer centre.

MAD/IQR: robust measures of spread.

Mahalanobis D²: multivariate distance for unusual combinations.

CUSUM: accumulates small directional changes so persistent shifts become visible.

Isolation Forest: identifies unusual combinations; in LATENTIS it is advisory and cannot independently override the core verdict.

### Lens 2 — Degradation: Is it slowly drifting?

The system models how a measurement changes over burn-in. The existing scientific core uses Shape–Amplitude decomposition because two early observations identify the change amplitude while the chosen shape describes how the change evolves.

value_i(t) = v0_i + A_i · Φg(t)
Φg(24) = 1
A_i = v24_i − v0_i

The 168 h forecast is accompanied by a conformal upper bound. The safety decision reads the bound, not only the point forecast.

### Lens 3 — Projected Risk: Will the trajectory become unsafe?

The forecast is compared with the safety envelope and usable margin. The system derives safety slope, observed early slope, predicted long-horizon slope, slope ratio and decision bands. Risk is decomposed into interpretable terms.

## 8. Data: What Goes In

The current core dataset is controlled synthetic data with explicit ground truth, physical imperfections, decoys, lot-disjoint splits and reproducibility. Real qualified telemetry can later replace or augment it without changing the scientific core.

## 9. Data Quality and Sensor-Fault Protection

This is a major engineering distinction: the system must distinguish 'the part is bad' from 'the measurement environment is bad'.

## 10. Technical Terms, Simplified

## 11. The Audited Scientific Core We Already Have

## 12. Phase 4 — Intelligence & Benchmarking

Rule: models are added because they answer an engineering question or provide useful evidence, not because they sound impressive.

## 13. Phase 5 — Backend & Live Platform

## 14. Phase 6 — Frontend & Digital Twin

The UI is a QA/reliability instrument, not a generic analytics dashboard.

Verdicts visually unambiguous and never colour-only.

Synthetic data visibly labelled SYNTHETIC.

Uncertain/degraded states explicit.

Important metrics backed by TracedValue.

Charts have accessible table fallbacks.

Frontend displays backend decisions and does not recreate mathematics.

## 15. Phase 7 — Validation, Red-Team & Demo

Recommended 3-minute judge flow:

Select a burn-in scenario and show the lot overview.

Show a component that passes the absolute limit but is suspicious relative to its lot.

Open the investigation panel and show exact evidence/arithmetic.

Show the 168 h forecast, upper bound and safety margin.

Switch to the sensor-fault scenario and show that the component is not blindly condemned.

Open provenance and record the engineer's final disposition.

## 16. How the System Decides Without Becoming a Black Box

Observed value
   ↓
Peer-relative evidence
   ↓
Temporal evidence
   ↓
Future forecast
   ↓
Prediction bound
   ↓
Safety margin / slope
   ↓
Risk components
   ↓
Recommendation
   ↓
Engineer disposition

Detection asks whether the current observation is unusual.

Prediction asks where the trajectory is going.

Conformal calibration quantifies uncertainty under its assumptions.

Safety logic asks whether the future bound fits the allowed envelope.

Attribution asks whether the effect belongs to the component or setup.

Recommendation translates evidence into action.

The engineer remains responsible for the final disposition.

## 17. Provenance — The 'Nothing Is Fabricated' Layer

## 18. Full Stack — What We Use and Why

## 19. Final System Architecture

┌──────────────────────────────┐
                         │       ENGINEER / JUDGE       │
                         │ Next.js + React + R3F UI     │
                         └──────────────┬───────────────┘
                                        │ REST / WebSocket
                                        ▼
                         ┌──────────────────────────────┐
                         │            FASTAPI            │
                         │ scenario • investigation     │
                         │ operator decision • reports  │
                         └──────────────┬───────────────┘
                                        │
                         ┌──────────────▼───────────────┐
                         │        SERVICE LAYER          │
                         │ replay • provenance • store  │
                         └──────────────┬───────────────┘
                                        │
                         ┌──────────────▼───────────────┐
                         │       SCIENTIFIC CORE         │
                         │ robust • DPAT • D² • attrib. │
                         │ shape • forecast • conformal │
                         │ safety • risk • recommendation│
                         └──────────────┬───────────────┘
                                        │
                 ┌──────────────────────┼──────────────────────┐
                 ▼                      ▼                      ▼
        ┌────────────────┐    ┌──────────────────┐    ┌────────────────┐
        │ DATA / PARQUET │    │ PHASE-4 MODELS   │    │ PROVENANCE     │
        │ DuckDB / replay│    │ CUSUM / IF /     │    │ TracedValue /  │
        │ synthetic      │    │ LSTM-AE / XGB*   │    │ formula registry│
        └────────────────┘    └──────────────────┘    └────────────────┘

*Optional/future components never silently become decision authorities.

## 20. What the Final Prototype Contains

✓ A reproducible burn-in dataset/scenario system with visible SYNTHETIC labelling.

✓ Lot/component/chamber/socket/zone context.

✓ Data-quality checks and sensor-confidence state.

✓ Lot-relative anomaly detection using robust statistics / DPAT.

✓ Robust multivariate Mahalanobis D² evidence.

✓ Part/socket/zone/tester attribution.

✓ Temporal drift analysis using Shape–Amplitude.

✓ 168 h forecast and linear baseline.

✓ Conformal upper prediction bound and validity status.

✓ Safety margin, safety slope, observed/predicted slope and decision bands.

✓ Interpretable risk decomposition with consistency check.

✓ Recommendation engine and explicit human disposition.

✓ CUSUM persistent-shift detection.

✓ Isolation Forest as advisory benchmark if integrated.

✓ Sensor-fault scenario and handling.

✓ Minimal condition-aware normalization where feasible.

✓ FastAPI backend exposing the verified computation.

✓ WebSocket live scenario updates where useful.

✓ Next.js/React command center.

✓ Modest React Three Fiber digital twin.

✓ Component investigation screen.

✓ Why-flagged evidence/arithmetic panel.

✓ Forecast/safety panel.

✓ Model comparison panel.

✓ Engineer decision + append-only audit record.

✓ Provenance and formula registry surfaced in the UI.

✓ Five repeatable demonstration scenarios.

✓ Automated tests and red-team checks for the critical path.

✓ Offline/replay fallback so the demo does not depend on external services.

## 21. What the 25–30 Hour Prototype Does NOT Promise

Validation on real ISRO hardware.

Synthetic-data performance equal to field performance.

A mandatory DuckDB→TimescaleDB migration during the hackathon.

Kafka, Kubernetes or a distributed microservice platform.

LSTM-AE/XGBoost as authoritative just because they are complex.

Isolation Forest as a hidden verdict override.

Risk_index being a probability without a valid probabilistic interpretation.

Browser-side invention of missing values or safety decisions.

Autonomous flight-hardware release authority.

Generic '100% accurate' claims.

## 22. 25–30 Hour Build Order

## 23. The Final Demo Story

1. A component is technically within the absolute limit.
2. LATENTIS compares it with its peer lot.
3. It is unusually high relative to the lot.
4. Temporal evidence shows a concerning trajectory.
5. The 168 h prediction has a calibrated upper bound.
6. Safety margin/slope shows whether the future is acceptable.
7. The system explains the evidence.
8. A sensor-fault scenario shows measurement problems are not blindly blamed on hardware.
9. The engineer sees the recommendation and makes the final decision.
10. Provenance shows how every important number was produced.

Product in one sentence: Find what a fixed threshold misses, explain why, show what happens next, and keep the engineer in control.

## 24. How We Prove It Works

## 25. Known Limitations and Honest Claims

Core data is synthetic; real-silicon generalization remains unknown.

NASA/public electronics data, if used, are proxy benchmarks, not ISRO validation.

Shape–Amplitude drift shape is a modelling assumption, not a universal physical law.

Conformal coverage depends on assumptions; a guard can flag threats but cannot restore a guarantee.

Some risk weights/thresholds are project assumptions unless independently validated.

The hackathon prototype is decision support, not an autonomous release authority.

Capabilities must be labelled Implemented, Verified, Measured or Target rather than pretending everything is finished.

## 26. What Comes After the Hackathon

Replace/augment synthetic data with qualified historical burn-in data.

Calibrate sensor-fault rules with real test-system failure modes.

Benchmark the three lenses on real component/run-disjoint data.

Validate uncertainty coverage and risk thresholds on domain-specific calibration sets.

Introduce PostgreSQL/TimescaleDB if operational scale requires it.

Add authenticated real telemetry gateways.

Increase digital-twin fidelity only where it improves operator understanding.

Perform formal reliability/qualification review before operational use.

## 27. Source Basis

SIH26170 problem statement: AI-Driven Anomaly Detection in Component Burn-In & Screening, ISRO.

LATENTIS project master specification and architecture documents.

LATENTIS data generation/dataset and model specifications.

LATENTIS explainability, provenance, API and UX specifications.

LATENTIS Phase 3 implementation and independent Tester/Red-Team records.

Merged AI Context / Burn-In Intelligence Platform document.

Merged Problem Overview describing the three-lens workflow, simulator, proxy-data strategy and product stack.

Current PS reference: https://sih2026.vuce.in/ps/SIH26170

The current public listing exposes the PS but does not provide a participant-accessible dataset link. The prototype therefore visibly labels synthetic data and treats public external data as proxy evidence only.

## 28. One-Page Mental Model

1. CAN I TRUST THE MEASUREMENT?
   → Data quality + sensor confidence

2. IS THIS PART WEIRD COMPARED WITH ITS PEERS?
   → DPAT + robust statistics + D² + CUSUM

3. IS IT GETTING WORSE?
   → Temporal drift + Shape–Amplitude + optional LSTM-AE

4. WHERE WILL IT BE AT 168 HOURS?
   → Forecast + conformal upper bound

5. DOES THAT FUTURE STATE LOOK SAFE?
   → Safety margin + slope + risk decomposition

6. WHAT SHOULD THE ENGINEER DO, AND CAN WE PROVE WHY?
   → Recommendation + TracedValue + provenance + human decision

## 29. Final Prototype Definition

The final 25–30 hour prototype is complete when a judge can load a reproducible burn-in scenario, watch or replay telemetry, see a component that a static threshold would miss, understand the lot-relative and temporal evidence, inspect the 168-hour uncertainty-aware forecast, see safety margin and risk decomposition, distinguish a sensor fault from a component fault, review the recommendation, make the human decision, and trace important numbers back to their inputs and formulas.

Everything else is an extension. The architecture is intentionally designed so additional models, real telemetry, richer storage and a more advanced digital twin can be added later without rewriting the audited scientific core.



| One-sentence product definition LATENTIS turns burn-in telemetry into explainable early-warning intelligence: it compares a component with its peer lot, detects unusual behaviour and persistent drift, projects future safety risk with uncertainty, separates sensor problems from component problems, and gives the engineer traceable evidence for the final disposition. |

| --- |



| Prototype status This document describes the final 25–30 hour hackathon prototype target. Phase 3 is already the audited scientific foundation. Phase 4–7 items are the integration target and are deliberately prioritized for a working end-to-end demonstration rather than production deployment. |

| --- |



| Differentiator The product chain is: data quality → sensor confidence → peer/lot comparison → temporal drift → future projection → uncertainty → safety margin → risk decomposition → explanation → engineer decision → provenance/audit. |

| --- |



| PS requirement | Plain meaning | LATENTIS response |

| --- | --- | --- |

| Module A: dynamic outlier detection | Catch a part that looks abnormal relative to peers even if it passes the absolute limit. | DPAT/lot-relative robust statistics, multivariate D², attribution, plus CUSUM/Isolation Forest extensions. |

| Module B: drift predictor | Use early measurements to estimate the 168 h value. | Shape–Amplitude forecast + conformal upper bound; optional ML benchmarks. |

| False negatives are costly | Missing a bad part is worse than raising a review flag. | False-negative-focused thresholding and latent-escape evaluation. |

| Explainability | An inspector must understand why a flag happened. | TracedValue, formula registry, arithmetic/evidence panel, uncertainty and provenance. |

| Time-series data | Measurements arrive across burn-in time. | 0 h/24 h early measurements with 168 h projection and scenario replay. |



| User need | What LATENTIS shows |

| --- | --- |

| Monitor a burn-in lot | Lot status, component states, chamber/run context, telemetry and alerts. |

| Find suspicious parts | Ranked components with anomaly, drift, risk and evidence states. |

| Understand why | Peer deviation, robust statistics, multivariate contribution, temporal evidence and model contribution where applicable. |

| Know what happens next | Projected 168 h value/bound, safety margin, slope comparison and uncertainty. |

| Separate sensor vs component problems | Data-quality and sensor-confidence state can prevent unsafe component conclusions. |

| Make the final call | Engineer disposition: accept / investigate / reject, with append-only audit record. |

| Prove what happened | Dataset hash, model/profile version, formula/version, inputs and Git SHA attached to decision-bearing values. |



| Model rule LSTM-AE and XGBoost can be benchmarked if time permits. They do not automatically replace the audited core just because they are more complex. |

| --- |



| Field | Meaning |

| --- | --- |

| lot_id | Peer group / production or test lot. |

| component_id | Unique component under investigation. |

| parameter | Measured quantity such as leakage/current/Iddq. |

| time_h | Burn-in time such as 0, 24, 96, 168 h. |

| value | Measured parameter value. |

| temperature | Thermal condition. |

| voltage/load | Electrical operating context. |

| chamber / zone / socket / tester | Physical/test setup context. |

| component_type | Part family/type. |

| scenario_id | Reproducible scenario identifier. |

| sensor_status | Measurement quality/confidence state. |



| Problem | Example | Response |

| --- | --- | --- |

| Missing data | No expected reading. | Degraded / insufficient evidence. |

| Flatline | Sensor stuck at one value. | Sensor concern, not automatic component failure. |

| Impossible/non-finite value | Invalid measurement. | Exclude from decision arithmetic. |

| Timestamp gap | Unexpected time jump. | Reduce confidence / flag data quality. |

| Abrupt discontinuity | Single inconsistent jump. | Investigate channel before blaming component. |

| Socket/chamber shift | Many parts in one location move together. | Attribution can credit setup effect. |



| Term | Simple explanation |

| --- | --- |

| ESS | Environmental Stress Screening: testing hardware under controlled stress to expose weak parts. |

| Burn-in | Operating components under elevated stress for a period so early-life weaknesses can reveal themselves. |

| Telemetry | Measurements produced by the test system over time. |

| Lot | A group of components treated as a peer population. |

| Latent defect | A defect not obvious under a simple pass/fail limit but showing suspicious behaviour or later deterioration. |

| Static threshold | A fixed absolute limit, e.g. below 50 µA. |

| Dynamic/lot-relative threshold | A decision based on peer behaviour, not only an absolute limit. |

| DPAT | Dynamic Parametric Analysis Technique: lot-relative analysis for unusual component measurements. |

| Robust statistics | Statistics designed to stay useful despite extreme observations. |

| Median | Middle value after sorting. |

| MAD | Median Absolute Deviation: robust spread around the median. |

| IQR | Interquartile Range: distance between the 25th and 75th percentiles. |

| Robust z-score | Normalized measure of how unusual a value is. |

| Mahalanobis D² | Multivariate distance measuring how unusual a combination of measurements is. |

| Attribution | Determining whether an effect belongs to the component, socket, zone, tester or chamber. |

| CUSUM | Cumulative Sum method for detecting persistent small shifts. |

| Isolation Forest | Tree-based multivariate anomaly detector. |

| LSTM | Sequence neural-network architecture for time-dependent data. |

| LSTM Autoencoder | LSTM trained to reconstruct normal sequences; high reconstruction error can indicate unusual temporal behaviour. |

| XGBoost | Gradient-boosted tree model for nonlinear prediction. |

| Quantile regression | Predicting a percentile/range rather than only an average. |

| Shape–Amplitude model | Separates how much a part changed from how that change evolves. |

| Conformal prediction | Calibration method that turns a forecast into an uncertainty bound under its assumptions. |

| Prediction bound | Conservative future estimate used in a safety decision. |

| Exchangeability | Assumption that calibration and future data are sufficiently comparable. |

| Neyman–Pearson | Decision framework that prioritizes control of false negatives/false positives under a specified trade-off. |

| False negative | Bad component incorrectly treated as safe. |

| False positive | Good component incorrectly flagged. |

| Latent Escape Recall | How well subtle defects that pass hard limits are caught. |

| MAE | Mean Absolute Error: average absolute prediction error. |

| Risk decomposition | Breaking total risk into understandable contributing terms. |

| TracedValue | Decision-bearing numeric object carrying value, units, inputs and provenance. |

| Formula Registry | Versioned location for important calculations and their executable implementations. |

| Provenance | History of where a result came from and how it was calculated. |

| Scenario ID | Stable identifier for deterministic replay. |

| Digital twin | Visual software representation of the chamber/components and their analytical state. |

| API | Controlled interface between frontend and backend. |

| WebSocket | Live two-way connection used to push changing state to the browser. |

| MQTT | Lightweight publish/subscribe telemetry protocol. |

| Redis | Fast in-memory service for cache/pub-sub when needed. |

| TimescaleDB | PostgreSQL extension optimized for time-series data. |



| Capability | What it does | Prototype role |

| --- | --- | --- |

| Robust statistics | Median, IQR, MAD and robust fences. | Stable peer comparison. |

| DPAT / robust z | Lot-relative anomaly evidence. | Primary Module A evidence. |

| MinCovDet / D² | Robust multivariate distance. | Joint anomaly detection/decomposition. |

| Part/socket/zone/tester attribution | Separates component effects from setup effects. | Prevents false component blame. |

| Shape–Amplitude | Models temporal change from early readings. | Primary Module B forecast family. |

| 168 h forecast | Forecast plus linear baseline. | Future trajectory. |

| Split conformal / Mondrian | Calibrates upper prediction bound. | Uncertainty-aware decision. |

| Exchangeability guard | Checks threats to calibration comparability. | Validity warning/void status. |

| Safety criterion | Margin, slope, ratio and bands. | Turns forecast into engineering risk. |

| Risk decomposition | Interpretable terms + sum check. | Explains why risk is high. |

| Recommendation | Maps evidence to action. | Decision support. |

| Formula registry | Executable formulas + expressions. | Prevents explanation/computation drift. |

| TracedValue | Value + unit + provenance. | Single source of decision-bearing numbers. |

| Architecture isolation | Core independent from API/UI/data plumbing. | Protects scientific correctness. |



| Phase 3 state The project record reports independent Tester and MiMo red-team clearance for T-311→T-316 and authorization for Phase 4. Phase 3 should therefore be treated as the frozen scientific foundation. |

| --- |



| Feature | Purpose | Priority | Authority |

| --- | --- | --- | --- |

| CUSUM | Persistent small-shift detection. | MUST | Evidence/advisory. |

| Sensor-fault rules | Protect against bad measurements. | MUST | Can degrade/block component conclusion. |

| Condition-aware normalization | Account for temperature, voltage/load, stage and context. | SHOULD | Preprocessing/evidence. |

| Isolation Forest | Multivariate anomaly benchmark. | SHOULD | Advisory only. |

| LSTM-AE | Temporal reconstruction benchmark. | OPTIONAL | Benchmark unless validated. |

| XGBoost Quantile | Nonlinear future-risk benchmark. | OPTIONAL | Benchmark unless validated. |

| Model comparison | Compare methods on same scenarios. | SHOULD | Comparison only. |

| NASA proxy replay | External realistic-data benchmark. | OPTIONAL | Proxy only, not ISRO validation. |



| Layer | Prototype choice | Why |

| --- | --- | --- |

| Python | Python 3.11+ | Matches the scientific core. |

| Scientific core | Python/NumPy/SciPy/scikit-learn where appropriate | Testable and framework-independent. |

| API | FastAPI + Pydantic | Typed boundary between core and browser. |

| Storage | DuckDB + Parquet | Keep the existing reproducible analytical path; avoid risky migration. |

| Live updates | WebSocket where useful | Push scenario/telemetry state. |

| Telemetry adapter | MQTT optional | Realistic live/replay path if stable. |

| Redis | Optional | Only if the demo actually needs pub/sub/cache. |

| TimescaleDB | Future production adapter | Good time-series store, but not a 25–30 h requirement. |

| Reporting | Self-contained PDF/report | Preserve evidence offline. |



| Architecture rule The browser never performs decision arithmetic. The backend is authoritative. Scientific computation stays in backend/core and is not duplicated in routes or UI. |

| --- |



| Surface | What the user sees |

| --- | --- |

| 1. Command Center / Lot Overview | Run, lot status, flags, risk summary and chamber state. |

| 2. Chamber / Digital Twin | Simple 3D/visual chamber with components, zones and state. |

| 3. Component Investigation | Selected component readings, peers, drift and forecast. |

| 4. Why Flagged? | Plain-language explanation tied to runtime evidence. |

| 5. Forecast & Safety | 168 h forecast, upper bound, limit, margin and slope. |

| 6. Model Comparison | DPAT/CUSUM/IF/LSTM-AE/XGBoost results when available. |

| 7. Data Quality / Sensor Health | Missingness, flatline, discontinuity, confidence and attribution. |

| 8. Engineer Decision & Audit | Recommendation, human disposition, reason, timestamp and provenance. |



| Scenario | What happens | Lesson |

| --- | --- | --- |

| A. Latent drift / threshold trap | Part stays under absolute limit but is extreme relative to peers and/or drifts. | Static limits can miss latent defects. |

| B. Future drift | Early readings look acceptable but projected 168 h bound becomes unsafe. | Act before failure. |

| C. Sensor fault | Channel becomes suspicious while component evidence is weak. | Bad data is not automatically bad hardware. |

| D. Healthy component | Normal part remains within peer/safety behaviour. | System does not flag everything. |

| E. Model comparison | Methods evaluated on the same scenario. | Model choice is evidence-driven. |



| Provenance item | Why |

| --- | --- |

| Input values | Exact measurements used. |

| Units | Prevents silent unit mistakes. |

| Formula/model version | Shows the calculation/model used. |

| Dataset hash/version | Identifies the input data. |

| Profile/configuration | Shows active limits and assumptions. |

| Git SHA | Identifies exact software state. |

| Request/computation ID | Connects UI result to backend computation. |

| Validity status | Makes degraded calibration explicit. |

| Scenario ID | Allows deterministic replay. |

| Engineer disposition | Separates human decision from AI recommendation. |



| TracedValue A TracedValue is a number that refuses to travel alone. It carries the evidence needed to understand and reproduce what that number means. |

| --- |



| Layer | Technology | Job |

| --- | --- | --- |

| Frontend | Next.js + React + TypeScript | Command-center UI and operator workflow. |

| 3D layer | React Three Fiber | Modest digital-twin representation. |

| Client data | TanStack Query / TanStack Table where used | Fetching and table/evidence presentation. |

| Backend | FastAPI + Pydantic | Typed REST API and operator endpoints. |

| Live | WebSockets | Push changing telemetry/state. |

| Telemetry | MQTT optional | Publish/subscribe for simulated/future live data. |

| Cache/pub-sub | Redis optional | Only when needed. |

| Hackathon storage | DuckDB + Parquet | Local analytical storage and replay artifacts. |

| Future storage | PostgreSQL + TimescaleDB | Long-running time-series deployment option. |

| Scientific Python | NumPy / SciPy / scikit-learn | Core statistics and benchmark models. |

| Deep-learning benchmark | PyTorch | LSTM-AE if time/evidence justify it. |

| Tree benchmark | XGBoost + SHAP | Optional nonlinear benchmark + explanation. |

| Testing | pytest + Hypothesis + E2E/browser tests | Known-answer, property, behavioral, differential and adversarial checks. |

| Reporting | Self-contained PDF/report | Offline evidence. |

| Versioning | Git | Reproducible checkpoints and audit trail. |



| Time | Build | Exit condition |

| --- | --- | --- |

| 0–2 h | Lock Phase 3 and prototype scope. | No redesign of audited core. |

| 2–6 h | CUSUM + sensor quality/fault path. | One scenario distinguishes persistent shift vs sensor issue. |

| 6–9 h | FastAPI integration. | One investigation returns fully traced values. |

| 9–15 h | Frontend + lot view + component drilldown. | End-to-end browser path works. |

| 15–18 h | Latent-drift + sensor-fault scenarios. | Two judge-visible scenarios work. |

| 18–21 h | Isolation Forest/model comparison/live state if stable. | Extra intelligence adds evidence, not instability. |

| 21–25 h | Independent tests, red-team attacks, fixes. | Critical path survives. |

| 25–28 h | Demo polish + provenance click-through. | 3-minute demo repeatable. |

| 28–30 h | Buffer. | Do not spend early; bugs are fond of deadlines. |



| Metric/check | What it proves |

| --- | --- |

| Latent Escape Recall | Catches subtle defects that pass simple limits. |

| False-negative-focused evaluation | Controls the dangerous error of letting bad parts escape. |

| MAE for 168 h prediction | Measures forecast error against actual 168 h values. |

| Early-Warning Lead Time | Measures how early a flag appears before a safety breach. |

| Lot-level disposition | Aggregates component findings into a defensible lot status. |

| Sensor-fault robustness | Avoids converting measurement failures into component failures. |

| Lot-size robustness | Checks behaviour with smaller peer groups. |

| Reproducibility | Same scenario/data/version gives the same result. |

| Provenance completeness | A reviewer can trace a number to its source/calculation. |

| Red-team tests | Adversarial inputs cannot quietly bypass decision rules. |



| Final product identity LATENTIS is an explainable burn-in intelligence and reliability screening platform. It is not a black-box predictor, not an autonomous flight-hardware release system, and not merely a dashboard. |

| --- |
