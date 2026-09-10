"""Split-conformal upper bound for LATENTIS numeric core (Phase 3, T-308).

Implements FR-305, FR-307, D-008, D-009, D-010, and CONFORMAL_SPEC § 2-§ 3:

  - Signed residuals ``s_i = y_i - ŷ_i`` (under-prediction is the dangerous
    direction; absolute residuals would waste half the width on it).
  - Finite-sample order statistic ``k = ⌈(n+1)(1-alpha)⌉`` — the ``+1`` is what
    makes the coverage statement finite-sample rather than asymptotic, pinned
    by the 9-element hand test (TEST-CONF-001). No interpolation: ``q̂`` is the
    ``k``-th smallest residual, because interpolated quantiles do not carry the
    same statement.
  - ``k > n`` ⇒ the bound is ``INFINITE`` with ``attainable_alpha = 1/(n+1)``
    rather than a silently returned maximum (the part routes to
    ``INSUFFICIENT_CALIBRATION``). Returning a number there would invent
    confidence the calibration set cannot support.
  - Mondrian ladder (CONFORMAL_SPEC § 3): the caller supplies groupings from
    fine to coarse — ``(component_type, parameter)``, ``(parameter)``,
    marginal — and the first attainable level wins; the level actually used
    travels in the payload as ``mondrian_level`` (``3`` = ``INFINITE``).
    Only the finest cell of a multi-level ladder must additionally clear
    ``n_min_mondrian``; fallbacks need an attainable quantile. A single
    calibration set is a direct § 2 evaluation (operational callers ladder
    before calling). See D-036 for this documented interpretation.
  - The **bound** drives the rejection decision downstream (D-010); the point
    forecast is carried alongside for display and MAE only (RT-005).

Constraints:
  - No numeric literals outside 0, 1, 2 (``alpha`` default and ``n_min`` imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
  - Never returns NaN or inf: ``INFINITE`` is ``upper=None`` plus a refusal.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from backend.core.constants import (
    DEFAULT_ALPHA,
    MONDRIAN_LEVEL_INSUFFICIENT,
    MONDRIAN_N_MIN_CALIBRATION,
)

ConformalRefusalCode = Literal[
    "INSUFFICIENT_CALIBRATION",
    "INVALID_INPUT",
]


@dataclass(frozen=True)
class ConformalResult:
    """Immutable one-sided conformal upper bound for one part / parameter."""

    upper: float | None
    point: float | None
    q_hat: float | None
    alpha: float
    mondrian_level: int
    mondrian_group: str | None
    n_cal: int | None
    k: int | None
    bound_finite: bool
    attainable_alpha: float | None
    refusal_code: ConformalRefusalCode | None = None
    warning: str | None = None


def _invalid(warning: str, alpha: float) -> ConformalResult:
    """Build the canonical malformed-input refusal (no bound)."""
    return ConformalResult(
        upper=None,
        point=None,
        q_hat=None,
        alpha=alpha,
        mondrian_level=MONDRIAN_LEVEL_INSUFFICIENT,
        mondrian_group=None,
        n_cal=None,
        k=None,
        bound_finite=False,
        attainable_alpha=None,
        refusal_code="INVALID_INPUT",
        warning=warning,
    )


def conformal_upper(
    point_forecast: float | None,
    calib_levels: Sequence[Sequence[float] | np.ndarray],
    level_names: Sequence[str] | None = None,
    alpha: float = DEFAULT_ALPHA,
    n_min_mondrian: int = MONDRIAN_N_MIN_CALIBRATION,
) -> ConformalResult:
    """Compute the one-sided split-conformal upper bound ``Û168 = ŷ + q̂``.

    Args:
        point_forecast: Shape-based point forecast ``ŷ`` (same unit as ``y``).
        calib_levels: Calibration signed residuals ``y - ŷ`` ordered from the
            finest Mondrian cell to the coarsest (marginal last). A single set
            is evaluated directly per CONFORMAL_SPEC § 2.
        level_names: Optional group label per level, aligned with
            ``calib_levels`` and reported as ``mondrian_group``.
        alpha: Miscoverage probability in ``(0, 1)`` (default from profile).
        n_min_mondrian: Minimum members for the finest cell of a multi-level
            ladder (default 50 per CONFORMAL_SPEC § 3).

    Returns:
        ConformalResult with the bound (or ``INFINITE`` as ``upper=None``),
        the quantile, the order statistic, and the level actually used.
    """
    try:
        alpha_val = float(alpha)
    except (TypeError, ValueError):
        return _invalid(f"alpha is not a real number: {alpha!r}", DEFAULT_ALPHA)
    if not math.isfinite(alpha_val) or not (alpha_val > 0.0 and alpha_val < 1.0):
        fallback_alpha = alpha_val if math.isfinite(alpha_val) else DEFAULT_ALPHA
        return _invalid(f"alpha must lie in (0, 1), got {alpha!r}", fallback_alpha)

    try:
        n_min_val = int(n_min_mondrian)
    except (TypeError, ValueError):
        return _invalid(f"n_min_mondrian is not an integer: {n_min_mondrian!r}", alpha_val)
    if n_min_val != n_min_mondrian or n_min_val < 1:
        return _invalid(
            f"n_min_mondrian must be a positive integer, got {n_min_mondrian!r}", alpha_val
        )

    if point_forecast is None:
        return _invalid("point forecast is missing: no bound", alpha_val)
    try:
        point_val = float(point_forecast)
    except (TypeError, ValueError):
        return _invalid("point forecast is not a real number: no bound", alpha_val)
    if not math.isfinite(point_val):
        return _invalid("point forecast is non-finite (NaN/inf): no bound", alpha_val)

    try:
        levels = list(calib_levels)
    except TypeError:
        return _invalid("calib_levels is not a sequence of residual sets", alpha_val)
    if len(levels) == 0:
        return ConformalResult(
            upper=None,
            point=point_val,
            q_hat=None,
            alpha=alpha_val,
            mondrian_level=MONDRIAN_LEVEL_INSUFFICIENT,
            mondrian_group=None,
            n_cal=0,
            k=None,
            bound_finite=False,
            attainable_alpha=1.0,
            refusal_code="INSUFFICIENT_CALIBRATION",
            warning="No calibration residuals supplied: bound INFINITE",
        )

    names: list[str] | None = None
    if level_names is not None:
        try:
            names = [str(v) for v in list(level_names)]
        except TypeError:
            return _invalid("level_names is not aligned with calib_levels", alpha_val)
        if len(names) != len(levels):
            return _invalid("level_names length does not match calib_levels", alpha_val)

    use_ladder_gate = len(levels) > 1
    cleaned: list[np.ndarray] = []
    skipped_total = 0
    for raw in levels:
        try:
            arr = np.asarray(raw, dtype=np.float64).ravel()
        except (TypeError, ValueError):
            return _invalid("A calibration level is not a real-valued vector", alpha_val)
        finite = arr[np.isfinite(arr)]
        skipped_total += arr.size - finite.size
        cleaned.append(finite)

    for index, finite in enumerate(cleaned):
        n_cal = finite.size
        k_stat = math.ceil((n_cal + 1) * (1.0 - alpha_val))
        if k_stat < 1 or k_stat > n_cal:
            continue
        if use_ladder_gate and index == 0 and n_cal < n_min_val:
            continue
        ordered = np.sort(finite)
        q_hat = float(ordered[k_stat - 1])
        if not math.isfinite(q_hat):
            continue
        upper = float(point_val + q_hat)
        if not math.isfinite(upper):
            return _invalid("Conformal bound overflowed float64 finite range", alpha_val)
        notes: list[str] = []
        if skipped_total > 0:
            notes.append(f"skipped {skipped_total} non-finite calibration residuals")
        if not use_ladder_gate:
            notes.append("direct single-group quantile (CONFORMAL_SPEC § 2)")
        return ConformalResult(
            upper=upper,
            point=point_val,
            q_hat=q_hat,
            alpha=alpha_val,
            mondrian_level=index,
            mondrian_group=(names[index] if names is not None else None),
            n_cal=n_cal,
            k=k_stat,
            bound_finite=True,
            attainable_alpha=None,
            refusal_code=None,
            warning="; ".join(notes) if notes else None,
        )

    n_marginal = cleaned[-1].size
    attainable = 1.0 / (n_marginal + 1)
    notes = ["k > n_cal at every level: bound INFINITE (CONFORMAL_SPEC § 2)"]
    if skipped_total > 0:
        notes.append(f"skipped {skipped_total} non-finite calibration residuals")
    return ConformalResult(
        upper=None,
        point=point_val,
        q_hat=None,
        alpha=alpha_val,
        mondrian_level=MONDRIAN_LEVEL_INSUFFICIENT,
        mondrian_group=(names[-1] if names is not None else None),
        n_cal=n_marginal,
        k=None,
        bound_finite=False,
        attainable_alpha=float(attainable),
        refusal_code="INSUFFICIENT_CALIBRATION",
        warning="; ".join(notes),
    )
