"""Population degradation shape estimation for LATENTIS numeric core (Phase 3, T-306).

Implements FR-302, D-005, D-006, and DRIFT_SPEC § 4 (Shape-Amplitude model):

  - ``value_i(t) = v0_i + A_i · Φ_g(t)`` with the normalisation ``Φ_g(24) ≡ 1``,
    so the per-part amplitude ``A_i = v24_i - v0_i`` is identifiable from exactly
    the two screening observations, and only the scalar ``Φ_g(168)`` is borrowed
    across parts within group ``g = (component_type, parameter)``.
  - ``estimate_phi`` fits ``Φ_g(168)`` on **training trajectories only** as the
    robust median of per-part empirical ratios ``(v168 - v0) / (v24 - v0)``. The
    median inherits the Type-7 convention (D-004) and the outlier insensitivity
    the screening task requires; the caller enforces the train-only discipline
    by passing ``train_lot_ids`` and the estimate records the lots actually used
    (TEST-DRIFT-003), so a calibration/test leak is auditable by a subset check.
  - ``phi_at`` evaluates every candidate family from DRIFT_SPEC § 4.2 with the
    normalisation enforced exactly (``t = 24`` short-circuits to ``1.0``), so
    TEST-DRIFT-001 holds for all families by construction rather than by fit.

Constraints:
  - No numeric literals outside 0, 1, 2 (all horizons/levels imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
  - Never returns NaN or inf in decision-bearing outputs; degenerate inputs
    refuse with an explicit code instead of a number.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from backend.core.constants import (
    FORECAST_HORIZON_H,
    INTERMEDIATE_READ_POINT_H,
    LINEAR_BASELINE_PHI_168,
    MIN_COHORT_SIZE,
)
from backend.core.robust import median

ShapeFamily = Literal["power_law", "log_time", "saturating", "linear", "empirical"]

ShapeRefusalCode = Literal[
    "INSUFFICIENT_COHORT",
    "NO_VARIATION",
    "INVALID_INPUT",
]

_ALLOWED_FAMILIES: tuple[str, ...] = ("power_law", "log_time", "saturating", "linear", "empirical")


@dataclass(frozen=True)
class ShapeEstimate:
    """Immutable population-shape fit for one group ``g``.

    ``phi_168`` is the only quantity needed at inference (DRIFT_SPEC § 4.1).
    ``lots_used`` records the training lots that contributed, so the caller can
    assert the fitted set is a subset of the train split (TEST-DRIFT-003).
    ``fallback_level`` is 0 for a group-fitted value; parent-group and linear
    fallbacks live in the training pipeline, which reports the level it used.
    """

    phi_168: float | None
    family: str
    family_param: float | None
    n_used: int
    n_skipped_zero_amplitude: int
    n_skipped_nonfinite: int
    n_excluded_by_train_filter: int
    lots_used: tuple[str, ...] | None
    fallback_level: int
    refusal_code: ShapeRefusalCode | None = None
    warning: str | None = None


def _refusal(
    family: str,
    n_used: int,
    n_zero: int,
    n_nonfinite: int,
    n_excluded: int,
    lots: tuple[str, ...] | None,
    code: ShapeRefusalCode,
    warning: str,
) -> ShapeEstimate:
    """Build the canonical shape-fit refusal (no ``phi_168``, counts kept)."""
    return ShapeEstimate(
        phi_168=None,
        family=family,
        family_param=None,
        n_used=n_used,
        n_skipped_zero_amplitude=n_zero,
        n_skipped_nonfinite=n_nonfinite,
        n_excluded_by_train_filter=n_excluded,
        lots_used=lots,
        fallback_level=0,
        refusal_code=code,
        warning=warning,
    )


def estimate_phi(
    v0: Sequence[float] | np.ndarray,
    v24: Sequence[float] | np.ndarray,
    v168: Sequence[float] | np.ndarray,
    lot_ids: Sequence[str] | np.ndarray | None = None,
    train_lot_ids: Sequence[str] | None = None,
    family: ShapeFamily = "empirical",
) -> ShapeEstimate:
    """Fit the population shape scalar ``Φ_g(168)`` from training trajectories.

    Estimator: robust median over per-part empirical ratios
    ``phi_i = (v168_i - v0_i) / (v24_i - v0_i)``. Parts with a zero 24 h
    amplitude carry no shape information and are skipped with a count (they are
    not evidence against the shape); non-finite entries are skipped likewise.
    ``Φ_g(24) ≡ 1`` holds by the model formulation, not by the data.

    Args:
        v0: 0 h readings, one per training part.
        v24: 24 h readings, aligned with ``v0``.
        v168: 168 h readings, aligned with ``v0`` (training lots only).
        lot_ids: Optional lot identifier per part, aligned with ``v0``.
        train_lot_ids: Optional allow-list of training lots. When supplied,
            only parts whose lot is in the set contribute; the rest are counted
            in ``n_excluded_by_train_filter`` and ``lots_used`` is then
            provably a subset of this set (TEST-DRIFT-003).
        family: Shape-family label carried into the estimate for the model
            card. The scalar fit itself is family-agnostic (empirical median);
            ``phi_at`` renders any family from it.

    Returns:
        ShapeEstimate with ``phi_168`` finite or a refusal code (never NaN).
    """
    family_name = str(family)
    if family_name not in _ALLOWED_FAMILIES:
        return _refusal(
            family_name,
            0,
            0,
            0,
            0,
            None,
            "INVALID_INPUT",
            f"Unknown shape family {family_name!r}",
        )

    try:
        a0 = np.asarray(v0, dtype=np.float64).ravel()
        a24 = np.asarray(v24, dtype=np.float64).ravel()
        a168 = np.asarray(v168, dtype=np.float64).ravel()
    except (TypeError, ValueError):
        return _refusal(
            family_name,
            0,
            0,
            0,
            0,
            None,
            "INVALID_INPUT",
            "Trajectory inputs are not real-valued vectors",
        )
    if not (a0.shape == a24.shape == a168.shape):
        return _refusal(
            family_name,
            0,
            0,
            0,
            0,
            None,
            "INVALID_INPUT",
            f"Trajectory length mismatch: {a0.shape} vs {a24.shape} vs {a168.shape}",
        )

    lots: list[str] | None = None
    if lot_ids is not None:
        try:
            lots = [str(v) for v in list(lot_ids)]
        except TypeError:
            return _refusal(
                family_name,
                0,
                0,
                0,
                0,
                None,
                "INVALID_INPUT",
                "lot_ids is not a sequence aligned with the trajectories",
            )
        if len(lots) != a0.shape[0]:
            return _refusal(
                family_name,
                0,
                0,
                0,
                0,
                None,
                "INVALID_INPUT",
                "lot_ids length does not match trajectory length",
            )

    train_set: set[str] | None = None
    if train_lot_ids is not None:
        if lots is None:
            return _refusal(
                family_name,
                0,
                0,
                0,
                0,
                None,
                "INVALID_INPUT",
                "train_lot_ids supplied without lot_ids: leak discipline unenforceable",
            )
        train_set = {str(v) for v in train_lot_ids}

    ratios: list[float] = []
    used_lots: list[str] = []
    n_zero = 0
    n_nonfinite = 0
    n_excluded = 0
    for idx in range(a0.shape[0]):
        if train_set is not None and lots is not None and lots[idx] not in train_set:
            n_excluded += 1
            continue
        x0 = float(a0[idx])
        x24 = float(a24[idx])
        x168 = float(a168[idx])
        if not (math.isfinite(x0) and math.isfinite(x24) and math.isfinite(x168)):
            n_nonfinite += 1
            continue
        amplitude = x24 - x0
        if amplitude == 0.0:
            n_zero += 1
            continue
        ratio = (x168 - x0) / amplitude
        if not math.isfinite(ratio):
            n_nonfinite += 1
            continue
        ratios.append(ratio)
        if lots is not None:
            used_lots.append(lots[idx])

    lots_used: tuple[str, ...] | None = None
    if lots is not None:
        lots_used = tuple(sorted(set(used_lots)))

    n_used = len(ratios)
    if n_used < MIN_COHORT_SIZE:
        if n_used == 0 and n_zero > 0 and (n_zero + n_nonfinite) >= MIN_COHORT_SIZE:
            return _refusal(
                family_name,
                n_used,
                n_zero,
                n_nonfinite,
                n_excluded,
                lots_used,
                "NO_VARIATION",
                "All usable trajectories have zero 24 h amplitude: shape unidentifiable",
            )
        return _refusal(
            family_name,
            n_used,
            n_zero,
            n_nonfinite,
            n_excluded,
            lots_used,
            "INSUFFICIENT_COHORT",
            f"Usable trajectories n={n_used} < {MIN_COHORT_SIZE}: no shape fit",
        )

    phi_value = float(median(np.asarray(ratios, dtype=np.float64)))
    if not math.isfinite(phi_value):
        return _refusal(
            family_name,
            n_used,
            n_zero,
            n_nonfinite,
            n_excluded,
            lots_used,
            "INVALID_INPUT",
            "Median shape ratio is non-finite; refusing to emit a shape",
        )

    family_param: float | None = None
    notes: list[str] = []
    if family_name in ("power_law", "empirical"):
        if phi_value > 0.0:
            family_param = float(math.log(phi_value) / math.log(LINEAR_BASELINE_PHI_168))
        else:
            notes.append("non-positive phi_168: power-law exponent undefined, scalar kept")
    if n_zero > 0 or n_nonfinite > 0 or n_excluded > 0:
        notes.append(
            f"skipped zero_amplitude={n_zero} nonfinite={n_nonfinite} "
            f"excluded_by_train_filter={n_excluded}"
        )

    return ShapeEstimate(
        phi_168=phi_value,
        family=family_name,
        family_param=family_param,
        n_used=n_used,
        n_skipped_zero_amplitude=n_zero,
        n_skipped_nonfinite=n_nonfinite,
        n_excluded_by_train_filter=n_excluded,
        lots_used=lots_used,
        fallback_level=0,
        refusal_code=None,
        warning="; ".join(notes) if notes else None,
    )


def phi_at(
    t_hours: float,
    phi_168: float | None = None,
    family: ShapeFamily = "power_law",
    family_param: float | None = None,
) -> float:
    """Evaluate the normalised shape curve ``Φ(t)`` with ``Φ(24) ≡ 1``.

    Family forms from DRIFT_SPEC § 4.2, each normalised so ``Φ(24) = 1``
    exactly (the ``t = 24`` case short-circuits to ``1.0`` rather than relying
    on floating-point cancellation):

      - ``power_law`` / ``empirical``: ``(t/24)^n`` with ``n`` from
        ``family_param`` when supplied, else derived from ``phi_168`` via
        ``n = log(phi_168) / log(7)`` (``Φ(168) = 7^n``).
      - ``linear``: ``t/24`` (``phi_168`` ignored; ``Φ(168) = 7`` always).
      - ``log_time``: ``log(1+t/τ) / log(1+24/τ)`` with ``τ = family_param``.
      - ``saturating``: ``(1-e^(-t/τ)) / (1-e^(-24/τ))`` with ``τ`` likewise.

    Args:
        t_hours: Elapsed time in hours (must be finite and non-negative).
        phi_168: Fitted group scalar (required for the power-law derivation).
        family: Which candidate family to render.
        family_param: Exponent ``n`` (power law) or time constant ``τ`` in
            hours (log-time / saturating). Required for log-time/saturating.

    Returns:
        Normalised shape multiplier (finite float, ``1.0`` at ``t = 24``).

    Raises:
        ValueError: On a non-finite/negative time, an unknown family, a
            missing or non-positive parameter, or a non-finite result.
    """
    family_name = str(family)
    if family_name not in _ALLOWED_FAMILIES:
        raise ValueError(f"Unknown shape family {family_name!r}")
    try:
        t_val = float(t_hours)
    except (TypeError, ValueError) as err:
        raise ValueError(f"Elapsed time is not a real number: {t_hours!r}") from err
    if not math.isfinite(t_val) or t_val < 0.0:
        raise ValueError(f"Elapsed time must be finite and non-negative, got {t_hours!r}")
    if t_val == 0.0:
        return 0.0
    if t_val == INTERMEDIATE_READ_POINT_H:
        return 1.0

    horizon = float(INTERMEDIATE_READ_POINT_H)
    if family_name == "linear":
        result = t_val / horizon
    elif family_name in ("power_law", "empirical"):
        exponent: float | None = None
        if family_param is not None:
            try:
                exponent = float(family_param)
            except (TypeError, ValueError) as err:
                raise ValueError(f"Shape exponent is not a real number: {family_param!r}") from err
            if not math.isfinite(exponent) or exponent <= 0.0:
                raise ValueError(
                    f"Shape exponent must be finite and positive, got {family_param!r}"
                )
        else:
            if phi_168 is None:
                raise ValueError("power-law evaluation needs phi_168 or an explicit exponent")
            try:
                phi_val = float(phi_168)
            except (TypeError, ValueError) as err:
                raise ValueError(f"phi_168 is not a real number: {phi_168!r}") from err
            if not math.isfinite(phi_val) or phi_val <= 0.0:
                raise ValueError(
                    f"phi_168 must be finite and positive to derive n, got {phi_168!r}"
                )
            exponent = float(math.log(phi_val) / math.log(LINEAR_BASELINE_PHI_168))
        result = float((t_val / horizon) ** exponent)
    elif family_name in ("log_time", "saturating"):
        if family_param is None:
            raise ValueError(f"Family {family_name!r} needs family_param=tau_hours")
        try:
            tau = float(family_param)
        except (TypeError, ValueError) as err:
            raise ValueError(f"time constant tau is not a real number: {family_param!r}") from err
        if not math.isfinite(tau) or tau <= 0.0:
            raise ValueError(f"time constant tau must be finite and positive, got {family_param!r}")
        if family_name == "log_time":
            result = float(math.log(1.0 + t_val / tau) / math.log(1.0 + horizon / tau))
        else:
            denom = 1.0 - math.exp(-horizon / tau)
            if denom == 0.0:
                raise ValueError(f"Saturating denominator underflow for tau={tau!r}")
            result = float((1.0 - math.exp(-t_val / tau)) / denom)
    else:  # pragma: no cover — guarded by the allow-list above
        raise ValueError(f"Unknown shape family {family_name!r}")

    if not math.isfinite(result):
        raise ValueError(f"Shape evaluation overflowed for t={t_val!r}, family={family_name!r}")
    if (
        t_val == FORECAST_HORIZON_H
        and family_name in ("power_law", "empirical")
        and phi_168 is not None
    ):
        try:
            anchor = float(phi_168)
        except (TypeError, ValueError):
            anchor = result
        if math.isfinite(anchor) and anchor > 0.0 and family_param is None:
            return anchor
    return result
