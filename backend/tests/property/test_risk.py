"""Property tests for the risk decomposition (T-311, FR-401/FR-402).

Implements TEST-RISK-001 (adding-up within 1e-9 over Hypothesis inputs),
TEST-RISK-002 (no weight vector moves the echoed band), and TEST-RISK-006
(determinism, finiteness, and refusal discipline naming ``compute_risk``).
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from backend.core.attribution import AttributionVerdict
from backend.core.risk import RiskWeights, compute_risk
from backend.core.safety import SafetyResult, evaluate_safety

ATTRIBUTIONS = st.sampled_from(["PART", "SOCKET", "ZONE", "TESTER", "INDETERMINATE"])


def _safety_for(slope_target: float) -> SafetyResult:
    """Authoritative T-310 result with a controlled slope ratio."""
    # headroom 40, usable 32, safety_slope 32/168; point sets the ratio.
    point = 10.0 + slope_target * 32.0
    upper = min(45.0, 10.0 + slope_target * 32.0 + 5.0)
    return evaluate_safety(10.0, upper, point, 12.0, 50.0)


@pytest.mark.property
@settings(max_examples=120)
@given(
    z=st.floats(min_value=-12.0, max_value=12.0, allow_nan=False, allow_infinity=False),
    slope=st.floats(min_value=-1.0, max_value=4.0, allow_nan=False, allow_infinity=False),
    dq=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    attribution=ATTRIBUTIONS,
)
def test_components_sum_to_total(z: float, slope: float, dq: float, attribution: str) -> None:
    """TEST-RISK-001: printed components sum to the printed total within 1e-9."""
    res = compute_risk(z, _safety_for(slope), AttributionVerdict(attribution), dq)
    assert res.refusal_code is None
    assert abs(res.sum_check.components_sum - res.sum_check.reported_total) <= 1e-9
    assert res.sum_check.abs_diff <= 1e-9
    assert res.risk_index == pytest.approx(res.sum_check.components_sum)


@pytest.mark.property
@settings(max_examples=80)
@given(
    z=st.floats(min_value=-12.0, max_value=12.0, allow_nan=False, allow_infinity=False),
    slope=st.floats(min_value=-1.0, max_value=4.0, allow_nan=False, allow_infinity=False),
    w_a=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    w_b=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    w_m=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    w_q=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    w_c=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_weights_cannot_cross_a_band_boundary(
    z: float, slope: float, w_a: float, w_b: float, w_m: float, w_q: float, w_c: float
) -> None:
    """TEST-RISK-002: sweeping weights never moves the echoed band (RT-010)."""
    safety = _safety_for(slope)
    assert safety.band is not None
    first = compute_risk(
        z,
        safety,
        AttributionVerdict.PART,
        0.9,
        RiskWeights(w_a, w_b, w_m, w_q, w_c),
    )
    second = compute_risk(z, safety, AttributionVerdict.PART, 0.9, RiskWeights())
    assert first.refusal_code is None and second.refusal_code is None
    assert first.band == safety.band == second.band


@pytest.mark.property
@settings(max_examples=80)
@given(
    z=st.floats(min_value=-12.0, max_value=12.0, allow_nan=False, allow_infinity=False),
    slope=st.floats(min_value=0.0, max_value=3.0, allow_nan=False, allow_infinity=False),
    dq=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    attribution=ATTRIBUTIONS,
)
def test_compute_risk_deterministic_finite_and_refusing(
    z: float, slope: float, dq: float, attribution: str
) -> None:
    """TEST-RISK-006: compute_risk is deterministic, finite, and honest."""
    safety = _safety_for(slope)
    first = compute_risk(z, safety, AttributionVerdict(attribution), dq)
    second = compute_risk(z, safety, AttributionVerdict(attribution), dq)
    assert first == second
    if first.refusal_code is None:
        assert first.band == safety.band
        for comp in first.components:
            assert 0.0 <= comp.raw <= 1.0
    else:
        assert first.components == ()
        assert first.band is None
