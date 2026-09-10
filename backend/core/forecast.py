"""Two-point 168 h forecast for LATENTIS numeric core (Phase 3, T-307).

Implements FR-302, FR-303, FR-304, D-005, and DRIFT_SPEC § 4-§ 7:

  - Shape-based point forecast consuming T-306 exactly:
    ``V̂168_shape = v0 + (v24 - v0) · Φ_g(168)`` with ``Φ_g(24) ≡ 1``.
  - Naïve linear baseline always emitted beside the point:
    ``baseline = v0 + (v24 - v0) · 7`` (the power-law special case ``n = 1``,
    TEST-DRIFT-008), so the physics-informed comparison can never be dropped.
  - Residual-correction hook (DRIFT_SPEC § 4.4, AG-10): an additive correction
    is applied only when it earns its place out-of-sample; a correction that
    worsens calibration MAE is rejected and the rejection is recorded
    (TEST-DRIFT-005). The Ridge/GBT fitting itself lives in the training
    pipeline; the core enforces the adoption rule on the numbers.
  - Missing read-points refuse with ``INSUFFICIENT_DATA`` and populate no
    forecast field (TEST-DRIFT-004). Interval-censored ``v24`` is consumed at
    its bound in the conservative direction and flagged (TEST-DRIFT-006).

Constraints:
  - No numeric literals outside 0, 1, 2 (horizons/baselines imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
  - Never returns NaN or inf in decision-bearing outputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from backend.core.constants import LINEAR_BASELINE_PHI_168

V24Censor = Literal["none", "below_lod", "overrange"]

ForecastRefusalCode = Literal[
    "INSUFFICIENT_DATA",
    "INVALID_INPUT",
]


@dataclass(frozen=True)
class ForecastResult:
    """Immutable two-point forecast for one part and one parameter."""

    point: float | None
    baseline_linear: float | None
    shape_point: float | None
    residual_correction: float
    residual_applied: bool
    residual_decision: str | None
    phi_168: float | None
    amplitude: float | None
    censored: bool
    refusal_code: ForecastRefusalCode | None = None
    warning: str | None = None


def _refusal(code: ForecastRefusalCode, warning: str, censored: bool = False) -> ForecastResult:
    """Build the canonical forecast refusal (no forecast field populated)."""
    return ForecastResult(
        point=None,
        baseline_linear=None,
        shape_point=None,
        residual_correction=0.0,
        residual_applied=False,
        residual_decision=None,
        phi_168=None,
        amplitude=None,
        censored=censored,
        refusal_code=code,
        warning=warning,
    )


def _as_finite_or_missing(value: float | None, name: str) -> tuple[float | None, bool]:
    """Split an input into (finite value, is_missing).

    Returns:
        ``(number, False)`` for a finite reading, ``(None, True)`` for ``None``.
        Non-finite floats are *invalid*, not missing: ``(None, False)`` with
        the caller mapping them to the refusal code.
    """
    if value is None:
        return None, True
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, False
    if not math.isfinite(number):
        return None, False
    return number, False


def forecast_v168(
    v0: float | None,
    v24: float | None,
    phi_168: float | None,
    residual_correction: float | None = None,
    shape_mae: float | None = None,
    residual_mae: float | None = None,
    seed_spread: float | None = None,
    v24_censored: V24Censor = "none",
) -> ForecastResult:
    """Forecast the 168 h value from the 0 h and 24 h reads (T-306 consumer).

    Formula: ``V̂_shape = v0 + (v24 - v0) · phi_168``,
    ``baseline = v0 + (v24 - v0) · 7``,
    ``V̂_final = V̂_shape + r̂`` when the correction is adopted.

    Adoption rule (DRIFT_SPEC § 4.4, AG-10): when both MAEs are supplied, the
    correction is adopted iff ``residual_mae + seed_spread < shape_mae``
    (strict improvement beyond the seed-to-seed spread; ``seed_spread = 0``
    when unreported). Otherwise the shape-only forecast ships and the decision
    string records why. When no MAEs are supplied, a caller-provided
    correction is applied as given (the pipeline already adjudicated it) and a
    missing/zero correction means shape-only.

    Censoring (DRIFT_SPEC § 7): ``below_lod`` consumes the reporting bound as
    ``v24`` — for an upper-limit parameter that bound is the largest value the
    truth can take, so the resulting point is conservative by monotonicity
    (TEST-DRIFT-006) — and marks ``censored=True``.

    Args:
        v0: 0 h reading (Amperes internally; unit travels with the caller).
        v24: 24 h reading at the censoring bound when censored.
        phi_168: Fitted group scalar from ``estimate_phi`` (or ``7.0`` for the
            explicit linear fallback; the fallback level is reported upstream).
        residual_correction: Additive correction ``r̂`` (default ``0.0``).
        shape_mae: Out-of-sample MAE of the shape-only model (if compared).
        residual_mae: Out-of-sample MAE with the correction (if compared).
        seed_spread: Seed-to-seed spread of the MAE comparison (if known).
        v24_censored: ``"none"`` | ``"below_lod"`` | ``"overrange"``.

    Returns:
        ForecastResult with the point, the always-present linear baseline, and
        an explicit refusal (never NaN/inf) on degenerate inputs.
    """
    censor_name = str(v24_censored)
    if censor_name not in ("none", "below_lod", "overrange"):
        return _refusal("INVALID_INPUT", f"Unknown censoring flag {v24_censored!r}")

    v0_val, v0_missing = _as_finite_or_missing(v0, "v0")
    v24_val, v24_missing = _as_finite_or_missing(v24, "v24")

    if v0 is not None and v0_val is None and v0_missing is False:
        return _refusal("INVALID_INPUT", "v0 is non-finite (NaN/inf): no forecast")
    if v24 is not None and v24_val is None and v24_missing is False:
        return _refusal("INVALID_INPUT", "v24 is non-finite (NaN/inf): no forecast", False)
    if v0_missing or v24_missing:
        missing = "v0" if v0_missing and v24_missing else ("v0" if v0_missing else "v24")
        return _refusal(
            "INSUFFICIENT_DATA",
            f"Missing {missing} read-point: no imputation of a decision input",
        )

    if phi_168 is None:
        return _refusal("INVALID_INPUT", "phi_168 is missing: no forecast")
    try:
        phi_val = float(phi_168)
    except (TypeError, ValueError):
        return _refusal("INVALID_INPUT", "phi_168 is not a real number: no forecast")
    if not math.isfinite(phi_val):
        return _refusal("INVALID_INPUT", "phi_168 is non-finite: no forecast")

    try:
        correction = 0.0 if residual_correction is None else float(residual_correction)
    except (TypeError, ValueError):
        return _refusal("INVALID_INPUT", "residual_correction is not a real number")
    if not math.isfinite(correction):
        return _refusal("INVALID_INPUT", "residual_correction is non-finite")

    assert v0_val is not None and v24_val is not None
    amplitude = float(v24_val - v0_val)
    shape_point = float(v0_val + amplitude * phi_val)
    baseline = float(v0_val + amplitude * LINEAR_BASELINE_PHI_168)
    if not (math.isfinite(shape_point) and math.isfinite(baseline) and math.isfinite(amplitude)):
        return _refusal("INVALID_INPUT", "Forecast overflowed float64 finite range")

    censored = censor_name != "none"
    decision: str | None = None
    applied = False
    final_point = shape_point
    if shape_mae is not None or residual_mae is not None:
        if shape_mae is None or residual_mae is None:
            return _refusal(
                "INVALID_INPUT",
                "MAE comparison needs both shape_mae and residual_mae",
                censored,
            )
        try:
            shape_err = float(shape_mae)
            resid_err = float(residual_mae)
            spread = 0.0 if seed_spread is None else float(seed_spread)
        except (TypeError, ValueError):
            return _refusal("INVALID_INPUT", "MAE comparison inputs are not real numbers", censored)
        if not (
            math.isfinite(shape_err)
            and math.isfinite(resid_err)
            and math.isfinite(spread)
            and shape_err >= 0.0
            and resid_err >= 0.0
            and spread >= 0.0
        ):
            return _refusal(
                "INVALID_INPUT", "MAE comparison inputs must be finite non-negative", censored
            )
        if resid_err + spread < shape_err and correction != 0.0:
            applied = True
            final_point = float(shape_point + correction)
            decision = (
                f"residual adopted: calib MAE {resid_err} + spread {spread} < shape MAE {shape_err}"
            )
        else:
            applied = False
            correction = 0.0
            decision = (
                f"residual rejected: calib MAE {resid_err} + spread {spread} "
                f">= shape MAE {shape_err}; shape-only ships (AG-10)"
            )
            final_point = shape_point
    else:
        if correction != 0.0:
            applied = True
            final_point = float(shape_point + correction)
            decision = "residual applied as adjudicated upstream (no MAE comparison in core)"
        else:
            applied = False
            decision = None

    if not math.isfinite(final_point):
        return _refusal("INVALID_INPUT", "Corrected forecast overflowed finite range", censored)

    notes: list[str] = []
    if censored:
        if censor_name == "below_lod":
            notes.append("v24 interval-censored below LOD: bound consumed conservatively")
        else:
            notes.append("v24 overrange-censored: bound consumed conservatively")
    if decision is not None and (shape_mae is not None):
        notes.append(decision)
        decision_out: str | None = decision
    else:
        decision_out = decision

    return ForecastResult(
        point=final_point,
        baseline_linear=baseline,
        shape_point=shape_point,
        residual_correction=float(correction),
        residual_applied=applied,
        residual_decision=decision_out,
        phi_168=phi_val,
        amplitude=amplitude,
        censored=censored,
        refusal_code=None,
        warning="; ".join(notes) if notes else None,
    )
