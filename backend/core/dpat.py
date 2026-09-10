"""Dynamic Part Average Testing (DPAT) for LATENTIS numeric core (Phase 3, T-303).

Implements FR-201..FR-204, D-001, D-003, and ANOMALY_SPEC § 4.1, § 4.2, § 9:
  - Leave-one-out cohort isolation (part i strictly excluded from its own cohort)
  - DPAT limit computation: median ± k * (IQR / 1.35)
  - Robust z-score computation: z_robust = (x - median) / robust_sigma
  - Small-lot fallback ladder (n < 20 guard, MAD path with c(n) correction)
  - Zero-variation and insufficient-cohort graceful handling without NaN/inf

Constraints:
  - No numeric literals outside 0, 1, 2 (all thresholds imported from constants.py)
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01)
  - Never returns NaN or inf on finite input (ANOMALY_SPEC § 9)
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np

from backend.core.constants import (
    DPAT_DEFAULT_K,
    MIN_COHORT_SIZE,
    SMALL_LOT_N_THRESHOLD,
)
from backend.core.robust import RobustStatsResult, _clean_1d_array, robust_stats


class DpatVerdict(StrEnum):
    """Verdict of DPAT screening window evaluation."""

    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_COHORT = "INSUFFICIENT_COHORT"
    NO_VARIATION = "NO_VARIATION"


@dataclass(frozen=True)
class DpatLimitsResult:
    """Complete, immutable evaluation result for Dynamic PAT."""

    limit_low: float | None
    limit_high: float | None
    median: float | None
    robust_sigma: float | None
    k: float
    z: float | None
    verdict: DpatVerdict | None
    estimator: str
    n: int
    reduced_power: bool
    zero_iqr: bool
    stats: RobustStatsResult | None = None
    warning: str | None = None


def leave_one_out(
    excluded_component_id: str,
    records: Sequence[Mapping[str, Any] | Any],
    value_field: str = "value",
    id_field: str = "component_id",
    status_field: str = "status",
    ok_status: str = "OK",
) -> np.ndarray:
    """Filter records to produce leave-one-out cohort values strictly excluding target part.

    Asserts non-negotiable invariant INV-2, FR-201, and TEST-STAT-002:
      cohort(i, p, t) = { j : j != i and status == OK }

    Args:
        excluded_component_id: Component ID of part under test to exclude.
        records: Sequence of records (mappings or objects with attribute access).
        value_field: Name of value key/attribute.
        id_field: Name of component ID key/attribute.
        status_field: Name of measurement status key/attribute.
        ok_status: Value indicating an un-flagged, valid measurement (default 'OK').

    Returns:
        1-D float64 numpy array of valid cohort values, strictly excluding target part.
    """
    values: list[float] = []

    for rec in records:
        # Support both dict and object attribute access
        if isinstance(rec, Mapping):
            cid = str(rec.get(id_field, ""))
            stat = str(rec.get(status_field, ok_status))
            val = rec.get(value_field)
        else:
            cid = str(getattr(rec, id_field, ""))
            stat = str(getattr(rec, status_field, ok_status))
            val = getattr(rec, value_field, None)

        if cid == excluded_component_id:
            continue
        if stat != ok_status:
            continue
        if val is None:
            continue

        try:
            fval = float(val)
            if np.isfinite(fval):
                values.append(fval)
        except (ValueError, TypeError):
            continue

    return np.array(values, dtype=np.float64)


def cohort(
    excluded_component_id: str,
    records: Sequence[Mapping[str, Any] | Any],
    target_parameter: str | None = None,
    target_read_point: int | None = None,
    target_lot_id: str | None = None,
    target_component_type: str | None = None,
    param_field: str = "parameter",
    rp_field: str = "read_point_h",
    lot_field: str = "lot_id",
    type_field: str = "component_type",
    value_field: str = "value",
    id_field: str = "component_id",
    status_field: str = "status",
    ok_status: str = "OK",
) -> np.ndarray:
    """Build leave-one-out cohort filtered by lot, type, parameter, and read point.

    Args:
        excluded_component_id: Part under test (strictly excluded).
        records: Source measurement records.
        target_parameter: Required parameter name if filtering.
        target_read_point: Required read point in hours if filtering.
        target_lot_id: Required lot identifier if filtering.
        target_component_type: Required device type if filtering.
        param_field: Name of parameter field.
        rp_field: Name of read point field.
        lot_field: Name of lot identifier field.
        type_field: Name of device type field.
        value_field: Name of measurement value field.
        id_field: Name of component ID field.
        status_field: Name of status field.
        ok_status: Status indicating measurement is valid.

    Returns:
        Filtered 1-D float64 array of cohort values.
    """
    filtered_records: list[Any] = []

    for rec in records:
        if isinstance(rec, Mapping):
            p = rec.get(param_field)
            rp = rec.get(rp_field)
            lid = rec.get(lot_field)
            ctype = rec.get(type_field)
        else:
            p = getattr(rec, param_field, None)
            rp = getattr(rec, rp_field, None)
            lid = getattr(rec, lot_field, None)
            ctype = getattr(rec, type_field, None)

        if target_parameter is not None and p != target_parameter:
            continue
        if target_read_point is not None and rp != target_read_point:
            continue
        if target_lot_id is not None and lid != target_lot_id:
            continue
        if target_component_type is not None and ctype != target_component_type:
            continue

        filtered_records.append(rec)

    return leave_one_out(
        excluded_component_id=excluded_component_id,
        records=filtered_records,
        value_field=value_field,
        id_field=id_field,
        status_field=status_field,
        ok_status=ok_status,
    )


def dpat_limits(
    values: Sequence[float] | np.ndarray,
    part_value: float | None = None,
    k: float = DPAT_DEFAULT_K,
    n_override: int | None = None,
) -> DpatLimitsResult:
    """Compute Dynamic Part Average Testing (DPAT) limits and evaluate candidate reading.

    Formula:
      Robust Sigma = (IQR / 1.35) if n >= 20 and IQR > 0
                     else 1.4826 * c(n) * MAD
      DPAT limits = median ± k * Robust Sigma
      z_robust = (part_value - median) / Robust Sigma

    Implements exact Degenerate Cases table from ANOMALY_SPEC § 9:
      - n < 3 -> INSUFFICIENT_COHORT, warning surfaced, no limits computed
      - 3 <= n < 20 -> MAD path with c(n) correction, reduced_power=True
      - IQR == 0 and MAD == 0 -> NO_VARIATION, never inf or NaN
      - part_value == median -> z = 0.0, PASS

    Args:
        values: Numerical cohort readings (leave-one-out).
        part_value: Optional value of part under test to score.
        k: Limit multiplier k (default 6.0 per AEC-Q001).
        n_override: Optional sample size override for testing small-lot branches.

    Returns:
        DpatLimitsResult with limits, robust z, and verdict.
    """
    arr = _clean_1d_array(values)
    n = n_override if n_override is not None else arr.size

    # 1. Degenerate case: insufficient cohort (n < 3)
    if n < MIN_COHORT_SIZE or arr.size == 0:
        return DpatLimitsResult(
            limit_low=None,
            limit_high=None,
            median=None,
            robust_sigma=None,
            k=k,
            z=None,
            verdict=DpatVerdict.INSUFFICIENT_COHORT,
            estimator="none",
            n=n,
            reduced_power=True,
            zero_iqr=True,
            stats=None,
            warning=(
                f"Cohort size {n} < {MIN_COHORT_SIZE}: insufficient for DPAT statistical limits"
            ),
        )

    stats = robust_stats(arr, n_override=n)

    # 2. Degenerate case: no variation (IQR == 0 and MAD == 0)
    if stats.refusal_code == "NO_VARIATION":
        z_val: float | None = None
        verdict_val: DpatVerdict | None = DpatVerdict.NO_VARIATION
        if part_value is None:
            verdict_val = None
        elif not math.isfinite(part_value):
            verdict_val = DpatVerdict.FAIL
        elif part_value == stats.median:
            z_val = 0.0
        return DpatLimitsResult(
            limit_low=None,
            limit_high=None,
            median=stats.median,
            robust_sigma=0.0,
            k=k,
            z=z_val,
            verdict=verdict_val,
            estimator=stats.estimator,
            n=n,
            reduced_power=stats.reduced_power,
            zero_iqr=True,
            stats=stats,
            warning="Zero variation in cohort: all values identical; DPAT window undefined",
        )

    # 3. Standard and Small-Lot DPAT window calculation
    limit_low = float(stats.median - k * stats.robust_sigma)
    limit_high = float(stats.median + k * stats.robust_sigma)

    warning_msg: str | None = None
    if stats.reduced_power:
        if stats.estimator == "iqr":
            warning_msg = (
                f"Small cohort (n={n} < {SMALL_LOT_N_THRESHOLD}): MAD collapsed to 0; "
                f"fallback to IQR / 1.35 dispersion; reduced statistical power"
            )
        else:
            warning_msg = (
                f"Small cohort (n={n} < {SMALL_LOT_N_THRESHOLD}): primary estimator is MAD "
                f"with finite-sample correction c(n)={stats.c_n:.4f}; reduced statistical power"
            )
    elif stats.zero_iqr:
        warning_msg = f"Cohort IQR is 0 with positive MAD ({stats.mad}): fallen back to MAD path"

    # 4. Score part value if supplied (TEST-003: None part_value returns verdict=None)
    if part_value is None:
        return DpatLimitsResult(
            limit_low=limit_low,
            limit_high=limit_high,
            median=stats.median,
            robust_sigma=stats.robust_sigma,
            k=k,
            z=None,
            verdict=None,
            estimator=stats.estimator,
            n=n,
            reduced_power=stats.reduced_power,
            zero_iqr=stats.zero_iqr,
            stats=stats,
            warning=warning_msg,
        )

    # Reject non-finite candidate reading immediately without NaN/inf emission (TEST-004)
    if not math.isfinite(part_value):
        return DpatLimitsResult(
            limit_low=limit_low,
            limit_high=limit_high,
            median=stats.median,
            robust_sigma=stats.robust_sigma,
            k=k,
            z=None,
            verdict=DpatVerdict.FAIL,
            estimator=stats.estimator,
            n=n,
            reduced_power=stats.reduced_power,
            zero_iqr=stats.zero_iqr,
            stats=stats,
            warning=f"Candidate part reading ({part_value}) is non-finite; evaluated as FAIL",
        )

    # Calculate signed robust z distance and evaluate limits (TEST-001)
    if stats.robust_sigma > 0.0:
        z_score: float | None = float((part_value - stats.median) / stats.robust_sigma)
        is_outside = (part_value < limit_low) or (part_value > limit_high)
        verdict = DpatVerdict.FAIL if is_outside else DpatVerdict.PASS
    else:
        # Robust sigma is 0.0: never produce float("inf")
        if part_value == stats.median:
            z_score = 0.0
            verdict = DpatVerdict.PASS
        else:
            z_score = None
            verdict = DpatVerdict.FAIL
            warning_msg = (
                (f"{warning_msg}; " if warning_msg else "")
                + "Zero dispersion in cohort; candidate value differs from median "
                "and cannot be evaluated"
            )

    return DpatLimitsResult(
        limit_low=limit_low,
        limit_high=limit_high,
        median=stats.median,
        robust_sigma=stats.robust_sigma,
        k=k,
        z=z_score,
        verdict=verdict,
        estimator=stats.estimator,
        n=n,
        reduced_power=stats.reduced_power,
        zero_iqr=stats.zero_iqr,
        stats=stats,
        warning=warning_msg,
    )


def dpat(
    values: Sequence[float] | np.ndarray,
    part_value: float,
    k: float = DPAT_DEFAULT_K,
    n_override: int | None = None,
) -> DpatLimitsResult:
    """Evaluate DPAT limits and part verdict against cohort (convenience wrapper).

    Args:
        values: Numerical cohort readings (leave-one-out).
        part_value: Value of part under test to evaluate.
        k: PAT limit multiplier k.
        n_override: Optional cohort size override.

    Returns:
        DpatLimitsResult with limits, robust z, and verdict.
    """
    return dpat_limits(
        values=values,
        part_value=part_value,
        k=k,
        n_override=n_override,
    )
