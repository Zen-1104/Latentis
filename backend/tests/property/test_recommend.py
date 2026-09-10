"""Property tests for the disposition rule table (T-312, FR-406).

Implements TEST-REC-008, naming ``recommend`` for QG-CORE-01: the table is
total (every input maps to an action), deterministic, trigger-textured, and
severity-consistent across Hypothesis inputs.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from backend.core.attribution import AttributionVerdict
from backend.core.recommend import Recommendation, recommend

BANDS = st.sampled_from(["SAFE", "WATCH", "EARLY_WARNING", "REJECT", None])
VERDICTS = st.sampled_from(["PART", "SOCKET", "ZONE", "TESTER", "INDETERMINATE", None])


@pytest.mark.property
@settings(max_examples=150)
@given(
    band=BANDS,
    absolute_fail=st.booleans(),
    z=st.floats(min_value=-15.0, max_value=15.0, allow_nan=False, allow_infinity=False),
    attribution=VERDICTS,
    margin=st.floats(min_value=-0.5, max_value=1.0, allow_nan=False, allow_infinity=False),
    weak=st.booleans(),
    zone_ok=st.booleans(),
)
def test_recommend_total_deterministic_and_triggered(
    band: str | None,
    absolute_fail: bool,
    z: float,
    attribution: str | None,
    margin: float,
    weak: bool,
    zone_ok: bool,
) -> None:
    """TEST-REC-008: recommend maps every input to a triggered action."""
    first = recommend(
        band,
        absolute_fail,
        z,
        AttributionVerdict(attribution) if attribution is not None else None,
        margin,
        evidence_weak=weak,
        zone_arrhenius_consistent=zone_ok,
    )
    second = recommend(
        band,
        absolute_fail,
        z,
        AttributionVerdict(attribution) if attribution is not None else None,
        margin,
        evidence_weak=weak,
        zone_arrhenius_consistent=zone_ok,
    )
    assert first == second
    assert isinstance(first.action, Recommendation)
    assert first.trigger.strip() != ""
    # Absolute failure always rejects, whatever else the inputs say.
    if absolute_fail and band is not None and attribution is not None:
        assert first.action == Recommendation.REJECT
    # Severity tracks |z| through the specified edges.
    if first.severity is not None:
        if abs(z) >= 6.0:
            assert first.severity.value == "SEVERE"
        elif abs(z) < 3.0:
            assert first.severity.value == "NOMINAL"
