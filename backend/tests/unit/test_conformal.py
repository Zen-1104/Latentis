"""Unit tests for the split-conformal upper bound (T-308, FR-305).

Implements TEST-CONF-001 (the ``+1`` order statistic) and TEST-CONF-005
(known-answer naming ``conformal_upper`` for QG-CORE-01), plus INFINITE,
degenerate, and determinism cases per CONFORMAL_SPEC § 2.
"""

from __future__ import annotations

import math

import pytest

from backend.core.conformal import conformal_upper


@pytest.mark.fast
def test_ceil_n_plus_1_order_statistic() -> None:
    """TEST-CONF-001: 9 residuals at alpha=0.10 give k=ceil(10*0.9)=9."""
    residuals = [-2.1, -0.5, 0.3, 1.2, 2.0, 3.1, 4.4, 5.9, 7.5]
    res = conformal_upper(32.3, [residuals], alpha=0.10)
    assert res.refusal_code is None
    assert res.bound_finite is True
    assert res.n_cal == 9
    assert res.k == 9
    assert res.q_hat == pytest.approx(7.5)
    assert res.upper == pytest.approx(39.8)
    assert res.mondrian_level == 0


@pytest.mark.fast
def test_conformal_upper_direct_quantile_beside_hand_case() -> None:
    """TEST-CONF-005: conformal_upper quartile wiring on a 4-point hand case."""
    residuals = [1.0, 2.0, 3.0, 4.0]
    # n=4, alpha=0.5 -> k=ceil(5*0.5)=3 -> q_hat=3.0 -> upper=13.0.
    res = conformal_upper(10.0, [residuals], alpha=0.5)
    assert res.refusal_code is None
    assert res.n_cal == 4 and res.k == 3
    assert res.q_hat == pytest.approx(3.0)
    assert res.upper == pytest.approx(13.0)
    assert res.point == pytest.approx(10.0)
    assert res.mondrian_level == 0
    assert res.bound_finite is True
    assert res.q_hat is not None and math.isfinite(res.q_hat)


@pytest.mark.fast
def test_unattainable_alpha_is_infinite_not_max() -> None:
    """k > n reports INFINITE with attainable_alpha instead of the maximum."""
    residuals = [1.0, 2.0, 3.0, 4.0]
    # n=4, alpha=0.05 -> k=ceil(5*0.95)=5 > 4.
    res = conformal_upper(10.0, [residuals], alpha=0.05)
    assert res.refusal_code == "INSUFFICIENT_CALIBRATION"
    assert res.bound_finite is False
    assert res.upper is None
    assert res.q_hat is None
    assert res.attainable_alpha == pytest.approx(1.0 / 5.0)
    assert res.mondrian_level == 3


@pytest.mark.fast
def test_nonfinite_point_and_alpha_refuse() -> None:
    """A non-finite point or an alpha outside (0, 1) yields no bound."""
    assert conformal_upper(None, [[1.0, 2.0]], alpha=0.1).refusal_code == "INVALID_INPUT"
    assert conformal_upper(float("nan"), [[1.0, 2.0]], alpha=0.1).refusal_code == "INVALID_INPUT"
    assert conformal_upper(10.0, [[1.0, 2.0]], alpha=0.0).refusal_code == "INVALID_INPUT"
    assert conformal_upper(10.0, [[1.0, 2.0]], alpha=1.0).refusal_code == "INVALID_INPUT"


@pytest.mark.fast
def test_nonfinite_residuals_skipped_with_warning() -> None:
    """NaN/inf calibration residuals never enter the order statistic."""
    res = conformal_upper(10.0, [[1.0, float("nan"), 2.0, 3.0]], alpha=0.5)
    assert res.refusal_code is None
    assert res.n_cal == 3
    assert res.warning is not None and "non-finite" in res.warning


@pytest.mark.fast
def test_deterministic_repeated_execution() -> None:
    """INV-8: identical calibration gives an identical bound twice."""
    residuals = [0.3, -0.5, 7.5, 1.2, 3.1]
    first = conformal_upper(32.3, [residuals], alpha=0.1)
    second = conformal_upper(32.3, [residuals], alpha=0.1)
    assert first == second


@pytest.mark.fast
def test_row_permutation_invariance() -> None:
    """Calibration order never moves the bound (sorting is canonical)."""
    residuals = [0.3, -0.5, 7.5, 1.2, 3.1, 2.0, 4.4, 5.9, -2.1, 0.0]
    assert (
        conformal_upper(5.0, [residuals], alpha=0.2).upper
        == conformal_upper(5.0, [list(reversed(residuals))], alpha=0.2).upper
    )
