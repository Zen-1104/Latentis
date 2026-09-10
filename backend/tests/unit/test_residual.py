"""Unit tests for the residual-correction adoption rule (T-307, FR-304).

Implements TEST-DRIFT-005 (AG-10): a residual model that worsens calibration
MAE must fall back to the shape-only forecast with the decision recorded.
"""

from __future__ import annotations

import pytest

from backend.core.forecast import forecast_v168


@pytest.mark.fast
def test_residual_model_adopted_only_if_it_wins() -> None:
    """TEST-DRIFT-005: worsening MAE falls back to shape-only, recorded."""
    worsened = forecast_v168(
        12.1,
        18.7,
        3.06,
        residual_correction=5.0,
        shape_mae=2.0,
        residual_mae=2.5,
        seed_spread=0.1,
    )
    assert worsened.refusal_code is None
    assert worsened.residual_applied is False
    assert worsened.residual_correction == pytest.approx(0.0)
    assert worsened.point == worsened.shape_point
    assert worsened.residual_decision is not None
    assert "rejected" in worsened.residual_decision
    assert worsened.warning is not None and "AG-10" in worsened.warning

    winner = forecast_v168(
        12.1,
        18.7,
        3.06,
        residual_correction=1.1,
        shape_mae=2.0,
        residual_mae=1.0,
        seed_spread=0.1,
    )
    assert winner.residual_applied is True
    assert winner.shape_point is not None
    assert winner.point == pytest.approx(winner.shape_point + 1.1)
    assert winner.residual_decision is not None and "adopted" in winner.residual_decision


@pytest.mark.fast
def test_tie_goes_to_shape_only() -> None:
    """An improvement inside the seed spread is not an improvement (AG-10)."""
    res = forecast_v168(
        12.1,
        18.7,
        3.06,
        residual_correction=0.5,
        shape_mae=2.0,
        residual_mae=1.95,
        seed_spread=0.1,
    )
    assert res.residual_applied is False
    assert res.point == res.shape_point


@pytest.mark.fast
def test_half_supplied_mae_comparison_is_invalid() -> None:
    """A one-sided MAE comparison refuses instead of assuming the outcome."""
    res = forecast_v168(12.1, 18.7, 3.06, residual_correction=0.5, shape_mae=2.0)
    assert res.refusal_code == "INVALID_INPUT"
    assert res.point is None
