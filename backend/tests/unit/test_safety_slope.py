"""Unit tests for the derived safety slope (T-310, FR-306).

Implements TEST-SAFE-001 and TEST-SAFE-002: the slope is derived from the
profile, never a constant in code, and an explicit delta limit takes
precedence over the margin path (DRIFT_SPEC § 6.2).
"""

from __future__ import annotations

import pytest

from backend.core.safety import evaluate_safety


@pytest.mark.fast
def test_slope_derived_from_profile_hand_computed() -> None:
    """TEST-SAFE-001: (50.0-12.1)*(1-0.20)/168 recomputed by hand."""
    res = evaluate_safety(12.1, 39.8, 32.3, 18.7, 50.0)
    assert res.refusal_code is None
    # headroom 37.9; usable 37.9*0.8 = 30.32; slope 30.32/168 = 0.180476...
    assert res.usable_margin == pytest.approx(30.32)
    assert res.safety_slope == pytest.approx(30.32 / 168.0)
    assert res.observed_early_slope == pytest.approx(6.6 / 24.0)
    assert res.predicted_long_slope == pytest.approx(20.2 / 168.0)
    assert res.predicted_margin == pytest.approx(10.2)
    assert res.predicted_margin_pct == pytest.approx(10.2 / 37.9)
    assert res.delta_max_used is False


@pytest.mark.fast
def test_explicit_delta_limit_takes_precedence() -> None:
    """TEST-SAFE-002: safety_slope = delta_max/horizon, margin path unused."""
    first = evaluate_safety(12.1, 39.8, 32.3, 18.7, 50.0, delta_max=5.0)
    assert first.refusal_code is None
    assert first.delta_max_used is True
    assert first.safety_slope == pytest.approx(5.0 / 168.0)
    # The margin reserve no longer steers the slope: varying it changes nothing.
    second = evaluate_safety(12.1, 39.8, 32.3, 18.7, 50.0, margin_fraction=0.40, delta_max=5.0)
    assert second.safety_slope == first.safety_slope
    # ...while without delta_max the same change does move the slope.
    third = evaluate_safety(12.1, 39.8, 32.3, 18.7, 50.0, margin_fraction=0.40)
    assert third.safety_slope == pytest.approx(37.9 * 0.6 / 168.0)
    assert third.safety_slope != first.safety_slope
