# RISK_SCORING_SPEC.md — Decomposable Risk, and the Case Against a Single Number

**Owner:** Data + ML Engineer · Implements FR-401..FR-405 · Grounded in D-I-01, R18

## 1. The design decision, stated first

Almost every hackathon submission in this space produces **one AI risk score, 0–100**, and makes it
the hero of the UI. We deliberately do not (R18 REJECT).

Reason: a single opaque score is exactly the artifact a QA inspector cannot act on, cannot audit, and
cannot defend in a Failure Review Board. Asked *"why 87?"*, a black-box score has no answer. Asked
*"what would make it 60?"*, it has no answer either. And the SIH criterion is explicitly
explainability to an inspector.

So risk in LATENTIS is a **decomposition with an exact adding-up property**, not a verdict:

```
risk_total = w_A · risk_anomaly
           + w_B · risk_drift
           + w_M · risk_margin
           + w_Q · risk_quality
           − w_C · credit_attribution           # setup-attributable evidence REDUCES part risk
```

with `Σ|w| = 1` and the constraint, asserted in code and in `TEST-RISK-001`, that the printed
components sum to the printed total within `1e-9`. If they ever do not, the response is a `5xx`, not
a rounded number.

The score exists to **order a worklist**, and it says so in the UI subtitle. The *decision* is the
band (`SAFE`/`WATCH`/`EARLY_WARNING`/`REJECT`) plus the two independent verdicts (PAT and absolute),
never the score.

## 2. Components

Each component is in `[0, 1]`, is computed from a `TracedValue`, and has a stated monotone direction.

### 2.1 `risk_anomaly` — lot-relative abnormality now (Module A)

```
risk_anomaly = clamp01( (|z_primary| − z_ref_low) / (z_ref_high − z_ref_low) )
```

`z_primary` is the primary robust distance (DPAT-z, or MAD-z when `n < 20`). `z_ref_low = 3` and
`z_ref_high = 6` are the **AEC-Q001-anchored** band edges from `ANOMALY_SPEC § 5`, so the mapping is
`ELEVATED → 0` and `SEVERE → 1`, and the two numbers in it are inherited from a standard rather than
chosen by us. Both are profile config.

### 2.2 `risk_drift` — predicted trajectory (Module B)

```
risk_drift = clamp01( slope_ratio / slope_ratio_ref )        # slope_ratio_ref default 2.0
```

`slope_ratio = predicted_long_slope / safety_slope` from `DRIFT_SPEC § 6.3`. At `slope_ratio = 1`
(the safety criterion exactly met) this is 0.5, which is the intended reading: the criterion boundary
sits in the middle of the component, not at its ceiling, so parts that exceed it by a lot are
distinguishable from parts that just touch it.

### 2.3 `risk_margin` — how little room is left at the bound

```
risk_margin = clamp01( 1 − predicted_margin_pct )
```

Uses `Û168`, so it inherits the conformal conservatism. This component is what separates two parts
with identical slopes but different distances to their limits — the thing a slope-only view misses.

### 2.4 `risk_quality` — evidential weakness, not part badness

```
risk_quality = 1 − data_quality_score
```

Driven by missing read-points, censored readings, small cohort (`n < 20`), `NO_VARIATION` cohorts,
duplicate rows and unit-validation warnings. Semantically distinct from the others: it raises
*"look at this, we are not confident"*, not *"this part is bad"*. The UI must render it in a different
visual channel for that reason (`UX_SPEC`), and the narrative wording differs: **"weak evidence"**,
never **"risky part"**.

### 2.5 `credit_attribution` — the term that *subtracts*

```
credit_attribution = 1  if attribution ∈ {SOCKET, TESTER}
                     0.5 if attribution == ZONE and the zone offset explains the anomaly via AF
                     0    if attribution ∈ {PART, INDETERMINATE}
```

This is the component we are most pleased with. When the evidence says the *setup* produced the
signal, total risk **goes down** and the recommendation becomes `RETEST_DIFFERENT_SOCKET`, not
`REJECT`. A screening tool that can only escalate is a tool that erodes trust and inflates scrap.
`ANOMALY_SPEC § 7` supplies the verdict; `DATASET_SPEC § 6` supplies `sensor_noise_anomaly` and
`S4-decoy-sensor` parts specifically so this path is **measured**, not merely claimed.

## 3. Weights — configuration with published provenance

| Weight | Default | Provenance |
|---|---|---|
| `w_A` (anomaly) | 0.30 | `assumed` — Module A is the primary escape detector |
| `w_B` (drift) | 0.30 | `assumed` — symmetric with Module A; the two mandated modules rank equally |
| `w_M` (margin) | 0.20 | `assumed` |
| `w_Q` (quality) | 0.10 | `assumed` — evidential, deliberately the smallest |
| `w_C` (credit) | 0.10 | `assumed` — bounded so attribution can never zero out a `SEVERE` part |

These are **policy inputs, not discovered truths**, and the UI labels them so. Three consequences we
accept and publish:

1. Weights live in the `ScreeningProfile`, are editable, and are versioned with it. Changing them
   changes the ordering of the worklist, which is the honest scope of their power.
2. `reports/SENSITIVITY.md` includes **rank correlation of the worklist under weight perturbation**
   (Spearman ρ across ±50 % jitter, 200 draws). If the ordering is fragile, that is a finding we
   report, not one we hide.
3. Weights **cannot** move a part across a band boundary. Bands come from `DRIFT_SPEC § 6.3` and the
   absolute-limit verdict; the score never overrides them. This is the structural protection against
   "tune the weights until the demo looks good" (AG-6).

## 4. What risk is *not* allowed to do

| Forbidden | Why |
|---|---|
| Override an `ABSOLUTE_FAIL` | A part outside an absolute limit is a hard fail (FR-210), full stop |
| Move a part between bands | Bands are derived from limits and the conformal bound, not from weights |
| Be presented without its decomposition | INV-1/XR: a number without its arithmetic is not shippable |
| Be described as a probability | It is an ordering index. Calling it a probability of failure would be a fabricated calibration claim we have not measured |
| Depend on `component_id`, row order, or lot position in the file | INV-2, `RT-004` |

That fourth row is a real trap: `risk_total = 0.87` invites the phrase *"87 % chance of failure"*. The
API field is named `risk_index`, the UI label is **"Risk index (worklist ordering)"**, and
`docs/GLOSSARY.md` binds the term. No component of the system is permitted to render it as a
percentage.

## 5. Lot-level roll-up and PDA (FR-406)

Per-part risk aggregates to a lot disposition through the **PDA** rule, which is the actual
standards-based lot criterion (D-A-03) — not an average of part scores.

```
n_reject      = |{parts with band == REJECT or verdict == ABSOLUTE_FAIL}|
pda_pct       = 100 · n_reject / n_parts_tested
lot_verdict   = FAIL_LOT   if pda_pct > pda_limit_pct          # profile default 5.0
                REVIEW     if pda_pct in (0.8·pda_limit, pda_limit]
                PASS_LOT   otherwise
```

Reported with the exact counts, the limit used, and its profile provenance, plus a **second, clearly
separated** figure: `pda_pct_including_early_warning`, which shows what the lot would look like if
`EARLY_WARNING` parts were also rejected. Two numbers, both labelled, because that is the decision the
engineering manager (P4) actually has to make, and presenting only one of them would be steering them.

`S5-lot-shift` lots exist in the dataset to prove the roll-up does **not** fail a coherently shifted
lot — DPAT absorbs the shift, so `n_reject` stays low, where a static-limit or SPAT screen would
condemn the whole lot (D-CD-02).

## 6. Recommendation mapping (FR-407) — the system recommends, the human disposes

| Recommendation | Condition |
|---|---|
| `REJECT` | `ABSOLUTE_FAIL`, or band `REJECT` with attribution `PART` |
| `RETEST_DIFFERENT_SOCKET` | Attribution `SOCKET` or `TESTER`, any severity |
| `EXTEND_BURN_IN` | Band `EARLY_WARNING` and `predicted_margin_pct > 0` — the part is drifting fast but has room; more oven time resolves the ambiguity with evidence instead of a guess |
| `INVESTIGATE` | `SEVERE` anomaly with band `SAFE`, or the two modules disagreeing — a genuine conflict, reported as a conflict |
| `ZONAL_REVIEW` | Attribution `ZONE` with a coherent Arrhenius-consistent offset |
| `ACCEPT` | Band `SAFE`, severity `NOMINAL`, quality good |
| `INSUFFICIENT_DATA` | Any required decision input missing |

Every recommendation carries its triggering condition as text and the `TracedValue`s that satisfied
it. The inspector then records `CONCUR`, `OVERRIDE` (reason mandatory), or `DEFER` (D-I-02), and the
system stores the payload it showed at that moment (`ARCHITECTURE § 8`).

`INVESTIGATE` deserves note: when Module A and Module B disagree, we surface the disagreement rather
than averaging it away (`ARCHITECTURE § 9`). An averaged verdict would be the more confident-looking
product and the less trustworthy one.

## 7. Output contract

```json
{
  "risk_index": {"value": 0.612, "unit": "index", "formula_id": "risk.total_v1",
                 "display_precision": 3},
  "components": [
    {"name": "anomaly",  "weight": 0.30, "raw": 0.94, "weighted": 0.282, "formula_id": "risk.anomaly_v1"},
    {"name": "drift",    "weight": 0.30, "raw": 0.66, "weighted": 0.198, "formula_id": "risk.drift_v1"},
    {"name": "margin",   "weight": 0.20, "raw": 0.73, "weighted": 0.146, "formula_id": "risk.margin_v1"},
    {"name": "quality",  "weight": 0.10, "raw": 0.14, "weighted": 0.014, "formula_id": "risk.quality_v1"},
    {"name": "attribution_credit", "weight": -0.10, "raw": 0.28, "weighted": -0.028,
     "formula_id": "risk.credit_v1"}
  ],
  "sum_check": {"components_sum": 0.612, "reported_total": 0.612, "abs_diff": 0.0, "tolerance": 1e-9},
  "recommendation": {"action": "EXTEND_BURN_IN",
                     "trigger": "band == EARLY_WARNING and predicted_margin_pct > 0",
                     "ordinal_note": "risk_index orders the worklist; it does not decide the band"},
  "lot_context": {"pda_pct": 3.2, "pda_limit_pct": 5.0, "lot_verdict": "PASS_LOT",
                  "pda_pct_including_early_warning": 6.1},
  "profile_id": "mil_std_883_like@2", "model_versions": {"anomaly": "1.0.0", "drift": "1.0.0"}
}
```

`sum_check` ships in the payload on purpose. It is a two-line field that lets any auditor — human or
`RT-007` — verify the decomposition without trusting us, and it is the cheapest possible proof that
the number was computed rather than chosen.
