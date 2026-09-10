"""Property and adversarial tests for robust Mahalanobis and additive decomposition (T-304).

Asserts non-negotiable invariants:
  - Strict row permutation invariance
  - Component-ID permutation invariance (INV-2)
  - Deterministic repeated execution (INV-8)
  - Parameter (column) permutation equivariance
  - Differential additive decomposition identity across Hypothesis-generated spaces
  - Numerical stability under singular covariance, near-constant cohorts, and extreme finite values
  - Strict absence of NaN or inf in decision-bearing numeric outputs (ANOMALY_SPEC § 9, RT-009)
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.core.constants import SUM_CHECK_TOLERANCE
from backend.core.multivariate import mahalanobis


@pytest.mark.fast
def test_mahalanobis_row_permutation_invariance() -> None:
    """Permuting the row order of a cohort must yield identical D² and contributions."""
    rng = np.random.default_rng(1001)
    n = 40
    p = 3
    cohort = rng.normal(loc=5.0, scale=2.0, size=(n, p))
    candidate = np.array([7.0, 4.0, 6.0])
    names = ["param_a", "param_b", "param_c"]

    baseline = mahalanobis(cohort, part_value=candidate, parameter_names=names)
    assert baseline.d2 is not None

    # Test across 10 random permutations of cohort rows
    for i in range(10):
        perm = rng.permutation(n)
        cohort_perm = cohort[perm]
        res_perm = mahalanobis(cohort_perm, part_value=candidate, parameter_names=names)

        assert res_perm.d2 is not None
        assert (
            abs(res_perm.d2 - baseline.d2) < 1e-10
        ), f"Row permutation {i} changed D²: {res_perm.d2} vs {baseline.d2}"
        assert baseline.p_value is not None and res_perm.p_value is not None
        assert abs(res_perm.p_value - baseline.p_value) < 1e-10

        assert baseline.contributions is not None and res_perm.contributions is not None
        for c_base, c_perm in zip(baseline.contributions, res_perm.contributions, strict=True):
            assert abs(c_base.contribution - c_perm.contribution) < 1e-10
            assert abs(c_base.share - c_perm.share) < 1e-10


@pytest.mark.fast
def test_component_id_permutation_invariance() -> None:
    """Component-ID permutation invariance (INV-2 / RT-004) with leave-one-out cohort.

    Bijectively permuting component IDs must leave Mahalanobis distance unchanged.
    """
    rng = np.random.default_rng(2002)
    n_parts = 35
    p = 2
    raw_values = rng.normal(loc=10.0, scale=1.5, size=(n_parts, p))

    # Construct records for two parameters across n_parts
    records: list[dict[str, object]] = []
    for i in range(n_parts):
        cid = f"PART_{i:04d}"
        records.append(
            {
                "component_id": cid,
                "param_x": raw_values[i, 0],
                "param_y": raw_values[i, 1],
            }
        )

    target_id = "PART_0000"
    target_x = np.array([raw_values[0, 0], raw_values[0, 1]])

    # Build cohort excluding target part
    cohort_x = np.array([r["param_x"] for r in records if r["component_id"] != target_id])
    cohort_y = np.array([r["param_y"] for r in records if r["component_id"] != target_id])
    cohort_matrix = np.column_stack([cohort_x, cohort_y])

    res_base = mahalanobis(cohort_matrix, part_value=target_x, parameter_names=["x", "y"])

    # Permute component IDs via bijective mapping
    perm_cids = rng.permutation([f"PART_{i:04d}" for i in range(n_parts)]).tolist()
    perm_records: list[dict[str, object]] = []
    target_new_id = perm_cids[0]
    for i in range(n_parts):
        perm_records.append(
            {
                "component_id": perm_cids[i],
                "param_x": raw_values[i, 0],
                "param_y": raw_values[i, 1],
            }
        )

    perm_cohort_x = np.array(
        [r["param_x"] for r in perm_records if r["component_id"] != target_new_id]
    )
    perm_cohort_y = np.array(
        [r["param_y"] for r in perm_records if r["component_id"] != target_new_id]
    )
    perm_cohort_matrix = np.column_stack([perm_cohort_x, perm_cohort_y])

    res_perm = mahalanobis(perm_cohort_matrix, part_value=target_x, parameter_names=["x", "y"])

    assert res_base.d2 is not None and res_perm.d2 is not None
    assert abs(res_base.d2 - res_perm.d2) < 1e-10


@pytest.mark.fast
def test_mahalanobis_deterministic_repeated_execution() -> None:
    """Repeated execution on identical inputs produces identical outputs (INV-8)."""
    rng = np.random.default_rng(3003)
    cohort = rng.normal(size=(45, 3))
    candidate = np.array([1.5, -0.5, 2.0])

    run1 = mahalanobis(cohort, part_value=candidate)
    for _ in range(5):
        run_i = mahalanobis(cohort, part_value=candidate)
        assert run1.d2 == run_i.d2
        assert run1.p_value == run_i.p_value
        assert run1.location == run_i.location
        assert run1.covariance == run_i.covariance
        assert run1.precision == run_i.precision


@pytest.mark.fast
def test_mahalanobis_parameter_permutation_equivariance() -> None:
    """Permuting feature columns permutes contribution vectors equivariantly."""
    rng = np.random.default_rng(4004)
    n = 50
    cohort = rng.normal(loc=[10.0, 20.0, 30.0], scale=[1.0, 2.0, 3.0], size=(n, 3))
    candidate = np.array([12.0, 25.0, 28.0])
    names = ["param_0", "param_1", "param_2"]

    res_original = mahalanobis(cohort, part_value=candidate, parameter_names=names)
    assert res_original.d2 is not None
    assert res_original.contributions is not None

    # Permute columns: (0, 1, 2) -> (2, 0, 1)
    perm_order = [2, 0, 1]
    cohort_perm = cohort[:, perm_order]
    candidate_perm = candidate[perm_order]
    names_perm = [names[i] for i in perm_order]

    res_perm = mahalanobis(cohort_perm, part_value=candidate_perm, parameter_names=names_perm)
    assert res_perm.d2 is not None
    assert res_original.contributions is not None
    assert res_perm.contributions is not None

    # Check contributions by parameter name
    orig_by_name = {c.parameter: c.contribution for c in res_original.contributions}
    perm_by_name = {c.parameter: c.contribution for c in res_perm.contributions}
    for name in names:
        assert abs(orig_by_name[name] - perm_by_name[name]) < 1e-9


@settings(max_examples=50, deadline=1000)
@given(
    st.integers(min_value=2, max_value=4),
    st.integers(min_value=25, max_value=50),
    st.integers(min_value=1, max_value=10000),
)
def test_additive_decomposition_identity_hypothesis(p: int, n: int, seed: int) -> None:
    """Hypothesis property test: additive decomposition identically sums to D²."""
    rng = np.random.default_rng(seed)
    mean = rng.uniform(-10.0, 10.0, size=p)
    # Generate random positive definite covariance matrix
    a = rng.normal(size=(p, p))
    cov = a @ a.T + np.eye(p) * 1.5
    cohort = rng.multivariate_normal(mean, cov, size=n)

    candidate = rng.uniform(-15.0, 15.0, size=p)
    res = mahalanobis(cohort, part_value=candidate)

    if res.refusal_code is None and res.d2 is not None and res.contributions is not None:
        contrib_sum = sum(c.contribution for c in res.contributions)
        assert abs(contrib_sum - res.d2) <= SUM_CHECK_TOLERANCE
        assert math.isfinite(res.d2)
        assert res.p_value is not None and math.isfinite(res.p_value)
        assert 0.0 <= res.p_value <= 1.0


@pytest.mark.fast
def test_adversarial_singular_and_collinear_cohorts() -> None:
    """Adversarial degenerate covariance cases must refuse gracefully with zero NaN/inf."""
    rng = np.random.default_rng(5005)
    n = 35

    # 1. Perfectly collinear features (col2 = 2 * col1)
    c1 = rng.normal(size=n)
    c2 = 2.0 * c1
    cohort_collinear = np.column_stack([c1, c2])
    res_collinear = mahalanobis(cohort_collinear, part_value=[1.0, 2.0])
    assert res_collinear.refusal_code == "SINGULAR_COVARIANCE"
    assert res_collinear.d2 is None

    # 2. Duplicate rows: n-1 rows identical, 1 row distinct
    cohort_tied = np.zeros((n, 2))
    cohort_tied[0] = [1.0, 1.0]
    res_tied = mahalanobis(cohort_tied, part_value=[2.0, 2.0])
    assert res_tied.refusal_code in ("SINGULAR_COVARIANCE", "NO_VARIATION")
    assert res_tied.d2 is None

    # 3. Three-way collinearity (col3 = col1 + col2)
    c3 = c1 + c2
    cohort_3d_singular = np.column_stack([c1, c2, c3])
    res_3d = mahalanobis(cohort_3d_singular, part_value=[1.0, 2.0, 3.0])
    assert res_3d.refusal_code == "SINGULAR_COVARIANCE"
    assert res_3d.d2 is None


@pytest.mark.fast
def test_adversarial_nan_inf_inputs() -> None:
    """Adversarial non-finite inputs must be rejected without NaN/inf emission."""
    rng = np.random.default_rng(6006)
    cohort = rng.normal(size=(30, 2))

    for bad_val in [float("nan"), float("inf"), float("-inf")]:
        res = mahalanobis(cohort, part_value=[bad_val, 1.0])
        assert res.refusal_code == "INVALID_INPUT"
        assert res.d2 is None
        assert res.p_value is None
        assert res.contributions is None


@pytest.mark.fast
def test_adversarial_extreme_magnitudes() -> None:
    """Extreme float magnitudes (1e-15 to 1e15) compute finite and stable outputs."""
    rng = np.random.default_rng(7007)
    for scale in [1e-15, 1e-8, 1e3, 1e12]:
        cohort = rng.normal(loc=10.0 * scale, scale=scale, size=(30, 2))
        candidate = np.array([12.0 * scale, 9.0 * scale])
        res = mahalanobis(cohort, part_value=candidate)
        assert res.refusal_code is None
        assert res.d2 is not None
        assert math.isfinite(res.d2)
        assert res.p_value is not None
        assert math.isfinite(res.p_value)
