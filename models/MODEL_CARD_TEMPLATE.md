# MODEL_CARD_TEMPLATE.md — Required Card for Every Registered Artifact

**Owner:** Data + ML Engineer · Implements MLR-09, DR-08 · Gate: `QG-MODEL-01`

A model artifact may not be registered — and therefore may not be loaded by the API — unless
`models/registry/<name>/<semver>/card.md` exists and every section below is filled. Sections are not
optional and "N/A" requires a reason. `scripts/validate_model_card.py` parses the headings and fails
the build on a missing one.

Numbers in a card are **`Measured`** in the `CLAUDE.md § 4` sense: produced by a real run on real
generated data, reproducible from the recorded seed and config, with the artifact committed under
`reports/`. A card containing a number that is not traceable to such an artifact is a P0 defect.

---

## Template — copy from here

````markdown
# Model Card — <name> v<semver>

## 1. Identity
| Field | Value |
|---|---|
| Model name | `anomaly` \| `drift_shape` \| `drift_residual` \| `conformal` |
| Version | `<semver>` |
| Trained at | `<ISO-8601 UTC>` |
| Generator/dataset hash | `sha256:<...>` |
| Config hash | `sha256:<...>` |
| Code git SHA | `<40-hex>` |
| Library versions | numpy / scipy / scikit-learn / python, exact |
| Profile | `<profile_id>@<version>` |
| Data provenance | **SYNTHETIC** (always — INV-3) |

## 2. Intended use
- **Intended:** <the one decision this artifact supports, in one sentence>
- **Out of scope:** <uses this artifact must not be put to>
- **Not intended for:** flight-lot disposition without a qualified human; any real device population
  without re-fitting and re-validating on that population.

## 3. Inputs
Exact ordered feature list as it appears in the fitted object's schema. For Module B artifacts this
list is asserted equal to the `DRIFT_SPEC § 3` allow-list by `TEST-DL-001`.

| Feature | Unit | Source | Read-point |
|---|---|---|---|

Explicit statement: **no feature derived from 96 h or 168 h observations** (INV-4).

## 4. Method
- Family / estimator and its hyperparameters, all of them, as fitted.
- For `drift_shape`: the selected shape family, its fitted parameter, `Φ_g(168)` per group, the number
  of training lots per group, and the plotted curve (`reports/figures/shape_<group>.png`).
- For `conformal`: `α`, score function, Mondrian grouping, `n_cal` and the order statistic index per
  group.
- Selection procedure, and what it was selected *against* (out-of-sample MAE on training folds only).

## 5. Training data
| Field | Value |
|---|---|
| Split | `train` (lot-disjoint) |
| Lots / parts / rows | |
| Lot IDs | listed, or hash of the sorted list |
| Excluded | rows excluded and why (e.g. `status != OK`) |

Calibration and test lot IDs are recorded too, with the assertion that the three sets are disjoint.
`TEST-SPLIT-001` re-checks disjointness from the artifact, not from the training script.

## 6. Measured performance
Every row: mean ± std over the 5 configured seeds, with the source artifact path.

| Metric | Value | Source |
|---|---|---|

Required for `anomaly`: LER on the Escape Set, FPR, flag rate, AUPRC, partial AUROC @ FPR ≤ 0.1, F2,
per-stratum recall `S0`–`S5`, `joint_only` recall.
Required for `drift_*`: MAE / RMSE / MedAE per parameter in physical units, Tail MAE (top decile),
per-stratum MAE with `S2` broken out, bias (signed mean error).
Required for `conformal`: empirical coverage marginal and per group with Clopper–Pearson 95 % CIs,
mean and median width, Winkler score.

## 7. Baseline comparison
The card is **rejected** without this section. At minimum:

| Configuration | Headline metric | Δ vs. this artifact |
|---|---|---|
| Absolute limits only | `LER = 0` by construction | |
| Classical mean ± 3σ | | |
| DPAT only (`k = 6`) | | |
| Linear extrapolation (`Φ(168) = 7`) | | |
| **This artifact** | | |

## 8. Ablation
Link the row(s) of `reports/ABLATION_<tag>.md` that justify this artifact's existence. If the ablation
does not show the improvement this artifact exists to provide, the artifact is **deleted**, not
shipped with a caveat (AG-10). State explicitly which ablation row is the justification.

## 9. Limitations and failure modes
Concrete and specific. Generic risk boilerplate is a card failure. Cover at least:
- Where the model is weakest (which stratum, which parameter, which cohort size).
- Behaviour on `intermittent` parts, given two-point partial observability (KL-05).
- Small-cohort degradation and the `reduced_power` path.
- Distribution shift: the exchangeability guard, when it fires, and what the bound does then.
- Anything the model cannot see at all (per-part shape deviation — irreducible, `DATA_GENERATION_SPEC § 3`).

## 10. Fairness / bias analysis — reframed for this domain
There are no protected human attributes here, so this section is not omitted, it is **repointed** at
the systematic bias that matters: does performance differ across `component_type`, `thermal_zone`,
`socket_id`, `tester_id`, `lot` size, and `data_quality_score` band?

| Slice | n | Headline metric | Gap vs. best slice |
|---|---|---|---|

A slice performing materially worse is reported here and in `FINAL_STATUS.md`. Under-serving small
lots or hot zones is the exact analogue of a fairness failure in this setting: a systematically
under-screened subpopulation.

## 11. Explainability
- Which explanation method applies (Ridge coefficients with signs / exact TreeSHAP / exact
  Mahalanobis contribution decomposition / DPAT arithmetic).
- Confirmation that explanations are computed from the same values as the decision (INV-5, `RT-007`).
- The `formula_id`s this artifact emits, and their registry entries.

## 12. Reproduction
```bash
# exact command, no placeholders
python -m datagen.generate --config data/config/default.yaml --seed <seed>
python -m models.train --model <name> --config <path> --seed <seed>
sha256sum models/registry/<name>/<semver>/model.joblib   # expect: <hash>
```
State the verified fact: re-running the above on the recorded git SHA reproduces the artifact hash
(NFR-07, INV-8). If it does not, the card says so and the release is blocked.

## 13. Sign-off
| Role | Agent | Date | Statement |
|---|---|---|---|
| Author | data-ml-engineer | | Numbers are Measured, not Target |
| Auditor | red-team-auditor | | Card audited against `RT-*`; no unsupported claim found |
| Release | integration-release-engineer | | Registered in `models/registry/`; health endpoint reports it |
````

---

## Notes on using this template

**Section 7 is the one to keep honest.** A card with strong absolute numbers and no baseline
comparison tells a judge nothing — everything looks good without a reference point. The baseline rows
are where the contribution either exists or does not.

**Section 10 is deliberately unconventional.** The reflex is to write "not applicable — no
demographic data". Repointing it at slice performance across zones, sockets, testers and cohort sizes
turns a compliance ritual into a real diagnostic, and it is the section most likely to surface a
genuine defect before a judge does.

**Section 8 has teeth.** `AG-10` is a standing commitment that any component failing its own ablation
is removed from the product. The card is where that commitment is either honoured or visibly broken.
