"""Property tests for conformal monotonicity and sign (T-308, FR-305).

Implements TEST-CONF-003: smaller alpha gives a weakly wider bound, and the
upper bound is the point plus the quantile (the classic sign error uses minus).
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from backend.core.conformal import conformal_upper


@pytest.mark.property
@settings(max_examples=100)
@given(
    residuals=st.lists(
        st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False),
        min_size=10,
        max_size=80,
    ),
    point=st.floats(min_value=-50.0, max_value=150.0, allow_nan=False, allow_infinity=False),
)
def test_monotone_in_alpha_and_bound_ge_point(residuals: list[float], point: float) -> None:
    """TEST-CONF-003: tighter alpha widens the bound; U == V + q_hat."""
    narrow = conformal_upper(point, [residuals], alpha=0.5)
    wide = conformal_upper(point, [residuals], alpha=0.05)
    assert narrow.refusal_code is None
    assert narrow.upper is not None and narrow.q_hat is not None
    # The bound is the point PLUS the quantile (never minus).
    assert narrow.upper == pytest.approx(point + narrow.q_hat)
    if wide.refusal_code == "INSUFFICIENT_CALIBRATION":
        # The tighter level is unattainable from this calibration set:
        # INFINITE is wider than any finite bound, so monotonicity holds.
        assert wide.upper is None and wide.attainable_alpha is not None
    else:
        assert wide.upper is not None and wide.q_hat is not None
        assert wide.upper == pytest.approx(point + wide.q_hat)
        # Smaller alpha -> weakly wider bound (larger order statistic).
        assert wide.upper >= narrow.upper
