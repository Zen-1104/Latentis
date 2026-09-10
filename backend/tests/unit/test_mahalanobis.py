"""Unit and differential tests for robust Mahalanobis distance and additive decomposition.

Implements TEST-STAT-007 (differential) and TEST-STAT-008 (known-answer), covering FR-206.
Also validates degeneracy handling, non-finite rejection, unscored cohorts, and edge cases.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from backend.core.constants import SUM_CHECK_TOLERANCE
from backend.core.dpat import DpatVerdict, dpat_limits
from backend.core.multivariate import contributions, mahalanobis


@pytest.mark.fast
def test_contributions_sum_to_d_squared() -> None:
    """TEST-STAT-007 (Differential): Contributions sum to total Mahalanobis D².

    Oracle: Two independent computations: sum of per-dimension contributions
    vs the quadratic form (x - μ)ᵀ Σ⁻¹ (x - μ), agreeing to within 1e-9.
    """
    rng = np.random.default_rng(101)
    n = 60
    p = 4
    # Generate well-conditioned synthetic multivariate normal data
    true_mean = np.array([10.0, 25.0, -5.0, 1.5])
    a = rng.normal(size=(p, p))
    true_cov = a @ a.T + np.eye(p) * 2.0
    cohort = rng.multivariate_normal(true_mean, true_cov, size=n)

    # Candidate outlier part
    candidate = np.array([14.0, 20.0, -2.0, 3.5])
    param_names = ["iddq_standby", "vth_shift", "leakage_input", "timing_delay"]

    result = mahalanobis(cohort, part_value=candidate, parameter_names=param_names)

    assert result.d2 is not None
    assert result.p_value is not None
    assert result.contributions is not None
    assert result.location is not None
    assert result.precision is not None
    assert result.refusal_code is None
    assert result.warning is None

    # Independent computation 1: direct quadratic form from raw precision matrix
    loc_arr = np.array(result.location)
    prec_arr = np.array(result.precision)
    delta = candidate - loc_arr
    quadratic_form_d2 = float(delta @ prec_arr @ delta)

    # Independent computation 2: sum of per-dimension additive contributions
    contrib_sum = sum(c.contribution for c in result.contributions)

    # Assert mutual agreement to within SUM_CHECK_TOLERANCE (1e-9)
    assert abs(contrib_sum - quadratic_form_d2) <= SUM_CHECK_TOLERANCE, (
        f"Differential mismatch: sum of contributions ({contrib_sum}) != "
        f"quadratic form ({quadratic_form_d2}), diff = {abs(contrib_sum - quadratic_form_d2)}"
    )
    assert abs(result.d2 - quadratic_form_d2) <= SUM_CHECK_TOLERANCE
    assert abs(result.d2 - contrib_sum) <= SUM_CHECK_TOLERANCE

    # Verify each individual contribution formula: c_q = (x - μ)_q * [Σ⁻¹ (x - μ)]_q
    weights = prec_arr @ delta
    for q, c in enumerate(result.contributions):
        expected_cq = float(delta[q] * weights[q])
        assert abs(c.contribution - expected_cq) <= SUM_CHECK_TOLERANCE
        assert c.parameter == param_names[q]
        assert abs(c.delta - delta[q]) <= SUM_CHECK_TOLERANCE
        assert abs(c.weight - weights[q]) <= SUM_CHECK_TOLERANCE
        expected_share = expected_cq / result.d2 if result.d2 > 0 else 0.0
        assert abs(c.share - expected_share) <= SUM_CHECK_TOLERANCE


@pytest.mark.fast
def test_joint_only_anomaly_detected_when_marginals_pass() -> None:
    """TEST-STAT-008 (Known-Answer): Joint-only anomaly detected when marginals pass DPAT.

    Oracle: A hand-constructed 2-D cohort where both marginals are inside their
    DPAT limits and the joint distance is an extreme outlier (ANOMALY_SPEC § 4.5,
    DATA_GENERATION_SPEC § 5.1).
    """
    rng = np.random.default_rng(202)
    n = 50
    # Strongly positively correlated bivariate distribution (r ≈ 0.95)
    r = 0.95
    cov_matrix = np.array([[1.0, r], [r, 1.0]])
    mean_vec = np.array([0.0, 0.0])

    # Sample cohort
    cohort = rng.multivariate_normal(mean_vec, cov_matrix, size=n)

    # Candidate part with off-manifold anti-correlated values
    # In marginals: x1 = 2.0, x2 = -2.0 (both within ±6 sigma of DPAT)
    part = np.array([2.0, -2.0])
    param_names = ["param_x", "param_y"]

    # 1. Evaluate marginal DPAT limits
    dpat_x = dpat_limits(cohort[:, 0], part_value=part[0])
    dpat_y = dpat_limits(cohort[:, 1], part_value=part[1])

    # Both marginals must pass DPAT window
    assert dpat_x.verdict == DpatVerdict.PASS
    assert dpat_y.verdict == DpatVerdict.PASS
    assert dpat_x.z is not None and abs(dpat_x.z) < 3.0  # Inside nominal band
    assert dpat_y.z is not None and abs(dpat_y.z) < 3.0  # Inside nominal band

    # 2. Evaluate joint robust Mahalanobis
    result = mahalanobis(cohort, part_value=part, parameter_names=param_names)

    assert result.d2 is not None
    assert result.p_value is not None
    assert result.refusal_code is None

    # Theoretical expected D² for [2, -2] under cov [[1, 0.95], [0.95, 1]]:
    # D² = 2 * (1 / (1 - 0.95²)) * (2² + (-2)² - 2*0.95*(2)*(-2))
    #    = (1 / 0.0975) * (4 + 4 + 7.6) = 15.6 / 0.0975 = 160.0
    # Joint distance should be very large (> 50) and p-value extremely small (< 1e-6)
    assert result.d2 > 50.0, f"Expected large D², got {result.d2}"
    assert result.p_value < 1e-6, f"Expected tiny p-value, got {result.p_value}"

    # Verify both parameters contribute equally to breaking the correlation
    assert result.contributions is not None
    assert len(result.contributions) == 2
    c_x = result.contributions[0].contribution
    c_y = result.contributions[1].contribution
    assert c_x > 0.0 and c_y > 0.0
    assert abs(c_x - c_y) / result.d2 < 0.05  # Symmetric shares ≈ 50% each


@pytest.mark.fast
def test_mahalanobis_unscored_part_value_none() -> None:
    """Cohort-only evaluation when part_value is None."""
    rng = np.random.default_rng(303)
    cohort = rng.normal(size=(30, 2))
    result = mahalanobis(cohort, part_value=None)

    assert result.d2 is None
    assert result.p_value is None
    assert result.contributions is None
    assert result.refusal_code is None
    assert result.warning is None
    assert result.location is not None
    assert result.covariance is not None
    assert result.precision is not None
    assert len(result.location) == 2
    assert len(result.covariance) == 2


@pytest.mark.fast
def test_mahalanobis_insufficient_cohort_sample_size() -> None:
    """Cohort size n < MIN_COHORT_SIZE or n <= p must return INSUFFICIENT_COHORT."""
    # n = 2 < 3
    cohort_small = np.array([[1.0, 2.0], [3.0, 4.0]])
    res = mahalanobis(cohort_small, part_value=[2.0, 3.0])
    assert res.refusal_code == "INSUFFICIENT_COHORT"
    assert res.d2 is None
    assert res.warning is not None


@pytest.mark.fast
def test_mahalanobis_insufficient_sample_ratio() -> None:
    """Cohort size n < MIN_COV_DET_SAMPLE_FACTOR * p must return INSUFFICIENT_SAMPLE_RATIO."""
    # p = 3 -> requires n >= 5 * 3 = 15
    # Provide n = 12 (< 15)
    rng = np.random.default_rng(404)
    cohort = rng.normal(size=(12, 3))
    res = mahalanobis(cohort, part_value=[0.0, 0.0, 0.0])
    assert res.refusal_code == "INSUFFICIENT_SAMPLE_RATIO"
    assert res.d2 is None
    assert "required for MinCovDet" in str(res.warning)


@pytest.mark.fast
def test_mahalanobis_no_variation_cohort() -> None:
    """Cohort with identical rows must return NO_VARIATION refusal without NaN/inf."""
    cohort = np.tile([5.0, 10.0, -3.0], (25, 1))
    res = mahalanobis(cohort, part_value=[5.0, 10.0, -3.0])
    assert res.refusal_code == "NO_VARIATION"
    assert res.d2 is None
    assert res.p_value is None
    assert res.covariance is None
    assert res.location == (5.0, 10.0, -3.0)


@pytest.mark.fast
def test_mahalanobis_singular_covariance_collinear() -> None:
    """Cohort with perfectly collinear or constant columns returns SINGULAR_COVARIANCE."""
    rng = np.random.default_rng(505)
    x1 = rng.normal(size=25)
    # Column 2 has zero variance
    x2 = np.full(25, 3.14)
    cohort = np.column_stack([x1, x2])

    res = mahalanobis(cohort, part_value=[1.0, 3.14], parameter_names=["param_1", "param_const"])
    assert res.refusal_code == "SINGULAR_COVARIANCE"
    assert res.d2 is None
    assert "zero variance" in str(res.warning)


@pytest.mark.fast
def test_mahalanobis_non_finite_candidate_rejected() -> None:
    """Candidate part vector containing NaN or Inf is rejected with INVALID_INPUT."""
    rng = np.random.default_rng(606)
    cohort = rng.normal(size=(25, 2))

    # Candidate with NaN
    res_nan = mahalanobis(cohort, part_value=[1.0, float("nan")])
    assert res_nan.refusal_code == "INVALID_INPUT"
    assert res_nan.d2 is None
    assert res_nan.p_value is None
    assert res_nan.contributions is None

    # Candidate with +inf
    res_inf = mahalanobis(cohort, part_value=[float("inf"), 2.0])
    assert res_inf.refusal_code == "INVALID_INPUT"
    assert res_inf.d2 is None


@pytest.mark.fast
def test_mahalanobis_cohort_with_nan_filtered() -> None:
    """Cohort containing some NaN rows filters them; clean rows are used."""
    rng = np.random.default_rng(707)
    clean_cohort = rng.normal(size=(25, 2))
    dirty_cohort = np.vstack([clean_cohort, [[np.nan, 1.0]], [[2.0, np.inf]]])

    res = mahalanobis(dirty_cohort, part_value=[0.0, 0.0])
    assert res.refusal_code is None
    assert res.n == 25
    assert res.d2 is not None


@pytest.mark.fast
def test_mahalanobis_extreme_finite_values() -> None:
    """Extreme finite float values within physically meaningful ranges remain stable."""
    rng = np.random.default_rng(808)
    # Scale cohort to 1e-12 (e.g. picoampere leakage currents)
    scale = 1e-12
    cohort = rng.normal(loc=10.0 * scale, scale=scale, size=(30, 2))
    candidate = np.array([12.0 * scale, 9.0 * scale])

    res = mahalanobis(cohort, part_value=candidate)
    assert res.refusal_code is None
    assert res.d2 is not None
    assert math.isfinite(res.d2)
    assert res.p_value is not None
    assert math.isfinite(res.p_value)


@pytest.mark.fast
def test_top_contributions_ordering() -> None:
    """_top_contributions method returns contributions ordered by absolute magnitude."""
    rng = np.random.default_rng(909)
    cohort = rng.normal(size=(35, 3))
    # Make candidate heavily deviated along parameter 2
    candidate = np.array([0.1, 5.0, 0.2])
    names = ["leakage_a", "leakage_b", "leakage_c"]

    res = mahalanobis(cohort, part_value=candidate, parameter_names=names)
    assert res.contributions is not None

    top = res._top_contributions()
    assert len(top) == 3
    # Top contributor should be leakage_b
    assert top[0]["parameter"] == "leakage_b"
    assert abs(top[0]["contribution"]) >= abs(top[1]["contribution"])
    assert abs(top[1]["contribution"]) >= abs(top[2]["contribution"])

    # Limit to top 1
    top1 = res._top_contributions(limit=1)
    assert len(top1) == 1
    assert top1[0]["parameter"] == "leakage_b"


@pytest.mark.fast
def test_contributions_direct_call() -> None:
    """Direct call to contributions function validates formula and error cases."""
    x = [2.0, 3.0]
    loc = [1.0, 1.0]
    prec = [[2.0, 0.0], [0.0, 1.0]]

    # delta = [1.0, 2.0]
    # w = [2.0, 2.0]
    # c1 = 1.0 * 2.0 = 2.0
    # c2 = 2.0 * 2.0 = 4.0
    # total = 6.0
    contribs = contributions(x, loc, prec, parameter_names=["p1", "p2"])
    assert len(contribs) == 2
    assert contribs[0].contribution == 2.0
    assert contribs[1].contribution == 4.0
    assert abs(contribs[0].share - 2.0 / 6.0) < 1e-9
    assert abs(contribs[1].share - 4.0 / 6.0) < 1e-9

    # Mismatched dimension raises ValueError
    with pytest.raises(ValueError, match="Dimension mismatch"):
        contributions([1.0], loc, prec)
