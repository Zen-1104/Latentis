"""Safety criterion and disposition bands for LATENTIS numeric core (Phase 3, T-310).

Implements FR-306, FR-307, D-002, D-010, and DRIFT_SPEC § 6-§ 7:

  - Derived slopes in physical units: ``observed_early_slope = (v24-v0)/24``
    and ``predicted_long_slope = (V̂168-v0)/168``.
  - Safety slope derived from configuration, never a universal constant:
    ``usable_margin = (limit_high - v0) · (1 - margin_fraction)`` and
    ``safety_slope = usable_margin / horizon`` (defaults ``0.20`` / ``168 h``,
    both ``assumed`` policy inputs swept in sensitivity analysis). Where the
    profile supplies an explicit delta limit ``Δ_max``, it takes precedence:
    ``safety_slope = Δ_max / horizon`` (the specified engineering criterion
    outranks the derivation).
  - Predicted margin from the **bound** (D-010):
    ``predicted_margin = limit_high - Û168``.
  - Four bands with conservative priority ``REJECT > EARLY_WARNING > WATCH >
    SAFE``. ``EARLY_WARNING`` — slope over the safety slope while the bound
    stays inside the absolute limit — is the flagship band that exists only
    because we forecast. A part whose bound merely enters the held-back
    reserve with a shallow slope promotes to ``WATCH`` rather than hiding in
    ``SAFE`` (documented gap-fill, D-036: the table pins the slope edges but
    not that corner, and the conservative direction is the only honest one).
  - Zero/negative/insufficient cases refuse explicitly: an ``INFINITE`` bound
    propagates as ``INSUFFICIENT_CALIBRATION`` (never silently converted to a
    rejection), a missing limit or a ``v0`` at/above the limit refuses as
    ``INVALID_INPUT`` (the absolute-limit path owns that part per FR-210), and
    no output is ever NaN or inf.

Constraints:
  - No numeric literals outside 0, 1, 2 (fractions/horizons/edges imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from backend.core.constants import (
    FORECAST_HORIZON_H,
    INTERMEDIATE_READ_POINT_H,
    SAFETY_MARGIN_FRACTION,
    SAFETY_SLOPE_RATIO_EARLY_WARNING,
    SAFETY_SLOPE_RATIO_WATCH,
)

SafetyBand = Literal["SAFE", "WATCH", "EARLY_WARNING", "REJECT"]

SafetyRefusalCode = Literal[
    "INSUFFICIENT_CALIBRATION",
    "INSUFFICIENT_DATA",
    "INVALID_INPUT",
]


@dataclass(frozen=True)
class SafetyResult:
    """Immutable safety evaluation for one part and one parameter."""

    band: SafetyBand | None
    usable_margin: float | None
    safety_slope: float | None
    observed_early_slope: float | None
    predicted_long_slope: float | None
    predicted_margin: float | None
    predicted_margin_pct: float | None
    slope_ratio: float | None
    safe_threshold: float | None
    limit_high: float | None
    v0: float | None
    upper_168: float | None
    point_168: float | None
    delta_max_used: bool
    refusal_code: SafetyRefusalCode | None = None
    warning: str | None = None


def _finite_or_none(value: float | None) -> float | None:
    """Return a finite float, else None (never propagates NaN or inf)."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def evaluate_safety(
    v0: float | None,
    upper_168: float | None,
    point_168: float | None,
    v24: float | None,
    limit_high: float | None,
    margin_fraction: float = SAFETY_MARGIN_FRACTION,
    horizon_hours: float = FORECAST_HORIZON_H,
    delta_max: float | None = None,
) -> SafetyResult:
    """Derive the safety criterion from configuration and assign the band.

    Band rules (DRIFT_SPEC § 6.3, bound-driven per D-010):

      - ``REJECT`` when ``Û168 ≥ limit_high``.
      - ``EARLY_WARNING`` when ``slope_ratio ≥ 1.0`` while ``Û168 < limit``.
      - ``WATCH`` when ``slope_ratio`` is in ``[0.7, 1.0)``, or when the bound
        has entered the held-back reserve with a shallower slope (gap-fill).
      - ``SAFE`` when the bound stays below ``limit_high - usable_margin``
        and ``slope_ratio < 0.7``.

    Args:
        v0: 0 h reading (same unit as the limit; Amperes internally).
        upper_168: Conformal upper bound ``Û168`` (None when ``INFINITE``).
        point_168: Shape-based point forecast ``V̂168`` (drives the slopes).
        v24: 24 h reading (drives the observed early slope; None allowed only
            when the early slope is not needed — it is always reported when
            available, and None otherwise).
        limit_high: Profile absolute limit for the parameter.
        margin_fraction: Configured reserve held back for post-screen life
            (default ``0.20``, ``assumed`` policy input).
        horizon_hours: Screening horizon in hours (default ``168``).
        delta_max: Explicit profile delta limit; when supplied it takes
            precedence for ``safety_slope`` (DRIFT_SPEC § 6.2).

    Returns:
        SafetyResult with every derived quantity and the band, or a refusal
        with ``band=None`` (never NaN/inf, never a silent default).
    """
    if upper_168 is None:
        return SafetyResult(
            band=None,
            usable_margin=None,
            safety_slope=None,
            observed_early_slope=None,
            predicted_long_slope=None,
            predicted_margin=None,
            predicted_margin_pct=None,
            slope_ratio=None,
            safe_threshold=None,
            limit_high=_finite_or_none(limit_high),
            v0=_finite_or_none(v0),
            upper_168=None,
            point_168=_finite_or_none(point_168),
            delta_max_used=False,
            refusal_code="INSUFFICIENT_CALIBRATION",
            warning="Conformal bound INFINITE: no safety band without a bound",
        )

    v0_val = _finite_or_none(v0)
    upper_val = _finite_or_none(upper_168)
    point_val = _finite_or_none(point_168)
    limit_val = _finite_or_none(limit_high)
    if v0_val is None:
        code: SafetyRefusalCode = "INSUFFICIENT_DATA" if v0 is None else "INVALID_INPUT"
        return SafetyResult(
            band=None,
            usable_margin=None,
            safety_slope=None,
            observed_early_slope=None,
            predicted_long_slope=None,
            predicted_margin=None,
            predicted_margin_pct=None,
            slope_ratio=None,
            safe_threshold=None,
            limit_high=limit_val,
            v0=None,
            upper_168=upper_val,
            point_168=point_val,
            delta_max_used=False,
            refusal_code=code,
            warning="v0 missing or non-finite: no safety criterion",
        )
    if upper_val is None or point_val is None or limit_val is None:
        return SafetyResult(
            band=None,
            usable_margin=None,
            safety_slope=None,
            observed_early_slope=None,
            predicted_long_slope=None,
            predicted_margin=None,
            predicted_margin_pct=None,
            slope_ratio=None,
            safe_threshold=None,
            limit_high=limit_val,
            v0=v0_val,
            upper_168=upper_val,
            point_168=point_val,
            delta_max_used=False,
            refusal_code="INVALID_INPUT",
            warning="upper bound, point forecast, or limit is non-finite",
        )

    try:
        margin_frac = float(margin_fraction)
        horizon = float(horizon_hours)
    except (TypeError, ValueError):
        return SafetyResult(
            band=None,
            usable_margin=None,
            safety_slope=None,
            observed_early_slope=None,
            predicted_long_slope=None,
            predicted_margin=None,
            predicted_margin_pct=None,
            slope_ratio=None,
            safe_threshold=None,
            limit_high=limit_val,
            v0=v0_val,
            upper_168=upper_val,
            point_168=point_val,
            delta_max_used=False,
            refusal_code="INVALID_INPUT",
            warning="margin_fraction or horizon_hours is not a real number",
        )
    if not (
        math.isfinite(margin_frac)
        and math.isfinite(horizon)
        and margin_frac >= 0.0
        and margin_frac < 1.0
        and horizon > 0.0
    ):
        return SafetyResult(
            band=None,
            usable_margin=None,
            safety_slope=None,
            observed_early_slope=None,
            predicted_long_slope=None,
            predicted_margin=None,
            predicted_margin_pct=None,
            slope_ratio=None,
            safe_threshold=None,
            limit_high=limit_val,
            v0=v0_val,
            upper_168=upper_val,
            point_168=point_val,
            delta_max_used=False,
            refusal_code="INVALID_INPUT",
            warning="margin_fraction must lie in [0, 1) and horizon must be positive",
        )

    headroom = float(limit_val - v0_val)
    if headroom <= 0.0:
        return SafetyResult(
            band=None,
            usable_margin=None,
            safety_slope=None,
            observed_early_slope=None,
            predicted_long_slope=None,
            predicted_margin=None,
            predicted_margin_pct=None,
            slope_ratio=None,
            safe_threshold=None,
            limit_high=limit_val,
            v0=v0_val,
            upper_168=upper_val,
            point_168=point_val,
            delta_max_used=False,
            refusal_code="INVALID_INPUT",
            warning="v0 at/above the absolute limit: absolute-limit path owns this part (FR-210)",
        )

    delta_val = _finite_or_none(delta_max) if delta_max is not None else None
    delta_used = False
    if delta_max is not None:
        if delta_val is None or delta_val <= 0.0:
            return SafetyResult(
                band=None,
                usable_margin=None,
                safety_slope=None,
                observed_early_slope=None,
                predicted_long_slope=None,
                predicted_margin=None,
                predicted_margin_pct=None,
                slope_ratio=None,
                safe_threshold=None,
                limit_high=limit_val,
                v0=v0_val,
                upper_168=upper_val,
                point_168=point_val,
                delta_max_used=False,
                refusal_code="INVALID_INPUT",
                warning="Supplied delta_max is non-finite or non-positive",
            )
        safety_slope = float(delta_val / horizon)
        delta_used = True
    else:
        safety_slope = float(headroom * (1.0 - margin_frac) / horizon)
    if not math.isfinite(safety_slope) or safety_slope <= 0.0:
        return SafetyResult(
            band=None,
            usable_margin=None,
            safety_slope=None,
            observed_early_slope=None,
            predicted_long_slope=None,
            predicted_margin=None,
            predicted_margin_pct=None,
            slope_ratio=None,
            safe_threshold=None,
            limit_high=limit_val,
            v0=v0_val,
            upper_168=upper_val,
            point_168=point_val,
            delta_max_used=delta_used,
            refusal_code="INVALID_INPUT",
            warning="Derived safety slope is non-finite or non-positive",
        )

    usable_margin = float(headroom * (1.0 - margin_frac))
    safe_threshold = float(limit_val - usable_margin)

    v24_val = _finite_or_none(v24)
    if v24_val is None:
        early_slope: float | None = None
    else:
        early_slope = float((v24_val - v0_val) / INTERMEDIATE_READ_POINT_H)
        if not math.isfinite(early_slope):
            return SafetyResult(
                band=None,
                usable_margin=usable_margin,
                safety_slope=safety_slope,
                observed_early_slope=None,
                predicted_long_slope=None,
                predicted_margin=None,
                predicted_margin_pct=None,
                slope_ratio=None,
                safe_threshold=safe_threshold,
                limit_high=limit_val,
                v0=v0_val,
                upper_168=upper_val,
                point_168=point_val,
                delta_max_used=delta_used,
                refusal_code="INVALID_INPUT",
                warning="Observed early slope overflowed finite range",
            )

    long_slope = float((point_val - v0_val) / horizon)
    ratio = float(long_slope / safety_slope)
    predicted_margin = float(limit_val - upper_val)
    predicted_margin_pct = float(predicted_margin / headroom)
    for candidate in (
        usable_margin,
        safe_threshold,
        long_slope,
        ratio,
        predicted_margin,
        predicted_margin_pct,
    ):
        if not math.isfinite(candidate):
            return SafetyResult(
                band=None,
                usable_margin=None,
                safety_slope=safety_slope,
                observed_early_slope=early_slope,
                predicted_long_slope=None,
                predicted_margin=None,
                predicted_margin_pct=None,
                slope_ratio=None,
                safe_threshold=None,
                limit_high=limit_val,
                v0=v0_val,
                upper_168=upper_val,
                point_168=point_val,
                delta_max_used=delta_used,
                refusal_code="INVALID_INPUT",
                warning="Safety derivation overflowed float64 finite range",
            )

    if upper_val >= limit_val:
        band: SafetyBand | None = "REJECT"
    elif ratio >= SAFETY_SLOPE_RATIO_EARLY_WARNING:
        band = "EARLY_WARNING"
    elif ratio >= SAFETY_SLOPE_RATIO_WATCH or upper_val >= safe_threshold:
        band = "WATCH"
    else:
        band = "SAFE"

    return SafetyResult(
        band=band,
        usable_margin=usable_margin,
        safety_slope=safety_slope,
        observed_early_slope=early_slope,
        predicted_long_slope=long_slope,
        predicted_margin=predicted_margin,
        predicted_margin_pct=predicted_margin_pct,
        slope_ratio=ratio,
        safe_threshold=safe_threshold,
        limit_high=limit_val,
        v0=v0_val,
        upper_168=upper_val,
        point_168=point_val,
        delta_max_used=delta_used,
        refusal_code=None,
        warning=None,
    )
