"""Robust univariate statistics for LATENTIS numeric core (Phase 3, T-302).

Implements FR-202, FR-205, D-001, D-003, D-004, and D-CD-03:
  - Median and Type-7 quartiles (pinned convention, D-004, TEST-STAT-001)
  - Interquartile Range (IQR) and Median Absolute Deviation (MAD)
  - Robust sigma estimation with small-sample guard (n < 20) and finite-sample
    correction factor c(n) (FR-202, RQ-03, TEST-STAT-005)
  - Medcouple (MC) robust skewness estimator (Brys, Hubert & Struyf 2004)
  - Adjusted boxplot fences (Hubert & Vandervieren 2008, RQ-04, TEST-STAT-006)
  - Tukey mild and extreme outlier fences

Constraints:
  - No numeric literals outside 0, 1, 2 (all parameters imported from constants.py)
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01)
  - No NaN or inf returned on finite input (ANOMALY_SPEC § 9)
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from backend.core.constants import (
    ADJUSTED_BOXPLOT_K,
    ADJUSTED_BOXPLOT_MC_EXP_LOWER_NEG,
    ADJUSTED_BOXPLOT_MC_EXP_LOWER_POS,
    ADJUSTED_BOXPLOT_MC_EXP_UPPER_NEG,
    ADJUSTED_BOXPLOT_MC_EXP_UPPER_POS,
    DPAT_IQR_DIVISOR,
    MAD_FINITE_SAMPLE_CORRECTIONS,
    MAD_SCALE_FACTOR,
    MIN_COHORT_SIZE,
    PERCENTILE_MEDIAN,
    PERCENTILE_Q1,
    PERCENTILE_Q3,
    QUARTILE_METHOD,
    SMALL_LOT_N_THRESHOLD,
    TUKEY_EXTREME_MULTIPLIER,
    TUKEY_MILD_MULTIPLIER,
)

EstimatorType = Literal["iqr", "mad", "none"]
RefusalCode = Literal["INSUFFICIENT_COHORT", "NO_VARIATION"]


@dataclass(frozen=True)
class RobustStatsResult:
    """Immutable result container for robust lot statistics."""

    median: float
    q1: float
    q3: float
    iqr: float
    mad: float
    robust_sigma: float
    c_n: float
    n: int
    estimator: EstimatorType
    reduced_power: bool
    zero_iqr: bool
    tukey_mild_lower: float
    tukey_mild_upper: float
    tukey_extreme_lower: float
    tukey_extreme_upper: float
    medcouple: float
    adjusted_boxplot_lower: float
    adjusted_boxplot_upper: float
    refusal_code: RefusalCode | None = None


def _clean_1d_array(data: Sequence[float] | np.ndarray) -> np.ndarray:
    """Convert input to a clean 1-D float64 numpy array without NaNs."""
    arr = np.asarray(data, dtype=np.float64).ravel()
    if arr.size == 0:
        return np.empty(0, dtype=np.float64)
    valid_mask = np.isfinite(arr)
    return arr[valid_mask]


def median(data: Sequence[float] | np.ndarray) -> float:
    """Compute median using pinned Type-7 linear interpolation convention.

    Args:
        data: Sequence of numerical values.

    Returns:
        Sample median as float, or 0.0 if empty.
    """
    arr = _clean_1d_array(data)
    if arr.size == 0:
        return 0.0
    return float(np.percentile(arr, PERCENTILE_MEDIAN, method=QUARTILE_METHOD))


def quartiles(data: Sequence[float] | np.ndarray) -> tuple[float, float, float]:
    """Compute Q1, median, and Q3 using pinned Type-7 linear interpolation (D-004).

    Asserted against hand-computed oracle on a 9-element list (TEST-STAT-001).

    Args:
        data: Sequence of numerical values.

    Returns:
        Tuple of (q1, median, q3). Returns (0.0, 0.0, 0.0) if empty.
    """
    arr = _clean_1d_array(data)
    if arr.size == 0:
        return (0.0, 0.0, 0.0)
    q1 = float(np.percentile(arr, PERCENTILE_Q1, method=QUARTILE_METHOD))
    med = float(np.percentile(arr, PERCENTILE_MEDIAN, method=QUARTILE_METHOD))
    q3 = float(np.percentile(arr, PERCENTILE_Q3, method=QUARTILE_METHOD))
    return (q1, med, q3)


def _mad(arr: np.ndarray, med: float) -> float:
    """Compute Median Absolute Deviation: median(|x_i - med|)."""
    if arr.size == 0:
        return 0.0
    abs_deviations = np.abs(arr - med)
    return float(np.percentile(abs_deviations, PERCENTILE_MEDIAN, method=QUARTILE_METHOD))


def medcouple(data: Sequence[float] | np.ndarray) -> float:
    """Compute medcouple robust measure of skewness (Brys, Hubert & Struyf 2004).

    For sample x_1 <= ... <= x_n and median m:
      h(x_i, x_j) = ((x_j - m) - (m - x_i)) / (x_j - x_i) for x_i <= m <= x_j, x_i != x_j
    Returns median of all h(x_i, x_j). Satisfies MC(-x) = -MC(x) (antisymmetric).

    Args:
        data: Sequence of numerical values.

    Returns:
        Medcouple in [-1.0, 1.0]. Returns 0.0 for n < 3 or constant samples.
    """
    arr = _clean_1d_array(data)
    n = arr.size
    if n < MIN_COHORT_SIZE:
        return 0.0

    sorted_arr = np.sort(arr)
    med_val = float(np.percentile(sorted_arr, PERCENTILE_MEDIAN, method=QUARTILE_METHOD))

    # Constant sample check
    if sorted_arr[0] == sorted_arr[-1]:
        return 0.0

    left = sorted_arr[sorted_arr <= med_val]
    right = sorted_arr[sorted_arr >= med_val]

    # Handle ties at median per Brys et al. (2004) kernel definition
    k_ties = int(np.sum(sorted_arr == med_val))
    left_tied_offset = left.size - k_ties

    h_values: list[float] = []

    for i, xi in enumerate(left):
        for j, yj in enumerate(right):
            if xi < yj:
                h = ((yj - med_val) - (med_val - xi)) / (yj - xi)
                h_values.append(h)
            elif xi == med_val and yj == med_val:
                # 1-based indices among tied elements
                p = i - left_tied_offset + 1
                q = j + 1
                sum_idx = p + q - 1
                if sum_idx < k_ties:
                    h_values.append(-1.0)
                elif sum_idx == k_ties:
                    h_values.append(0.0)
                else:
                    h_values.append(1.0)

    h_arr = np.array(h_values, dtype=np.float64)
    return float(np.percentile(h_arr, PERCENTILE_MEDIAN, method=QUARTILE_METHOD))


def adjusted_boxplot(
    data: Sequence[float] | np.ndarray,
    mc_value: float | None = None,
) -> tuple[float, float]:
    """Compute adjusted boxplot fences for skewed distributions (Hubert & Vandervieren 2008).

    For right-skewed data (MC >= 0):
      lower = Q1 - 1.5 * exp(-4 * MC) * IQR  (tightens lower boundary)
      upper = Q3 + 1.5 * exp(3 * MC) * IQR   (widens upper boundary)
    For left-skewed data (MC < 0):
      lower = Q1 - 1.5 * exp(-3 * MC) * IQR  (widens lower boundary)
      upper = Q3 + 1.5 * exp(4 * MC) * IQR   (tightens upper boundary)

    Args:
        data: Sequence of numerical values.
        mc_value: Optional precomputed medcouple. If None, computed from data.

    Returns:
        Tuple of (lower_fence, upper_fence).
    """
    arr = _clean_1d_array(data)
    if arr.size == 0:
        return (0.0, 0.0)

    q1, _, q3 = quartiles(arr)
    iqr_val = q3 - q1

    if mc_value is None:
        mc_val = medcouple(arr)
    else:
        mc_val = mc_value

    if mc_val >= 0.0:
        lower_multiplier = ADJUSTED_BOXPLOT_K * math.exp(ADJUSTED_BOXPLOT_MC_EXP_LOWER_POS * mc_val)
        upper_multiplier = ADJUSTED_BOXPLOT_K * math.exp(ADJUSTED_BOXPLOT_MC_EXP_UPPER_POS * mc_val)
    else:
        lower_multiplier = ADJUSTED_BOXPLOT_K * math.exp(ADJUSTED_BOXPLOT_MC_EXP_LOWER_NEG * mc_val)
        upper_multiplier = ADJUSTED_BOXPLOT_K * math.exp(ADJUSTED_BOXPLOT_MC_EXP_UPPER_NEG * mc_val)

    lower_fence = q1 - lower_multiplier * iqr_val
    upper_fence = q3 + upper_multiplier * iqr_val

    return (float(lower_fence), float(upper_fence))


def robust_stats(
    data: Sequence[float] | np.ndarray,
    n_override: int | None = None,
) -> RobustStatsResult:
    """Compute comprehensive robust statistics with small-lot fallback ladder.

    Implements the selection rules from ANOMALY_SPEC § 4.2 and § 9:
      - n < 3: refusal code INSUFFICIENT_COHORT, robust_sigma = 0.0
      - 3 <= n < 20: MAD path primary with finite-sample correction c(n),
        reduced_power = True
      - n >= 20: IQR path primary (robust_sigma = IQR / 1.35)
      - IQR == 0 and MAD > 0: fallback to MAD path, zero_iqr = True
      - IQR == 0 and MAD == 0: refusal code NO_VARIATION, robust_sigma = 0.0,
        never produces inf or NaN

    Args:
        data: Sequence of numerical values.
        n_override: Optional cohort size override for testing sample size logic.

    Returns:
        RobustStatsResult dataclass containing all computed statistics.
    """
    arr = _clean_1d_array(data)
    n = n_override if n_override is not None else arr.size

    # Fallback for insufficient sample size
    if n < MIN_COHORT_SIZE or arr.size == 0:
        med_val = median(arr) if arr.size > 0 else 0.0
        return RobustStatsResult(
            median=med_val,
            q1=med_val,
            q3=med_val,
            iqr=0.0,
            mad=0.0,
            robust_sigma=0.0,
            c_n=1.0,
            n=n,
            estimator="none",
            reduced_power=True,
            zero_iqr=True,
            tukey_mild_lower=med_val,
            tukey_mild_upper=med_val,
            tukey_extreme_lower=med_val,
            tukey_extreme_upper=med_val,
            medcouple=0.0,
            adjusted_boxplot_lower=med_val,
            adjusted_boxplot_upper=med_val,
            refusal_code="INSUFFICIENT_COHORT",
        )

    q1, med, q3 = quartiles(arr)
    iqr_val = float(q3 - q1)
    mad_val = _mad(arr, med)
    c_n_val = float(MAD_FINITE_SAMPLE_CORRECTIONS.get(n, 1.0))
    mc_val = medcouple(arr)
    adj_low, adj_high = adjusted_boxplot(arr, mc_value=mc_val)

    # Tukey fences
    tukey_mild_low = float(q1 - TUKEY_MILD_MULTIPLIER * iqr_val)
    tukey_mild_high = float(q3 + TUKEY_MILD_MULTIPLIER * iqr_val)
    tukey_ext_low = float(q1 - TUKEY_EXTREME_MULTIPLIER * iqr_val)
    tukey_ext_high = float(q3 + TUKEY_EXTREME_MULTIPLIER * iqr_val)

    # Estimator selection ladder (ANOMALY_SPEC § 4.2 & § 9)
    if iqr_val == 0.0 and mad_val == 0.0:
        return RobustStatsResult(
            median=med,
            q1=q1,
            q3=q3,
            iqr=0.0,
            mad=0.0,
            robust_sigma=0.0,
            c_n=c_n_val,
            n=n,
            estimator="none",
            reduced_power=(n < SMALL_LOT_N_THRESHOLD),
            zero_iqr=True,
            tukey_mild_lower=tukey_mild_low,
            tukey_mild_upper=tukey_mild_high,
            tukey_extreme_lower=tukey_ext_low,
            tukey_extreme_upper=tukey_ext_high,
            medcouple=mc_val,
            adjusted_boxplot_lower=adj_low,
            adjusted_boxplot_upper=adj_high,
            refusal_code="NO_VARIATION",
        )

    # Note on Type-7 Quantile Invariant (TEST-005):
    # Under Hyndman & Fan (1996) Type-7 linear interpolation, IQR == 0 mathematically
    # implies that at least (n + 1)/2 data points are identical to the median, which
    # strictly forces MAD == 0. Thus, for raw arrays, IQR == 0 with MAD > 0 is
    # mathematically impossible and intercepted by NO_VARIATION above.
    #
    # Estimator Selection Ladder (ANOMALY_SPEC § 4.2, § 5, § 9):
    # For small lots (n < 20), MAD is the primary estimator with c(n) correction.
    # However, if MAD collapses to 0.0 due to >50% ties at median while IQR > 0.0
    # (TEST-001), we fall back to IQR / 1.35 dispersion to prevent zero-sigma and infinite z.
    if n < SMALL_LOT_N_THRESHOLD:
        if mad_val > 0.0:
            robust_sigma = float(MAD_SCALE_FACTOR * c_n_val * mad_val)
            estimator: EstimatorType = "mad"
        else:
            # Fallback when MAD collapses on discrete/tied small cohort with non-zero IQR
            robust_sigma = float(iqr_val / DPAT_IQR_DIVISOR)
            estimator = "iqr"
        reduced_power = True
        zero_iqr = False
    else:
        # Normal sample size (n >= 20): DPAT standard IQR / 1.35 path
        robust_sigma = float(iqr_val / DPAT_IQR_DIVISOR)
        estimator = "iqr"
        reduced_power = False
        zero_iqr = False

    return RobustStatsResult(
        median=med,
        q1=q1,
        q3=q3,
        iqr=iqr_val,
        mad=mad_val,
        robust_sigma=robust_sigma,
        c_n=c_n_val,
        n=n,
        estimator=estimator,
        reduced_power=reduced_power,
        zero_iqr=zero_iqr,
        tukey_mild_lower=tukey_mild_low,
        tukey_mild_upper=tukey_mild_high,
        tukey_extreme_lower=tukey_ext_low,
        tukey_extreme_upper=tukey_ext_high,
        medcouple=mc_val,
        adjusted_boxplot_lower=adj_low,
        adjusted_boxplot_upper=adj_high,
        refusal_code=None,
    )
