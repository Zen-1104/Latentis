"""Property tests for CUSUM determinism, finiteness, and monotonicity (T-408).

Implements TEST-CUSUM-008 (bitwise-identical replay) and TEST-CUSUM-010
(finite outputs, signal/crossing consistency, count accounting, and
weak monotonicity of the high accumulator in the deviations).
"""

from __future__ import annotations

import math

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from backend.core.cusum import cusum_evidence

FINITE_FLOATS = st.floats(min_value=-1.0e6, max_value=1.0e6, allow_nan=False, allow_infinity=False)
OBSERVATION = st.one_of(FINITE_FLOATS, st.none())


@pytest.mark.property
@settings(max_examples=100)
@given(
    values=st.lists(OBSERVATION, min_size=0, max_size=30),
    reference=FINITE_FLOATS,
    scale=st.floats(min_value=0.1, max_value=1.0e6, allow_nan=False, allow_infinity=False),
)
def test_cusum_deterministic_repeated_execution(
    values: list[float | None], reference: float, scale: float
) -> None:
    """TEST-CUSUM-008: identical inputs replay bitwise-identically."""
    first = cusum_evidence(values, reference, scale)
    second = cusum_evidence(list(values), reference, scale)
    third = cusum_evidence(tuple(values), reference, scale)
    assert first == second == third


@pytest.mark.property
@settings(max_examples=100)
@given(
    values=st.lists(OBSERVATION, min_size=0, max_size=30),
    reference=FINITE_FLOATS,
    scale=st.floats(min_value=0.1, max_value=1.0e6, allow_nan=False, allow_infinity=False),
)
def test_cusum_finite_consistent_and_monotone(
    values: list[float | None], reference: float, scale: float
) -> None:
    """TEST-CUSUM-010: finiteness, signal/crossing/count consistency."""
    res = cusum_evidence(values, reference, scale)
    n_gaps = sum(1 for v in values if v is None)
    n_obs = len(values) - n_gaps
    assert res.n_observations == n_obs and res.n_gaps == n_gaps
    assert math.isfinite(res.k) and math.isfinite(res.h)
    if n_obs < 3:
        assert res.refusal_code == "INSUFFICIENT_DATA"
        assert res.s_high is None and res.s_low is None
        return
    assert res.refusal_code is None
    assert res.s_high is not None and res.s_low is not None
    assert math.isfinite(res.s_high) and math.isfinite(res.s_low)
    assert res.s_high >= 0.0 and res.s_low >= 0.0
    assert res.signal_high == (res.first_crossing_high is not None)
    assert res.signal_low == (res.first_crossing_low is not None)
    if res.first_crossing_high is not None:
        assert 0 <= res.first_crossing_high < len(values)
        assert values[res.first_crossing_high] is not None
    if res.first_crossing_low is not None:
        assert 0 <= res.first_crossing_low < len(values)
        assert values[res.first_crossing_low] is not None

    # Weak monotonicity: pointwise-larger non-negative deviations (same gaps)
    # weakly dominate the high accumulator and never shrink a crossing to None.
    lifted = [(v + 1.0 if v is not None and v >= reference else v) for v in values]
    lifted_res = cusum_evidence(lifted, reference, scale)
    assert lifted_res.refusal_code is None
    assert lifted_res.s_high is not None and res.s_high is not None
    assert lifted_res.s_high >= res.s_high
    if res.signal_high:
        assert lifted_res.signal_high
