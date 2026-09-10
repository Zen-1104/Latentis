"""Unit tests for robust statistics (T-302, TEST-STAT-001).

Pins the Type-7 quartile convention against hand-computed oracle, and verifies
scale/dispersion estimators and small-lot guard behavior.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.core.constants import DPAT_IQR_DIVISOR, MAD_SCALE_FACTOR
from backend.core.robust import (
    median,
    quartiles,
    robust_stats,
)


@pytest.mark.fast
def test_quartiles_type7_hand_computed() -> None:
    """Quartiles of a 9-value list computed by hand under the type-7 convention (TEST-STAT-001).

    Hand computation derivation:
      Given sorted 9-element sample X = [2.0, 4.0, 7.0, 11.0, 16.0, 22.0, 29.0, 37.0, 46.0]
      Under Hyndman & Fan (1996) Type 7 (the default in R, S-PLUS, NumPy 'linear'):
        Index formula: h = 1 + (n - 1) * p = 1 + 8 * p
        For Q1 (p = 0.25): h = 1 + 8 * 0.25 = 3.0 -> exact 3rd order statistic:
          Q1 = X[3] = 7.0
        For Median (p = 0.50): h = 1 + 8 * 0.50 = 5.0 -> exact 5th order statistic:
          Median = X[5] = 16.0
        For Q3 (p = 0.75): h = 1 + 8 * 0.75 = 7.0 -> exact 7th order statistic:
          Q3 = X[7] = 29.0
        IQR = Q3 - Q1 = 29.0 - 7.0 = 22.0

      Contrast with Type 6 (Weibull, p * (n + 1)):
        For Q1: h = 0.25 * 10 = 2.5 -> (X[2] + X[3]) / 2 = (4.0 + 7.0) / 2 = 5.5 != 7.0
      Contrast with Type 8 (median-unbiased, (p * (n + 1/3)) + 1/3):
        For Q1: h = 0.25 * (9 + 1/3) + 1/3 = 2.666... -> 4.0 + 0.666... * 3.0 = 6.0 != 7.0

      This test pins Type-7 definitively to ensure reproducibility and auditability.
    """
    data = [2.0, 4.0, 7.0, 11.0, 16.0, 22.0, 29.0, 37.0, 46.0]

    q1, med, q3 = quartiles(data)
    assert q1 == pytest.approx(7.0), f"Expected Q1=7.0 under Type-7, got {q1}"
    assert med == pytest.approx(16.0), f"Expected Median=16.0 under Type-7, got {med}"
    assert q3 == pytest.approx(29.0), f"Expected Q3=29.0 under Type-7, got {q3}"
    assert (q3 - q1) == pytest.approx(22.0)

    # Standalone median function must agree identically
    assert median(data) == pytest.approx(16.0)


@pytest.mark.fast
def test_robust_stats_normal_sample_selects_iqr_path() -> None:
    """For n >= 20 and IQR > 0, robust_stats selects the standard IQR / 1.35 path."""
    # 25 samples
    rng = np.random.default_rng(12345)
    data = rng.normal(loc=10.0, scale=2.0, size=25).tolist()

    res = robust_stats(data)
    assert res.n == 25
    assert res.estimator == "iqr"
    assert not res.reduced_power
    assert not res.zero_iqr
    assert res.refusal_code is None
    assert res.robust_sigma == pytest.approx(res.iqr / DPAT_IQR_DIVISOR)


@pytest.mark.fast
def test_robust_stats_small_sample_selects_mad_path() -> None:
    """For n < 20, robust_stats selects the MAD path and applies c(n) correction."""
    # 12 samples
    data = [10.1, 10.3, 9.8, 10.5, 10.2, 9.9, 10.0, 10.4, 9.7, 10.6, 10.1, 10.2]
    res = robust_stats(data)

    assert res.n == 12
    assert res.estimator == "mad"
    assert res.reduced_power
    assert res.refusal_code is None
    assert res.c_n == pytest.approx(1.0766)
    expected_sigma = MAD_SCALE_FACTOR * res.c_n * res.mad
    assert res.robust_sigma == pytest.approx(expected_sigma)


@pytest.mark.fast
def test_robust_stats_degenerate_insufficient_cohort() -> None:
    """For n < 3, robust_stats returns refusal code INSUFFICIENT_COHORT with robust_sigma=0.0."""
    data = [12.5, 13.0]
    res = robust_stats(data)

    assert res.n == 2
    assert res.refusal_code == "INSUFFICIENT_COHORT"
    assert res.robust_sigma == 0.0
    assert res.estimator == "none"
    assert not np.isnan(res.robust_sigma)
    assert not np.isinf(res.robust_sigma)


@pytest.mark.fast
def test_robust_stats_zero_iqr_tied_data() -> None:
    """When >50% of values are tied causing IQR=0, zero_iqr flag is set True."""
    # Heavily tied distribution at 10.0
    data = [10.0] * 20 + [5.0, 6.0, 14.0, 15.0, 16.0]
    res = robust_stats(data)

    assert res.n == 25
    assert res.iqr == 0.0
    assert res.zero_iqr is True
    assert res.refusal_code == "NO_VARIATION"


@pytest.mark.fast
def test_robust_stats_zero_variation_all_identical() -> None:
    """When all cohort values are identical (IQR==0 and MAD==0), returns NO_VARIATION."""
    data = [42.0] * 30
    res = robust_stats(data)

    assert res.n == 30
    assert res.iqr == 0.0
    assert res.mad == 0.0
    assert res.robust_sigma == 0.0
    assert res.refusal_code == "NO_VARIATION"
    assert not np.isnan(res.robust_sigma)
    assert not np.isinf(res.robust_sigma)


@pytest.mark.fast
def test_tukey_fences_hand_computed() -> None:
    """Tukey mild (1.5*IQR) and extreme (3.0*IQR) fences match hand arithmetic."""
    # Q1 = 10.0, Q3 = 20.0 => IQR = 10.0
    data = [10.0] * 10 + [20.0] * 10
    res = robust_stats(data)

    assert res.q1 == pytest.approx(10.0)
    assert res.q3 == pytest.approx(20.0)
    assert res.iqr == pytest.approx(10.0)
    # Mild: Q1 - 1.5*10 = -5.0, Q3 + 1.5*10 = 35.0
    assert res.tukey_mild_lower == pytest.approx(-5.0)
    assert res.tukey_mild_upper == pytest.approx(35.0)
    # Extreme: Q1 - 3.0*10 = -20.0, Q3 + 3.0*10 = 50.0
    assert res.tukey_extreme_lower == pytest.approx(-20.0)
    assert res.tukey_extreme_upper == pytest.approx(50.0)


@pytest.mark.fast
def test_robust_stats_small_cohort_zero_mad_fallback_to_iqr() -> None:
    """When n < 20 and MAD collapses to 0 while IQR > 0, falls back to IQR / 1.35 (TEST-001)."""
    # 10 samples (< 20): 6 ties at median 10.0, but extremities exist (IQR = 7.5 > 0, MAD = 0.0)
    data = [1.0] + [10.0] * 6 + [20.0] * 3
    res = robust_stats(data)

    assert res.n == 10
    assert res.iqr == pytest.approx(7.5)
    assert res.mad == 0.0
    assert res.estimator == "iqr"
    assert res.reduced_power is True
    assert res.robust_sigma == pytest.approx(7.5 / DPAT_IQR_DIVISOR)
    assert not np.isnan(res.robust_sigma)
    assert not np.isinf(res.robust_sigma)


@pytest.mark.fast
def test_type7_iqr_zero_implies_mad_zero_invariant() -> None:
    """Theorem: Type-7 linear interpolation IQR==0 mathematically implies MAD==0 (TEST-005)."""
    for n in (5, 9, 12, 20, 35):
        ties = (n // 2) + 2
        arr = [0.0] * ((n - ties) // 2) + [10.0] * ties + [20.0] * ((n - ties + 1) // 2)
        res = robust_stats(arr)
        if res.iqr == 0.0:
            assert res.mad == 0.0, f"Invariant violation at n={n}: iqr={res.iqr}, mad={res.mad}"
            assert res.refusal_code == "NO_VARIATION"
