"""Property tests for sensor/data-quality evidence (T-409, D-039).

Implements TEST-QUAL-006 (bitwise-identical replay naming ``assess_quality``
for QG-CORE-01) plus bounded-score and append-a-defect monotonicity
properties over the linear deduction schedule.
"""

from __future__ import annotations

import math

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from backend.core.quality import assess_quality, roll_up_quality

FINITE_FLOATS = st.floats(min_value=-1.0e6, max_value=1.0e6, allow_nan=False, allow_infinity=False)
OBSERVATION = st.one_of(FINITE_FLOATS, st.none())


@pytest.mark.property
@settings(max_examples=100)
@given(
    values=st.lists(OBSERVATION, min_size=0, max_size=30),
    n_censored=st.integers(min_value=0, max_value=10),
)
def test_quality_score_deterministic(values: list[float | None], n_censored: int) -> None:
    """TEST-QUAL-006: identical series replay bitwise-identically."""
    first = assess_quality(values, n_censored=n_censored)
    second = assess_quality(list(values), n_censored=n_censored)
    third = assess_quality(tuple(values), n_censored=n_censored)
    assert first == second == third
    assert first.score is not None
    assert math.isfinite(first.score)
    assert 0.0 <= first.score <= 1.0


@pytest.mark.property
@settings(max_examples=100)
@given(values=st.lists(OBSERVATION, min_size=0, max_size=30))
def test_quality_appending_a_defect_never_raises_the_score(
    values: list[float | None],
) -> None:
    """Appending a missing/corrupt observation weakly lowers the score.

    The valid subsequence is untouched by the append, so no finding can
    clear and every deduction count weakly grows — exact in float
    arithmetic because each step is monotone.
    """
    base = assess_quality(values)
    with_missing = assess_quality([*values, None])
    with_corrupt = assess_quality([*values, float("nan")])
    assert base.score is not None
    assert with_missing.score is not None and with_corrupt.score is not None
    assert with_missing.score <= base.score
    assert with_corrupt.score <= base.score
    n_valid_base = sum(1 for v in values if v is not None and math.isfinite(v))
    assert with_missing.n_valid == n_valid_base
    assert with_corrupt.n_valid == n_valid_base


@pytest.mark.property
@settings(max_examples=100)
@given(
    scores=st.lists(
        st.one_of(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            st.none(),
        ),
        min_size=0,
        max_size=20,
    )
)
def test_roll_up_quality_bounded_deterministic_and_honest(
    scores: list[float | None],
) -> None:
    """Lot roll-up is bounded, deterministic, and accounts exclusions exactly."""
    first = roll_up_quality(scores)
    second = roll_up_quality(list(scores))
    assert first == second
    assert first.n_parts == len(scores)
    assert first.n_excluded == sum(1 for s in scores if s is None)
    usable = [s for s in scores if s is not None]
    if not usable:
        assert first.refusal_code == "INSUFFICIENT_DATA"
        assert first.score is None
    else:
        assert first.refusal_code is None
        assert first.score is not None and math.isfinite(first.score)
        assert 0.0 <= first.score <= 1.0
        assert first.score == pytest.approx(sum(usable) / len(usable))
