"""Unit tests for Dynamic Part Average Testing (DPAT) (T-303, TEST-STAT-004, TEST-STAT-005).

Pins AEC-Q001 arithmetic against worked hand computation and verifies
estimator selection ladder and small-lot guard behavior (ANOMALY_SPEC § 5 & § 9).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from backend.core.constants import MAD_FINITE_SAMPLE_CORRECTIONS
from backend.core.dpat import (
    DpatVerdict,
    dpat,
    dpat_limits,
)


@pytest.mark.fast
def test_dpat_limits_hand_computed() -> None:
    """AEC-Q001 formula evaluated on paper (TEST-STAT-004).

    Oracle derivation:
      median = 10.4, IQR = 2.7, k = 6.0
      Under AEC-Q001 / DPAT standard:
        robust_sigma = IQR / 1.35 = 2.7 / 1.35 = 2.0
        limit_high = median + k * robust_sigma = 10.4 + 6 * 2.0 = 22.4
        limit_low = median - k * robust_sigma = 10.4 - 6 * 2.0 = -1.6
      For candidate reading x = 27.8:
        x - median = 27.8 - 10.4 = 17.4
        z_robust = 17.4 / 2.0 = 8.7 > k=6 => FAIL
    """
    # Construct a 25-element symmetric sample with exact Q1=9.05, Med=10.4, Q3=11.75 => IQR=2.7
    # For n=25, under Type-7 (linear):
    #   h_q1 = 1 + 24*0.25 = 7 (index 6)
    #   h_med = 1 + 24*0.50 = 13 (index 12)
    #   h_q3 = 1 + 24*0.75 = 19 (index 18)
    sample = [9.05] * 7 + [10.4] * 6 + [11.75] * 12

    res = dpat_limits(sample, part_value=27.8, k=6.0)

    assert res.median == pytest.approx(10.4)
    assert res.robust_sigma == pytest.approx(2.0)
    assert res.limit_high == pytest.approx(22.4)
    assert res.limit_low == pytest.approx(-1.6)
    assert res.estimator == "iqr"
    assert not res.reduced_power
    assert res.z == pytest.approx(8.7)
    assert res.verdict == DpatVerdict.FAIL

    # Inside limits: part_value = 10.4 => z=0.0, PASS
    res_pass = dpat(sample, part_value=10.4, k=6.0)
    assert res_pass.z == pytest.approx(0.0)
    assert res_pass.verdict == DpatVerdict.PASS

    # Exactly at boundary 22.4 => PASS
    res_boundary = dpat(sample, part_value=22.4, k=6.0)
    assert res_boundary.z == pytest.approx(6.0)
    assert res_boundary.verdict == DpatVerdict.PASS


@pytest.mark.fast
def test_mad_path_primary_below_n20() -> None:
    """ANOMALY_SPEC § 5 table: n=12 selects 'mad' with c(n); n=40 selects 'iqr' (TEST-STAT-005)."""
    # Case 1: n = 12 (< 20)
    rng = np.random.default_rng(42)
    sample_12 = rng.normal(loc=50.0, scale=3.0, size=12).tolist()

    res_12 = dpat(sample_12, part_value=50.0)
    assert res_12.n == 12
    assert res_12.estimator == "mad"
    assert res_12.reduced_power is True
    assert res_12.stats is not None
    assert res_12.stats.c_n == pytest.approx(MAD_FINITE_SAMPLE_CORRECTIONS[12])
    assert res_12.stats.c_n == pytest.approx(1.0766)
    assert res_12.warning is not None
    assert "Small cohort" in res_12.warning

    # Case 2: n = 40 (>= 20)
    sample_40 = rng.normal(loc=50.0, scale=3.0, size=40).tolist()
    res_40 = dpat(sample_40, part_value=50.0)
    assert res_40.n == 40
    assert res_40.estimator == "iqr"
    assert res_40.reduced_power is False
    assert res_40.stats is not None
    assert res_40.stats.c_n == pytest.approx(1.0)
    assert res_40.warning is None


@pytest.mark.fast
def test_dpat_degenerate_insufficient_cohort() -> None:
    """Cohort size n < 3 returns INSUFFICIENT_COHORT with no limits (ANOMALY_SPEC § 9)."""
    sample_small = [1.2, 1.5]
    res = dpat(sample_small, part_value=1.4)

    assert res.n == 2
    assert res.verdict == DpatVerdict.INSUFFICIENT_COHORT
    assert res.limit_low is None
    assert res.limit_high is None
    assert res.robust_sigma is None
    assert res.z is None
    assert res.estimator == "none"
    assert res.warning is not None
    assert "insufficient" in res.warning.lower()


@pytest.mark.fast
def test_dpat_degenerate_no_variation() -> None:
    """All identical readings return NO_VARIATION and z=0.0 if part==median (ANOMALY_SPEC § 9)."""
    sample_identical = [25.0] * 30

    # Candidate matches median identically
    res_match = dpat(sample_identical, part_value=25.0)
    assert res_match.verdict == DpatVerdict.NO_VARIATION
    assert res_match.limit_low is None
    assert res_match.limit_high is None
    assert res_match.robust_sigma == 0.0
    assert res_match.z == 0.0
    assert res_match.zero_iqr is True

    # Candidate differs from identical cohort
    res_diff = dpat(sample_identical, part_value=30.0)
    assert res_diff.verdict == DpatVerdict.NO_VARIATION
    assert res_diff.z is None
    assert res_diff.zero_iqr is True


@pytest.mark.fast
def test_dpat_small_cohort_zero_mad_fallback_no_inf() -> None:
    """Small cohort with MAD==0 and IQR>0 must fall back to IQR without emitting inf (TEST-001)."""
    # 10 samples (< 20): 6 ties at median 10.0, but extremities exist (IQR = 7.5 > 0, MAD = 0.0)
    cohort = [1.0] + [10.0] * 6 + [20.0] * 3
    res = dpat_limits(cohort, part_value=25.0)

    assert res.z is not None
    assert res.robust_sigma is not None
    assert not math.isinf(res.z)
    assert not math.isnan(res.z)
    assert res.robust_sigma > 0.0
    assert res.estimator == "iqr"
    assert res.reduced_power is True
    # Inside limits [-23.33, 43.33] => PASS
    assert res.verdict == DpatVerdict.PASS

    # Value outside limits => FAIL, finite z
    res_fail = dpat_limits(cohort, part_value=50.0)
    assert res_fail.z is not None
    assert not math.isinf(res_fail.z)
    assert res_fail.verdict == DpatVerdict.FAIL


@pytest.mark.fast
def test_dpat_unscored_part_value_none_returns_none_verdict() -> None:
    """When part_value is None, limits are returned but part verdict is None (TEST-003)."""
    cohort = [10.0, 11.0, 12.0, 13.0, 14.0]
    res = dpat_limits(cohort, part_value=None)

    assert res.z is None
    assert res.verdict is None
    assert res.limit_low is not None
    assert res.limit_high is not None


@pytest.mark.fast
def test_dpat_non_finite_part_value_rejected_with_fail() -> None:
    """Candidate part_value with NaN or Inf is rejected with FAIL and z=None (TEST-004)."""
    cohort = [10.0, 11.0, 12.0, 13.0, 14.0]

    # NaN candidate reading
    res_nan = dpat_limits(cohort, part_value=float("nan"))
    assert res_nan.verdict == DpatVerdict.FAIL
    assert res_nan.z is None
    assert res_nan.warning is not None
    assert "non-finite" in res_nan.warning.lower()

    # Inf candidate reading
    res_inf = dpat_limits(cohort, part_value=float("inf"))
    assert res_inf.verdict == DpatVerdict.FAIL
    assert res_inf.z is None
