"""Property tests for population shape estimation (T-306, FR-302).

Pins DRIFT_SPEC § 4 invariants:
  - TEST-DRIFT-001: Phi_g(24) == 1 exactly for every fitted shape family.
  - TEST-DRIFT-002: for Phi(168) > 0, V_hat_168 is monotone in (v24 - v0).
  - TEST-DRIFT-008: Phi(168) == 7 reduces exactly to linear extrapolation.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from backend.core.forecast import forecast_v168
from backend.core.shape import phi_at


@pytest.mark.property
@settings(max_examples=100)
@given(
    phi_168=st.floats(min_value=0.5, max_value=7.0, allow_nan=False, allow_infinity=False),
    tau=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    exponent=st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False),
)
def test_phi_at_24_is_exactly_one(phi_168: float, tau: float, exponent: float) -> None:
    """TEST-DRIFT-001: normalisation Phi_g(24) == 1 for every shape family."""
    assert phi_at(24.0, phi_168, family="power_law") == 1.0
    assert phi_at(24.0, phi_168, family="empirical") == 1.0
    assert phi_at(24.0, None, family="power_law", family_param=exponent) == 1.0
    assert phi_at(24.0, None, family="linear") == 1.0
    assert phi_at(24.0, None, family="log_time", family_param=tau) == 1.0
    assert phi_at(24.0, None, family="saturating", family_param=tau) == 1.0


@pytest.mark.property
@settings(max_examples=100)
@given(
    v0=st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    amp_lo=st.floats(min_value=-50.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    amp_gap=st.floats(min_value=0.01, max_value=50.0, allow_nan=False, allow_infinity=False),
    phi_168=st.floats(min_value=0.1, max_value=7.0, allow_nan=False, allow_infinity=False),
)
def test_forecast_monotone_in_amplitude(
    v0: float, amp_lo: float, amp_gap: float, phi_168: float
) -> None:
    """TEST-DRIFT-002: for Phi(168) > 0, V_hat_168 rises with (v24 - v0)."""
    amp_hi = amp_lo + amp_gap
    res_lo = forecast_v168(v0, v0 + amp_lo, phi_168)
    res_hi = forecast_v168(v0, v0 + amp_hi, phi_168)
    assert res_lo.refusal_code is None and res_hi.refusal_code is None
    assert res_lo.point is not None and res_hi.point is not None
    assert res_hi.point > res_lo.point


@pytest.mark.property
@settings(max_examples=100)
@given(
    v0=st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    amplitude=st.floats(
        min_value=-50.0, max_value=50.0, allow_nan=False, allow_infinity=False
    ).filter(lambda a: abs(a) > 0.01),
)
def test_reduces_to_linear_at_phi_168_equals_7(v0: float, amplitude: float) -> None:
    """TEST-DRIFT-008: Phi(168) == 7 reproduces v0 + 7 * (v24 - v0)."""
    res = forecast_v168(v0, v0 + amplitude, 7.0)
    assert res.refusal_code is None
    assert res.point is not None and res.baseline_linear is not None
    assert res.shape_point is not None
    assert res.point == res.baseline_linear == res.shape_point
    assert res.point == pytest.approx(v0 + 7.0 * amplitude)
