"""Decomposable risk index for LATENTIS numeric core (Phase 3, T-311).

Implements FR-401, D-019, and RISK_SCORING_SPEC § 1-§ 5 (additive risk
decomposition, structurally unable to cross a band boundary):

  - ``risk_total = w_A·anomaly + w_B·drift + w_M·margin + w_Q·quality
    - w_C·credit`` with each component in ``[0, 1]``. Every component is
    computed by calling its registry ``fn`` directly, so there is exactly one
    implementation of each mapping (D-017).
  - Inputs are the authoritative decision values: the DPAT robust distance,
    the ``SafetyResult`` (slope ratio, margin, band), the attribution verdict,
    and the data-quality score. Nothing is recomputed from raw data here; a
    refused upstream (``band None``, missing ``z``) propagates as an explicit
    refusal rather than a substituted default.
  - The ``band`` travels through as an echo, never recomputed and never read
    from the weights: no weight vector can move a part across a band boundary
    (RT-010 at core level, TEST-RISK-002). The score orders the worklist; the
    band plus the two independent verdicts decide.
  - ``sum_check`` ships every figure an auditor needs: the components sum to
    the reported total within ``SUM_CHECK_TOLERANCE``, or the result refuses.
  - Lot roll-up follows the PDA rule (RISK_SCORING_SPEC § 5, D-A-03) with both
    figures reported: reject percentage and the including-EARLY_WARNING
    percentage. Refused parts are excluded with an explicit count, never
    silently diluted into the denominator.

Constraints:
  - No numeric literals outside 0, 1, 2 (edges/weights imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
  - Never returns NaN or inf in decision-bearing outputs.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from backend.core.attribution import AttributionVerdict
from backend.core.constants import (
    DEFAULT_WEIGHT_ANOMALY,
    DEFAULT_WEIGHT_CREDIT,
    DEFAULT_WEIGHT_DRIFT,
    DEFAULT_WEIGHT_MARGIN,
    DEFAULT_WEIGHT_QUALITY,
    PDA_LIMIT_PCT,
    PDA_REVIEW_FRACTION,
    PERCENT_SCALE,
    RISK_SLOPE_RATIO_REF,
    SEVERITY_ELEVATED_Z,
    SEVERITY_SEVERE_Z,
    SUM_CHECK_TOLERANCE,
)
from backend.core.formulas import FORMULAS, attribution_credit_value
from backend.core.safety import SafetyBand, SafetyResult

RiskRefusalCode = Literal[
    "INSUFFICIENT_CALIBRATION",
    "INSUFFICIENT_DATA",
    "INVALID_INPUT",
]

LotVerdict = Literal["PASS_LOT", "REVIEW", "FAIL_LOT"]


@dataclass(frozen=True)
class RiskWeights:
    """Worklist-ordering weights from the ScreeningProfile (policy, D-019)."""

    w_anomaly: float = DEFAULT_WEIGHT_ANOMALY
    w_drift: float = DEFAULT_WEIGHT_DRIFT
    w_margin: float = DEFAULT_WEIGHT_MARGIN
    w_quality: float = DEFAULT_WEIGHT_QUALITY
    w_credit: float = DEFAULT_WEIGHT_CREDIT


@dataclass(frozen=True)
class RiskComponent:
    """One named, weighted contribution to the risk index."""

    name: str
    weight: float
    raw: float
    weighted: float
    formula_id: str


@dataclass(frozen=True)
class RiskSumCheck:
    """Auditor-facing adding-up proof (RISK_SCORING_SPEC § 7)."""

    components_sum: float
    reported_total: float
    abs_diff: float
    tolerance: float


@dataclass(frozen=True)
class RiskResult:
    """Immutable decomposed risk index for one part and one parameter."""

    risk_index: float
    components: tuple[RiskComponent, ...]
    sum_check: RiskSumCheck
    band: SafetyBand | None
    refusal_code: RiskRefusalCode | None = None
    warning: str | None = None


@dataclass(frozen=True)
class LotRollup:
    """Immutable PDA lot disposition with both reported figures."""

    n_tested: int
    n_reject: int
    n_early_warning: int
    n_excluded: int
    pda_pct: float | None
    pda_pct_including_early_warning: float | None
    pda_limit_pct: float
    lot_verdict: LotVerdict | None
    refusal_code: RiskRefusalCode | None = None
    warning: str | None = None


def _risk_refusal(code: RiskRefusalCode, warning: str) -> RiskResult:
    """Build the canonical risk refusal (no index, no components)."""
    return RiskResult(
        risk_index=0.0,
        components=(),
        sum_check=RiskSumCheck(
            components_sum=0.0,
            reported_total=0.0,
            abs_diff=0.0,
            tolerance=SUM_CHECK_TOLERANCE,
        ),
        band=None,
        refusal_code=code,
        warning=warning,
    )


def _checked_weights(weights: RiskWeights | None) -> RiskWeights | RiskResult:
    """Validate profile weights (finite, non-negative) or refuse."""
    resolved = weights if weights is not None else RiskWeights()
    for name in ("w_anomaly", "w_drift", "w_margin", "w_quality", "w_credit"):
        val = getattr(resolved, name)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return _risk_refusal("INVALID_INPUT", f"Weight {name} is not a number")
        if not math.isfinite(float(val)) or float(val) < 0.0:
            return _risk_refusal("INVALID_INPUT", f"Weight {name} must be finite and non-negative")
    return resolved


def compute_risk(
    z_primary: float | None,
    safety: SafetyResult | None,
    attribution: AttributionVerdict | str | None,
    data_quality_score: float | None,
    weights: RiskWeights | None = None,
    zone_arrhenius_consistent: bool = False,
) -> RiskResult:
    """Decompose the risk index from authoritative decision values (T-311).

    Component mappings (RISK_SCORING_SPEC § 2): anomaly from ``|z|`` across
    the AEC-Q001 band edges; drift from ``slope_ratio`` with the criterion
    boundary reading 0.5; margin from the bound-based margin percentage;
    quality from the data-quality score; credit from the attribution table
    (setup evidence subtracts). The total is the weighted sum; the band is
    echoed through untouched.

    Args:
        z_primary: Primary robust distance (DPAT-z, or MAD-z when n < 20).
        safety: Authoritative T-310 result (slope ratio, margin, band).
        attribution: Authoritative T-305 verdict (enum or string).
        data_quality_score: Upstream ingest quality in [0, 1].
        weights: Profile weights (defaults are the documented policy).
        zone_arrhenius_consistent: Whether a ZONE offset is
            Arrhenius-consistent (unlocks the half credit, D-035).

    Returns:
        RiskResult with components, sum_check, and the echoed band — or an
        explicit refusal when an upstream refused or an input is invalid.
    """
    checked = _checked_weights(weights)
    if isinstance(checked, RiskResult):
        return checked
    resolved_weights = checked

    if z_primary is None:
        return _risk_refusal("INSUFFICIENT_DATA", "Primary robust distance missing: no risk")
    if isinstance(z_primary, bool) or not isinstance(z_primary, (int, float)):
        return _risk_refusal("INVALID_INPUT", "Primary robust distance is not a number")
    z_val = float(z_primary)
    if not math.isfinite(z_val):
        return _risk_refusal("INVALID_INPUT", "Primary robust distance is non-finite")

    if safety is None or safety.band is None or safety.refusal_code is not None:
        code: RiskRefusalCode = "INSUFFICIENT_DATA"
        detail = "Safety evaluation refused: risk needs the bound-driven band"
        if safety is not None and safety.refusal_code is not None:
            code = safety.refusal_code
            detail = f"Safety refused ({safety.refusal_code}): risk propagates the refusal"
        return _risk_refusal(code, detail)
    if safety.slope_ratio is None or safety.predicted_margin_pct is None:
        return _risk_refusal("INVALID_INPUT", "Safety result lacks slope ratio or margin")

    if attribution is None:
        return _risk_refusal("INSUFFICIENT_DATA", "Attribution verdict missing: no risk")
    try:
        verdict = (
            attribution
            if isinstance(attribution, AttributionVerdict)
            else AttributionVerdict(str(attribution))
        )
    except ValueError:
        return _risk_refusal("INVALID_INPUT", f"Unknown attribution verdict {attribution!r}")

    if data_quality_score is None:
        return _risk_refusal("INSUFFICIENT_DATA", "Data-quality score missing: no risk")
    if isinstance(data_quality_score, bool) or not isinstance(data_quality_score, (int, float)):
        return _risk_refusal("INVALID_INPUT", "Data-quality score is not a number")
    dq_val = float(data_quality_score)
    if not math.isfinite(dq_val) or dq_val < 0.0 or dq_val > 1.0:
        return _risk_refusal("INVALID_INPUT", "Data-quality score must lie in [0, 1]")

    zone_flag = "yes" if bool(zone_arrhenius_consistent) else "no"
    try:
        anomaly = float(
            FORMULAS["risk.anomaly_v1"].fn(
                abs_z=abs(z_val), z_low=SEVERITY_ELEVATED_Z, z_high=SEVERITY_SEVERE_Z
            )
        )
        drift = float(
            FORMULAS["risk.drift_v1"].fn(
                slope_ratio=safety.slope_ratio, slope_ref=RISK_SLOPE_RATIO_REF
            )
        )
        margin = float(FORMULAS["risk.margin_v1"].fn(margin_pct=safety.predicted_margin_pct))
        quality = float(FORMULAS["risk.quality_v1"].fn(data_quality_score=dq_val))
        credit = float(attribution_credit_value(verdict.value, zone_flag))
    except (ValueError, ZeroDivisionError, OverflowError) as err:
        return _risk_refusal("INVALID_INPUT", f"Risk component evaluation failed: {err}")

    raws = (anomaly, drift, margin, quality, credit)
    if any(not math.isfinite(v) for v in raws):
        return _risk_refusal("INVALID_INPUT", "Risk component overflowed finite range")
    if any(v < 0.0 or v > 1.0 for v in raws):
        return _risk_refusal("INVALID_INPUT", "Risk component escaped [0, 1]")

    weighted = (
        resolved_weights.w_anomaly * anomaly,
        resolved_weights.w_drift * drift,
        resolved_weights.w_margin * margin,
        resolved_weights.w_quality * quality,
        resolved_weights.w_credit * credit,
    )
    try:
        total = float(
            FORMULAS["risk.total_v1"].fn(
                anomaly=anomaly,
                drift=drift,
                margin=margin,
                quality=quality,
                credit=credit,
                w_a=resolved_weights.w_anomaly,
                w_b=resolved_weights.w_drift,
                w_m=resolved_weights.w_margin,
                w_q=resolved_weights.w_quality,
                w_c=resolved_weights.w_credit,
            )
        )
    except (ValueError, ZeroDivisionError, OverflowError) as err:
        return _risk_refusal("INVALID_INPUT", f"Risk total evaluation failed: {err}")
    if not math.isfinite(total):
        return _risk_refusal("INVALID_INPUT", "Risk total overflowed finite range")

    w_anom, w_drift, w_margin, w_quality, w_credit = weighted
    components = (
        RiskComponent("anomaly", resolved_weights.w_anomaly, anomaly, w_anom, "risk.anomaly_v1"),
        RiskComponent("drift", resolved_weights.w_drift, drift, w_drift, "risk.drift_v1"),
        RiskComponent("margin", resolved_weights.w_margin, margin, w_margin, "risk.margin_v1"),
        RiskComponent("quality", resolved_weights.w_quality, quality, w_quality, "risk.quality_v1"),
        RiskComponent(
            "attribution_credit", resolved_weights.w_credit, credit, w_credit, "risk.credit_v1"
        ),
    )
    components_sum = float(w_anom + w_drift + w_margin + w_quality - w_credit)
    abs_diff = abs(components_sum - total)
    if not math.isfinite(abs_diff) or abs_diff > SUM_CHECK_TOLERANCE:
        return _risk_refusal(
            "INVALID_INPUT",
            f"Risk decomposition does not add up (diff {abs_diff!r}); refusing",
        )
    return RiskResult(
        risk_index=total,
        components=components,
        sum_check=RiskSumCheck(
            components_sum=components_sum,
            reported_total=total,
            abs_diff=abs_diff,
            tolerance=SUM_CHECK_TOLERANCE,
        ),
        band=safety.band,
        refusal_code=None,
        warning=None,
    )


def roll_up_lot(
    bands: Sequence[SafetyBand | str | None],
    absolute_fails: Sequence[bool] | None = None,
    pda_limit_pct: float = PDA_LIMIT_PCT,
) -> LotRollup:
    """Roll a lot up to its PDA disposition with both figures (RISK_SPEC § 5).

    ``n_reject`` counts parts with band REJECT or an absolute-limit failure;
    the second figure additionally counts EARLY_WARNING parts. Parts that
    upstream refused (band None, no absolute failure) are excluded with an
    explicit count — never silently diluted into the denominator.

    Args:
        bands: Per-part safety bands (None where upstream refused).
        absolute_fails: Parallel absolute-limit failure flags (all False when
            omitted).
        pda_limit_pct: Profile PDA limit in percent (default 5.0).

    Returns:
        LotRollup with counts, both percentages, and the lot verdict — or an
        explicit refusal on malformed input or an empty tested set.
    """
    try:
        band_list = list(bands)
    except TypeError:
        return LotRollup(
            0,
            0,
            0,
            0,
            None,
            None,
            PDA_LIMIT_PCT,
            None,
            "INVALID_INPUT",
            "Lot bands are not a sequence",
        )
    if absolute_fails is None:
        fail_list = [False] * len(band_list)
    else:
        try:
            fail_list = [bool(v) for v in list(absolute_fails)]
        except TypeError:
            return LotRollup(
                0,
                0,
                0,
                0,
                None,
                None,
                PDA_LIMIT_PCT,
                None,
                "INVALID_INPUT",
                "Absolute-fail flags are not a sequence",
            )
        if len(fail_list) != len(band_list):
            return LotRollup(
                0,
                0,
                0,
                0,
                None,
                None,
                PDA_LIMIT_PCT,
                None,
                "INVALID_INPUT",
                "Band and absolute-fail sequences differ in length",
            )
    try:
        limit = float(pda_limit_pct)
    except (TypeError, ValueError):
        return LotRollup(
            0,
            0,
            0,
            0,
            None,
            None,
            PDA_LIMIT_PCT,
            None,
            "INVALID_INPUT",
            "PDA limit is not a number",
        )
    if not math.isfinite(limit) or limit <= 0.0:
        return LotRollup(
            0,
            0,
            0,
            0,
            None,
            None,
            PDA_LIMIT_PCT,
            None,
            "INVALID_INPUT",
            "PDA limit must be finite and positive",
        )

    n_reject = 0
    n_early = 0
    n_excluded = 0
    for band, failed in zip(band_list, fail_list, strict=True):
        if failed:
            n_reject += 1
            continue
        if band is None:
            n_excluded += 1
            continue
        try:
            name = band if isinstance(band, str) else band.value
        except (AttributeError, ValueError):
            return LotRollup(
                0, 0, 0, 0, None, None, limit, None, "INVALID_INPUT", f"Unknown band value {band!r}"
            )
        if name not in ("SAFE", "WATCH", "EARLY_WARNING", "REJECT"):
            return LotRollup(
                0, 0, 0, 0, None, None, limit, None, "INVALID_INPUT", f"Unknown band value {band!r}"
            )
        if name == "REJECT":
            n_reject += 1
        elif name == "EARLY_WARNING":
            n_early += 1
    n_tested = len(band_list) - n_excluded
    if n_tested <= 0:
        return LotRollup(
            0,
            0,
            0,
            n_excluded,
            None,
            None,
            limit,
            None,
            "INSUFFICIENT_DATA",
            "No tested parts in the lot after exclusions",
        )
    try:
        pda = float(
            FORMULAS["lot.pda_pct_v1"].fn(
                percent_scale=PERCENT_SCALE, n_reject=float(n_reject), n_tested=float(n_tested)
            )
        )
        pda_ew = float(
            FORMULAS["lot.pda_pct_ew_v1"].fn(
                percent_scale=PERCENT_SCALE,
                n_reject_ew=float(n_reject + n_early),
                n_tested=float(n_tested),
            )
        )
    except (ValueError, ZeroDivisionError, OverflowError) as err:
        return LotRollup(
            0,
            0,
            0,
            n_excluded,
            None,
            None,
            limit,
            None,
            "INVALID_INPUT",
            f"PDA evaluation failed: {err}",
        )
    for candidate in (pda, pda_ew):
        if not math.isfinite(candidate):
            return LotRollup(
                0,
                0,
                0,
                n_excluded,
                None,
                None,
                limit,
                None,
                "INVALID_INPUT",
                "PDA percentage overflowed finite range",
            )
    if pda > limit:
        verdict: LotVerdict = "FAIL_LOT"
    elif pda > PDA_REVIEW_FRACTION * limit:
        verdict = "REVIEW"
    else:
        verdict = "PASS_LOT"
    return LotRollup(
        n_tested=n_tested,
        n_reject=n_reject,
        n_early_warning=n_early,
        n_excluded=n_excluded,
        pda_pct=pda,
        pda_pct_including_early_warning=pda_ew,
        pda_limit_pct=limit,
        lot_verdict=verdict,
        refusal_code=None,
        warning=None,
    )
