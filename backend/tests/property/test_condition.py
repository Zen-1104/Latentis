"""Property tests for condition-aware context (T-410, D-040).

Implements TEST-COND-003: bitwise-identical replay, AF monotonicity in
zone temperature, and exact unity at equal temperatures.
"""

from __future__ import annotations

import math

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from backend.core.condition import arrhenius_af, zone_arrhenius_consistent

TEMPS = st.floats(min_value=-273.0, max_value=500.0, allow_nan=False, allow_infinity=False)
POSITIVE_EA = st.floats(min_value=0.01, max_value=3.0, allow_nan=False, allow_infinity=False)


@pytest.mark.property
@settings(max_examples=100)
@given(
    zone=TEMPS,
    reference=TEMPS,
    energy=POSITIVE_EA,
    offset=st.floats(min_value=-1.0e6, max_value=1.0e6, allow_nan=False, allow_infinity=False),
    direction=st.sampled_from([1, -1]),
)
def test_condition_deterministic_and_monotone(
    zone: float, reference: float, energy: float, offset: float, direction: int
) -> None:
    """TEST-COND-003: replay-identical verdicts; AF monotone in zone heat."""
    first = zone_arrhenius_consistent(zone, reference, energy, offset, direction)
    second = zone_arrhenius_consistent(zone, reference, energy, offset, direction)
    assert first == second

    factor = arrhenius_af(zone, reference, energy)
    assert arrhenius_af(zone, reference, energy) == factor
    if factor is None:
        # Overflow/absolute-zero corner: no factor, so no thermal verdict —
        # and the refusal is the deterministic INVALID_INPUT, not a guess.
        assert first.refusal_code == "INVALID_INPUT"
        assert first.consistent is None
        return
    assert math.isfinite(factor) and factor > 0.0
    if zone == reference:
        assert factor == 1.0
        assert first.consistent is None
        assert first.refusal_code == "INSUFFICIENT_DATA"
    elif first.refusal_code is None:
        assert first.af == factor
        assert first.consistent is not None

    hotter = arrhenius_af(zone + 10.0, reference, energy)
    if hotter is None:
        # Overflow strictly above the finite factor: monotonicity holds
        # vacuously at the float64 boundary.
        return
    assert hotter >= factor
