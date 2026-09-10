"""Unit tests for the disposition rule table (T-312, FR-406).

Implements TEST-REC-001..007, one row each with its trigger text asserted
verbatim, against RISK_SCORING_SPEC § 6. Cross-row properties live in
``backend/tests/property/test_recommend.py`` (TEST-REC-008).
"""

from __future__ import annotations

import pytest

from backend.core.attribution import AttributionVerdict
from backend.core.recommend import Recommendation, recommend


@pytest.mark.fast
def test_accept() -> None:
    """TEST-REC-001: SAFE + NOMINAL + strong evidence accepts."""
    res = recommend("SAFE", False, 1.0, AttributionVerdict.PART, 0.5)
    assert res.action == Recommendation.ACCEPT
    assert res.trigger == "band SAFE with nominal anomaly evidence and strong provenance"
    assert res.severity is not None and res.severity.value == "NOMINAL"


@pytest.mark.fast
def test_monitor() -> None:
    """TEST-REC-002: WATCH with a quiet anomaly channel monitors."""
    res = recommend("WATCH", False, 1.0, AttributionVerdict.PART, 0.3)
    assert res.action == Recommendation.MONITOR
    assert res.trigger == "band == WATCH with a quiet anomaly channel: watch, do not scrap"


@pytest.mark.fast
def test_investigate() -> None:
    """TEST-REC-003: SEVERE anomaly with a SAFE band investigates."""
    res = recommend("SAFE", False, 7.5, AttributionVerdict.PART, 0.5)
    assert res.action == Recommendation.INVESTIGATE
    assert "disagree" in res.trigger
    assert res.severity is not None and res.severity.value == "SEVERE"


@pytest.mark.fast
def test_retest_different_socket() -> None:
    """TEST-REC-004: SOCKET attribution retests via the credit path only."""
    res = recommend("REJECT", False, 9.0, AttributionVerdict.SOCKET, 0.0)
    assert res.action == Recommendation.RETEST_DIFFERENT_SOCKET
    assert "SOCKET" in res.trigger
    tester = recommend("WATCH", False, 1.0, AttributionVerdict.TESTER, 0.3)
    assert tester.action == Recommendation.RETEST_DIFFERENT_SOCKET


@pytest.mark.fast
def test_extended_burn_in() -> None:
    """TEST-REC-005: EARLY_WARNING with room extends burn-in."""
    res = recommend("EARLY_WARNING", False, 5.0, AttributionVerdict.PART, 0.2)
    assert res.action == Recommendation.EXTEND_BURN_IN
    assert res.trigger == (
        "band == EARLY_WARNING and predicted_margin_pct > 0: more oven time resolves "
        "the ambiguity with evidence instead of a guess"
    )


@pytest.mark.fast
def test_reject() -> None:
    """TEST-REC-006: absolute failure and bound REJECT both reject."""
    hard = recommend("SAFE", True, 1.0, AttributionVerdict.PART, 0.5)
    assert hard.action == Recommendation.REJECT
    assert "FR-210" in hard.trigger
    bound = recommend("REJECT", False, 2.0, AttributionVerdict.PART, 0.0)
    assert bound.action == Recommendation.REJECT


@pytest.mark.fast
def test_insufficient_evidence() -> None:
    """TEST-REC-007: missing inputs decline to recommend (row exists for this)."""
    res = recommend(None, False, 1.0, AttributionVerdict.PART, 0.5)
    assert res.action == Recommendation.INSUFFICIENT_EVIDENCE
    assert res.trigger.startswith("band missing")
    assert recommend("SAFE", False, None, AttributionVerdict.PART, 0.5).action == (
        Recommendation.INSUFFICIENT_EVIDENCE
    )


@pytest.mark.fast
def test_zonal_review_needs_arrhenius_flag() -> None:
    """ZONE with consistency reviews zonally; without, it investigates."""
    review = recommend(
        "WATCH", False, 2.0, AttributionVerdict.ZONE, 0.3, zone_arrhenius_consistent=True
    )
    assert review.action == Recommendation.ZONAL_REVIEW
    uncertain = recommend("WATCH", False, 2.0, AttributionVerdict.ZONE, 0.3)
    assert uncertain.action == Recommendation.INVESTIGATE
