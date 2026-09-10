"""Two-sided tabular CUSUM persistent-shift evidence (Phase 4, T-408).

Implements D-038 and `LATENTIS_Hackathon_Implementation_Plan.md` § 12 (Lens 1):

  - Page's tabular two-sided CUSUM, the standard SPC construction for turning
    small sustained deviations into visible evidence. With ``z = (x - ref)/s``,
    ``S_H = max(0, S_H + z - k)`` accumulates upward runs and
    ``S_L = max(0, S_L - z - k)`` downward runs; either exceeding ``h``
    signals persistent-shift evidence in that direction.
  - The caller supplies the observation series (time-ordered,
    screening-visible only — never 96 h/168 h observations, INV-4), the
    ``reference`` level, and the ``scale``. This module computes no cohort
    statistics itself (typically the leave-one-out lot median and robust
    sigma travel in from the DPAT path), so there is no second statistical
    truth and no new normalisation model.
  - ``None`` entries are gaps: accumulation pauses, the gap is counted, and
    crossing indices stay aligned with the caller's series. Any non-finite
    or non-numeric entry refuses with ``INVALID_INPUT`` rather than silently
    re-indexing the series (a short evidence series must not hide data
    defects; contrast the conformal skip rule for long calibration sets).
  - Fewer than ``CUSUM_MIN_OBSERVATIONS`` effective observations refuse with
    ``INSUFFICIENT_DATA``: persistence is a property of a run, and 1-2 point
    snapshots are owned by the DPAT/delta paths.
  - Advisory only (D-038): the result carries no verdict, band, or
    recommendation, and no decision module may import this one
    (TEST-CUSUM-009 pins both). The Phase 3 chain is byte-identical with
    CUSUM evidence present or absent.

Constraints:
  - No numeric literals outside 0, 1, 2 (``k``, ``h``, minimum imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
  - Never returns NaN or inf: overflow refuses with ``INVALID_INPUT``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from backend.core.constants import (
    CUSUM_DECISION_H,
    CUSUM_MIN_OBSERVATIONS,
    CUSUM_REFERENCE_K,
)

CusumRefusalCode = Literal[
    "INSUFFICIENT_DATA",
    "INVALID_INPUT",
]


@dataclass(frozen=True)
class CusumResult:
    """Immutable two-sided CUSUM evidence for one part / parameter series."""

    s_high: float | None
    s_low: float | None
    signal_high: bool
    signal_low: bool
    first_crossing_high: int | None
    first_crossing_low: int | None
    n_observations: int
    n_gaps: int
    k: float
    h: float
    refusal_code: CusumRefusalCode | None = None
    warning: str | None = None


def _refusal(
    code: CusumRefusalCode,
    warning: str,
    n_observations: int,
    n_gaps: int,
    k: float,
    h: float,
) -> CusumResult:
    """Build the canonical refusal: counts and parameters travel, no statistic."""
    return CusumResult(
        s_high=None,
        s_low=None,
        signal_high=False,
        signal_low=False,
        first_crossing_high=None,
        first_crossing_low=None,
        n_observations=n_observations,
        n_gaps=n_gaps,
        k=k,
        h=h,
        refusal_code=code,
        warning=warning,
    )


def _parse_tuning(k: float, h: float) -> tuple[float, float] | None:
    """Validate the allowance and decision interval; None when unusable."""
    for candidate in (k, h):
        if isinstance(candidate, (bool, str, bytes, bytearray)):
            return None
        try:
            as_float = float(candidate)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(as_float):
            return None
    try:
        k_val = float(k)
        h_val = float(h)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(k_val) and math.isfinite(h_val)):
        return None
    if k_val <= 0.0 or h_val <= 0.0:
        return None
    return (k_val, h_val)


def cusum_evidence(
    values: Sequence[float | None],
    reference: float,
    scale: float,
    k: float = CUSUM_REFERENCE_K,
    h: float = CUSUM_DECISION_H,
) -> CusumResult:
    """Accumulate two-sided tabular CUSUM evidence over a measurement series.

    Args:
        values: Time-ordered observations in physical units; ``None`` marks a
            gap (accumulation pauses, the gap is counted). Must contain only
            finite reals and ``None`` — anything else refuses.
        reference: Caller-supplied target level in the same unit (typically
            the leave-one-out lot median). Must be finite.
        scale: Caller-supplied dispersion in the same unit (typically the lot
            robust sigma). Must be finite and strictly positive.
        k: Per-step allowance in scale units (default ``CUSUM_REFERENCE_K``).
        h: Decision interval in scale units (default ``CUSUM_DECISION_H``).

    Returns:
        CusumResult with the final accumulators ``s_high``/``s_low`` (scale
        units), the latched signal flags, the first crossing indices into the
        caller's series (``None`` when never crossed), and the effective
        counts — or an explicit refusal carrying the counts and parameters.
    """
    tuning = _parse_tuning(k, h)
    if tuning is None:
        return _refusal(
            "INVALID_INPUT",
            f"k and h must be finite with k > 0 and h > 0, got k={k!r} h={h!r}",
            0,
            0,
            CUSUM_REFERENCE_K,
            CUSUM_DECISION_H,
        )
    k_val, h_val = tuning

    if isinstance(reference, (bool, str, bytes, bytearray)):
        return _refusal(
            "INVALID_INPUT",
            f"reference is not a real number: {reference!r}",
            0,
            0,
            k_val,
            h_val,
        )
    try:
        ref_val = float(reference)
    except (TypeError, ValueError):
        return _refusal(
            "INVALID_INPUT",
            f"reference is not a real number: {reference!r}",
            0,
            0,
            k_val,
            h_val,
        )
    if not math.isfinite(ref_val):
        return _refusal(
            "INVALID_INPUT",
            "reference is non-finite (NaN/inf): no evidence",
            0,
            0,
            k_val,
            h_val,
        )

    if isinstance(scale, (bool, str, bytes, bytearray)):
        return _refusal(
            "INVALID_INPUT",
            f"scale is not a real number: {scale!r}",
            0,
            0,
            k_val,
            h_val,
        )
    try:
        scale_val = float(scale)
    except (TypeError, ValueError):
        return _refusal(
            "INVALID_INPUT",
            f"scale is not a real number: {scale!r}",
            0,
            0,
            k_val,
            h_val,
        )
    if not math.isfinite(scale_val) or scale_val <= 0.0:
        return _refusal(
            "INVALID_INPUT",
            f"scale must be finite and strictly positive, got {scale!r}",
            0,
            0,
            k_val,
            h_val,
        )

    try:
        series = list(values)
    except TypeError:
        return _refusal(
            "INVALID_INPUT",
            "values is not a sequence of observations",
            0,
            0,
            k_val,
            h_val,
        )

    deviations: list[float | None] = []
    for entry in series:
        if entry is None:
            deviations.append(None)
            continue
        if isinstance(entry, (bool, str, bytes, bytearray)):
            return _refusal(
                "INVALID_INPUT",
                f"observation is not a real number: {entry!r}",
                0,
                0,
                k_val,
                h_val,
            )
        try:
            observed = float(entry)
        except (TypeError, ValueError):
            return _refusal(
                "INVALID_INPUT",
                f"observation is not a real number: {entry!r}",
                0,
                0,
                k_val,
                h_val,
            )
        if not math.isfinite(observed):
            return _refusal(
                "INVALID_INPUT",
                "observation is non-finite (NaN/inf): represent it as a gap or fix upstream",
                0,
                0,
                k_val,
                h_val,
            )
        shift = observed - ref_val
        if not math.isfinite(shift):
            return _refusal(
                "INVALID_INPUT",
                "observation minus reference overflowed float64 finite range",
                0,
                0,
                k_val,
                h_val,
            )
        deviations.append(shift / scale_val)

    n_gaps = sum(1 for item in deviations if item is None)
    n_obs = len(deviations) - n_gaps
    if n_obs < CUSUM_MIN_OBSERVATIONS:
        return _refusal(
            "INSUFFICIENT_DATA",
            f"only {n_obs} effective observations "
            f"(minimum {CUSUM_MIN_OBSERVATIONS}): persistence needs a run",
            n_obs,
            n_gaps,
            k_val,
            h_val,
        )

    s_high = 0.0
    s_low = 0.0
    first_high: int | None = None
    first_low: int | None = None
    for index, item in enumerate(deviations):
        if item is None:
            continue
        s_high = max(0.0, s_high + item - k_val)
        s_low = max(0.0, s_low - item - k_val)
        if not (math.isfinite(s_high) and math.isfinite(s_low)):
            return _refusal(
                "INVALID_INPUT",
                "CUSUM accumulator overflowed float64 finite range",
                n_obs,
                n_gaps,
                k_val,
                h_val,
            )
        if first_high is None and s_high > h_val:
            first_high = index
        if first_low is None and s_low > h_val:
            first_low = index

    warning: str | None = None
    if n_gaps > 0:
        warning = f"{n_gaps} gaps paused accumulation without resetting it"
    return CusumResult(
        s_high=s_high,
        s_low=s_low,
        signal_high=first_high is not None,
        signal_low=first_low is not None,
        first_crossing_high=first_high,
        first_crossing_low=first_low,
        n_observations=n_obs,
        n_gaps=n_gaps,
        k=k_val,
        h=h_val,
        refusal_code=None,
        warning=warning,
    )
