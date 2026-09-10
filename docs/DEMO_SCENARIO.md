# DEMO_SCENARIO.md — The Live Demonstration, Scripted

**Owner:** Lead Orchestrator + Frontend Engineer · Implements DMR-01..DMR-08, JR-01..JR-07
**Constraint:** the demo runs **offline**, from a clean checkout, on a machine we may not control.

## 1. The one thing the demo must prove

> **A part that passes every absolute limit is caught, and we can show exactly why, from the arithmetic
> up, in the operator's own vocabulary.**

Everything else — the UI, the charts, the reports — is in service of that sentence. If we get 90 seconds
instead of 8 minutes, we show Act II and nothing else.

## 2. Pre-flight (before the room)

| Check | Command / action | Pass condition |
|---|---|---|
| Clean bootstrap | `scripts/bootstrap.sh` on a fresh clone | Completes offline, backend `:8000`, frontend `:5173` |
| Health | `GET /api/v1/health` | `status: ok`, all models `loaded: true`, `dirty: false` |
| Demo parts resolve | `scripts/select_demo_parts.py` | Writes `reports/DEMO_PARTS_<tag>.json` |
| Network off | Disable Wi-Fi **before** starting | Everything still works (NFR-08) |
| Projector | 1920×1080, light theme, Compact density | Contrast verified at distance |
| Backup | `reports/DEMO_RECORDING_<tag>.mp4` + the exported PDFs on local disk | Playable without network |

**The demo parts are selected by a script, not by hand.** `scripts/select_demo_parts.py` queries the
generated dataset for parts satisfying stated *predicates* — "an `S1` part with `dpat.verdict == FAIL`
and `absolute.verdict == PASS` and attribution `PART`" — and writes out whichever component IDs match.
This matters more than it looks: it means we are not showing a cherry-picked part we found by browsing,
and if the seed changes, the demo re-selects automatically. The predicates are in the script and are
readable by a judge. Nothing in the UI knows a demo part is a demo part (INV-2).

## 3. Act structure — 8 minutes

### Act I — The gap (60 s, one slide, no software)

State the problem in the audience's language, with the standard named:

> MIL-STD-883 Method 1015 exists to precipitate latent defects. The screen that follows it compares each
> reading to a fixed absolute limit. A part reading 45 µA against a 50 µA limit passes — even when its
> lot averages 10 µA. That part is an escape, and it is on the payload.

Then the framing that positions the whole submission:

> The industry already has an answer to the first half: AEC-Q001 **Dynamic Part Average Testing**. And
> military drawings already specify **delta limits** on parametric change. We implemented both, made the
> second one *predictive*, and measured what that buys.

No claim of novelty where none exists. This is the moment that separates us from submissions that invent
a heuristic and call it AI.

### Act II — Module A, the flagship (150 s)

1. **S1 Mission Control.** Point at the provenance header first: dataset hash, row count, `SYNTHETIC`
   badge, model versions. *"Everything you are about to see is computed from that dataset at that hash."*
2. **Escape spotlight** → click the top part.
3. **S3, verdict strip.** The moment: **`DYNAMIC PAT: ✗ FAIL`** beside **`ABSOLUTE LIMIT: ✓ PASS,
   9.6 % margin`**. Say plainly: *"Conventional screening ships this part. We do not."*
4. **The arithmetic panel** — already expanded, no clicking to reveal:
   `median 10.4 + 6 × (2.7 / 1.35) = 22.4 µA`, then `(45.2 − 10.4) / 2.0 = 17.4 σ`.
   *"`k = 6` and the 1.35 divisor are AEC-Q001's, not ours."*
5. **Click `2.7`** → ledger drawer → the IQR's own operands → the raw readings with their ingest rows.
   *"Any number here, all the way down to the file row it came from."*
6. **Cohort strip plot** — 187 siblings, DPAT limits drawn, this part alone on the right.
7. **Counterfactual** — *"This part flags at any `k` below 17.4. The configured value is 6. The verdict is
   not sensitive to that choice."*

Judge question we are inviting, and the prepared answer: *"Isn't 45 µA just a high-but-normal part?"* →
attribution panel: socket median offset 0.3 σ, zone median offset 0.2 σ ⇒ verdict `PART`, and the
`joint_only` Mahalanobis contribution table.

### Act III — Module B, the forecast (150 s)

1. **S4 Drift Studio** on the same part. Two observed points; nothing else is observed.
2. **The naïve dashed line** to 58.3 µA — *above* the 50 µA limit. *"Linear extrapolation from two points
   rejects this part."*
3. **The fitted line** to 32.3 µA, and the reason: `Φ_g(168) = 3.06` from a power law with `n = 0.58`,
   fitted on 26 training lots. *"Degradation is sub-linear. Linear extrapolation over-predicts, so it
   throws away good parts."*
4. **`GET /models/shape/...`** — show the fitted curve itself. *"That is the one number the forecast rests
   on. It is published, and you can dispute it."*
5. **The conformal band** to 39.8 µA. *"We reject on the upper bound, never the point estimate. Measured
   coverage for this group is 91.2 %, 95 % CI 87.9–93.8 %, on 388 held-out parts."*
6. **The safety slope**, read off the chart with its derivation
   `(50.0 − 12.1) × (1 − 0.20) / 168`. *"There is no universal constant for safe drift. This is derived
   from the profile, and the 20 % reserve is a policy input you can change."*
7. **Turn the Mission Risk Posture dial** from `α = 0.10` to `0.02`. The band widens; the part crosses
   into `EARLY_WARNING`. *"Fewer escapes, more false positives. That trade-off is yours, and it is
   visible."*

### Act IV — The system protects a good part (90 s)

Open the pre-selected `S4-decoy-sensor` part. Three members fire; the socket's median offset is 4.1 σ;
the part is *typical within its own socket*.

Verdict: **`SOCKET`**, recommendation **`RETEST_DIFFERENT_SOCKET`**, and `risk_index` goes **down**
because `credit_attribution` subtracts.

> *"A screening tool that can only escalate is a tool that inflates scrap and loses the operator's trust.
> This part is fine; the socket is not."*

This act is deliberate and it is the one most demos do not have. It is the strongest available evidence
that the system reasons rather than alarms.

### Act V — Evidence and honesty (90 s)

1. **S6 Model Info** — the ablation table as *data from a committed run*: absolute-limits-only at
   `LER = 0` by construction, DPAT-only, then each member's contribution, then full. *"Every component
   here earns its place in that table, or it is deleted. That is a written commitment: AG-10."*
2. **Coverage table** per group, with binomial intervals.
3. **The exchangeability guard.** Switch to the injected lot-shift lot: the banner fires,
   `guarantee_status: VOID`, the bound widens. *"The system tells you when its own guarantee does not
   hold. Most do not."*
4. **Export the PDF** and open it: same numbers, provenance appendix with every formula, synthetic-data
   banner on every page.
5. **Known limitations, stated by us first** (`FINAL_STATUS.md`): `intermittent` parts are unreliable from
   two read-points and we publish the measured number; the physics model is grounded in published
   standards, not validated against real devices; all data is synthetic.

Volunteering limitations before being asked is the single highest-leverage credibility move available,
and it costs 20 seconds.

## 4. Contingencies

| Failure | Response |
|---|---|
| Backend will not start | `scripts/bootstrap.sh --verbose`; if unresolved in 60 s, switch to the recording and narrate live |
| A model artifact is missing | Health shows `degraded` and names it; the UI disables those panels. **Show that** — a graceful degradation is a feature, and it is honest |
| Frontend crashes | API via HTTPie against the projector; the JSON *is* the evidence, and the arithmetic is in it |
| A judge asks for an unseeded/new dataset | `scripts/generate_demo_dataset.sh --seed <their number>` — takes ~90 s and is the strongest possible answer |
| A judge disputes the safety-slope derivation | S5 Screening Profile: change `margin_fraction` live, watch the band recompute server-side |
| Time cut to 2 minutes | Act II only, ending on the counterfactual sentence |
| Time cut to 30 seconds | The verdict strip. One sentence: *"passes the absolute limit, fails its own lot at 17.4 robust sigma, and here is the arithmetic."* |

## 5. Questions we expect, with the surface that answers them

| Question | Answer surface |
|---|---|
| "How do you fit a curve to two points?" | `DRIFT_SPEC § 2` + the fitted-shape endpoint. We do not: one baseline, one amplitude, shape borrowed from the population and published |
| "Isn't this just a z-score?" | Robust statistics vs. classical, and the ablation row where mean ± 3σ **masks** the outlier it should catch |
| "Where did `k = 6` come from?" | AEC-Q001 (D-CD-02), and the `k`-sensitivity counterfactual showing the verdict survives any `k < 17.4` |
| "What's your false-positive rate?" | `reports/METRICS_<tag>.json`, reported beside LER and flag rate — never LER alone |
| "Is this real ISRO data?" | No. Synthetic, labelled on every surface and every page. Here is the generator and its provenance tags |
| "What if the new lot is different?" | The exchangeability guard, demonstrated live in Act V |
| "Why no deep learning?" | `research/ML_METHOD_RESEARCH.md § 1.1`: 40 lots, 3 % prevalence, and an auditability requirement a neural net cannot meet. It would be a worse answer, not a more impressive one |
| "What can't it do?" | `FINAL_STATUS.md § Known Limitations`, with measured numbers |

## 6. Roles

| Role | Owner | Job |
|---|---|---|
| Narrator | Team lead | Acts I–V, keeps time, states limitations |
| Driver | Frontend engineer | Drives the UI; never explains — the narrator explains |
| Backstop | Backend engineer | Terminal ready, health endpoint up, contingencies |
| Domain answerer | Whoever knows the standards | Fields standards questions with document references |

Two people on the machine, one voice. A demo with two narrators loses the thread, and the thread is the
only thing carrying the argument.
