"""Unit tests for the four safety bands (T-310, FR-306/FR-307/FR-310).

Implements TEST-SAFE-003 (one hand-constructed case per band row including
both boundary values), TEST-SAFE-004 (the band reads the bound, never the
point — RT-005 at unit level), and TEST-SAFE-005 (known-answer-adjacent
property naming ``evaluate_safety`` for QG-CORE-01: finite, deterministic,
conservative refusals).
"""

from __future__ import annotations

import dataclasses
import math

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from backend.core.safety import evaluate_safety


def _assert_all_finite(res: object) -> None:
    """Every float on the result is finite or None (never NaN/inf)."""
    for field_info in dataclasses.fields(res):  # type: ignore[arg-type]
        value = getattr(res, field_info.name)
        if isinstance(value, float):
            assert math.isfinite(value), f"{field_info.name} is non-finite"


@pytest.mark.fast
def test_all_four_band_rows() -> None:
    """TEST-SAFE-003: SAFE / WATCH / EARLY_WARNING / REJECT by hand."""
    # SAFE: bound below the reserve threshold (18.0) and ratio 0.0625 < 0.7.
    safe = evaluate_safety(10.0, 15.0, 12.0, 11.0, 50.0)
    assert safe.refusal_code is None and safe.band == "SAFE"

    # WATCH: ratio 0.75 inside [0.7, 1.0).
    # headroom 40, usable 32, safety 32/168; point 34 -> long 24/168, ratio 0.75.
    watch = evaluate_safety(10.0, 30.0, 34.0, 12.0, 50.0)
    assert watch.refusal_code is None and watch.band == "WATCH"
    assert watch.slope_ratio == pytest.approx(0.75)

    # WATCH at the 0.7 edge: point-v0 = 5.6 over headroom 10 (40->50).
    edge_watch = evaluate_safety(40.0, 45.0, 45.6, 41.0, 50.0)
    assert edge_watch.refusal_code is None and edge_watch.band == "WATCH"

    # EARLY_WARNING at the exact 1.0 edge: point-v0 == headroom*(1-mf).
    edge_early = evaluate_safety(10.0, 45.0, 42.0, 12.0, 50.0)
    assert edge_early.refusal_code is None
    assert edge_early.slope_ratio == 1.0
    assert edge_early.band == "EARLY_WARNING"

    # EARLY_WARNING interior: ratio 1.5 while the bound stays inside the limit.
    early = evaluate_safety(10.0, 45.0, 58.0, 14.0, 60.0)
    assert early.refusal_code is None and early.band == "EARLY_WARNING"

    # REJECT at the boundary value: upper exactly equals the limit.
    edge_reject = evaluate_safety(10.0, 50.0, 30.0, 12.0, 50.0)
    assert edge_reject.refusal_code is None and edge_reject.band == "REJECT"

    # REJECT interior: bound above the limit.
    reject = evaluate_safety(10.0, 55.0, 30.0, 12.0, 50.0)
    assert reject.refusal_code is None and reject.band == "REJECT"

    for res in (safe, watch, edge_watch, edge_early, early, edge_reject, reject):
        _assert_all_finite(res)


@pytest.mark.fast
def test_band_uses_bound_not_point_estimate() -> None:
    """TEST-SAFE-004: V inside but U outside the limit is REJECT (D-010)."""
    res = evaluate_safety(10.0, 55.0, 30.0, 12.0, 50.0)
    assert res.refusal_code is None
    assert res.point_168 is not None and res.point_168 < 50.0
    assert res.upper_168 is not None and res.upper_168 >= 50.0
    assert res.band == "REJECT"
    # The mirror image (point outside, bound inside) is impossible by
    # construction here, but a point-driven rule would PASS this part while
    # the bound-driven rule rejects it — the mutation RT-005 hunts for.


@pytest.mark.fast
def test_evaluate_safety_degenerate_refusals_are_finite() -> None:
    """TEST-SAFE-005: evaluate_safety refuses explicitly, never NaN/inf."""
    infinite_bound = evaluate_safety(10.0, None, 30.0, 12.0, 50.0)
    assert infinite_bound.refusal_code == "INSUFFICIENT_CALIBRATION"
    assert infinite_bound.band is None

    missing_limit = evaluate_safety(10.0, 30.0, 25.0, 12.0, None)
    assert missing_limit.refusal_code == "INVALID_INPUT"

    at_limit = evaluate_safety(50.0, 55.0, 52.0, 51.0, 50.0)
    assert at_limit.refusal_code == "INVALID_INPUT"
    assert at_limit.band is None

    bad_fraction = evaluate_safety(10.0, 30.0, 25.0, 12.0, 50.0, margin_fraction=1.0)
    assert bad_fraction.refusal_code == "INVALID_INPUT"

    for res in (infinite_bound, missing_limit, at_limit, bad_fraction):
        _assert_all_finite(res)

    # Determinism on the flagship worked example.
    first = evaluate_safety(12.1, 39.8, 32.3, 18.7, 50.0)
    second = evaluate_safety(12.1, 39.8, 32.3, 18.7, 50.0)
    assert first == second
    assert first.band == "WATCH"


@pytest.mark.property
@settings(max_examples=100)
@given(
    v0=st.floats(min_value=0.0, max_value=40.0, allow_nan=False, allow_infinity=False),
    headroom=st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    drift=st.floats(min_value=-20.0, max_value=120.0, allow_nan=False, allow_infinity=False),
    slack=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
)
def test_evaluate_safety_band_priority_property(
    v0: float, headroom: float, drift: float, slack: float
) -> None:
    """REJECT has absolute priority: any bound at/over the limit rejects."""
    limit = v0 + headroom
    res = evaluate_safety(v0, limit + slack, v0 + drift, v0 + 1.0, limit)
    assert res.refusal_code is None
    assert res.band == "REJECT"
    _assert_all_finite(res)
