"""Unit tests for the decomposed risk index (T-311, FR-401/FR-403).

Implements TEST-RISK-003 (attribution credit strictly reduces risk and flips
the recommendation to RETEST_DIFFERENT_SOCKET) plus refusal, validation, and
determinism cases against RISK_SCORING_SPEC § 1-§ 4. Adding-up and
band-invariance properties live in ``backend/tests/property/test_risk.py``.
"""

from __future__ import annotations

import dataclasses
import math

import pytest

from backend.core.attribution import AttributionVerdict
from backend.core.recommend import recommend
from backend.core.risk import RiskWeights, compute_risk
from backend.core.safety import SafetyResult, evaluate_safety


def _safety() -> SafetyResult:
    """Authoritative T-310 result on the DRIFT_SPEC § 8 worked example."""
    return evaluate_safety(12.1, 39.8, 32.3, 18.7, 50.0)


def _assert_result_finite(result: object) -> None:
    """Every float on the result is finite or None (never NaN/inf)."""
    for field_info in dataclasses.fields(result):  # type: ignore[arg-type]
        value = getattr(result, field_info.name)
        if isinstance(value, float):
            assert math.isfinite(value), f"{field_info.name} is non-finite"


@pytest.mark.fast
def test_attribution_credit_reduces_risk() -> None:
    """TEST-RISK-003: SOCKET risk is strictly lower and retests, not rejects."""
    safety = _safety()
    assert safety.band == "WATCH"
    part = compute_risk(7.5, safety, AttributionVerdict.PART, 0.9)
    socket = compute_risk(7.5, safety, AttributionVerdict.SOCKET, 0.9)
    assert part.refusal_code is None and socket.refusal_code is None
    assert socket.risk_index < part.risk_index
    assert socket.risk_index == pytest.approx(part.risk_index - 0.10)
    assert socket.band == part.band == "WATCH"
    rec = recommend("WATCH", False, 7.5, AttributionVerdict.SOCKET, 0.27)
    assert rec.action.value == "RETEST_DIFFERENT_SOCKET"
    _assert_result_finite(part)
    _assert_result_finite(socket)


@pytest.mark.fast
def test_zone_half_credit_needs_arrhenius_flag() -> None:
    """ZONE without downstream consistency earns no credit (D-035 scoping)."""
    safety = _safety()
    plain = compute_risk(7.5, safety, AttributionVerdict.ZONE, 0.9)
    flagged = compute_risk(
        7.5, safety, AttributionVerdict.ZONE, 0.9, zone_arrhenius_consistent=True
    )
    assert plain.refusal_code is None and flagged.refusal_code is None
    credit_plain = next(c for c in plain.components if c.name == "attribution_credit")
    credit_flagged = next(c for c in flagged.components if c.name == "attribution_credit")
    assert credit_plain.raw == pytest.approx(0.0)
    assert credit_flagged.raw == pytest.approx(0.5)
    assert flagged.risk_index < plain.risk_index


@pytest.mark.fast
def test_components_bounded_and_named() -> None:
    """Five named components with weights, raws in [0, 1], registry ids."""
    res = compute_risk(2.0, _safety(), AttributionVerdict.PART, 1.0)
    assert res.refusal_code is None
    assert [c.name for c in res.components] == [
        "anomaly",
        "drift",
        "margin",
        "quality",
        "attribution_credit",
    ]
    for comp in res.components:
        assert 0.0 <= comp.raw <= 1.0
        assert comp.formula_id.startswith("risk.")
        assert math.isfinite(comp.weighted)
    # |z| = 2 below ELEVATED reads exactly 0; perfect quality reads exactly 0.
    raws = {c.name: c.raw for c in res.components}
    assert raws["anomaly"] == pytest.approx(0.0)
    assert raws["quality"] == pytest.approx(0.0)


@pytest.mark.fast
def test_refusal_propagation_and_invalid_inputs() -> None:
    """Refused/invalid upstreams refuse explicitly (never a default index)."""
    assert compute_risk(None, _safety(), AttributionVerdict.PART, 0.9).refusal_code is not None
    assert (
        compute_risk(float("nan"), _safety(), AttributionVerdict.PART, 0.9).refusal_code
        == "INVALID_INPUT"
    )
    assert compute_risk(2.0, None, AttributionVerdict.PART, 0.9).refusal_code is not None
    refused_safety = evaluate_safety(10.0, None, 30.0, 12.0, 50.0)
    assert (
        compute_risk(2.0, refused_safety, AttributionVerdict.PART, 0.9).refusal_code
        == "INSUFFICIENT_CALIBRATION"
    )
    assert compute_risk(2.0, _safety(), None, 0.9).refusal_code is not None
    assert compute_risk(2.0, _safety(), "NOZZLE", 0.9).refusal_code == "INVALID_INPUT"
    assert compute_risk(2.0, _safety(), AttributionVerdict.PART, None).refusal_code is not None
    assert (
        compute_risk(2.0, _safety(), AttributionVerdict.PART, 1.5).refusal_code == "INVALID_INPUT"
    )
    bad_weights = RiskWeights(w_anomaly=float("inf"))
    assert (
        compute_risk(2.0, _safety(), AttributionVerdict.PART, 0.9, bad_weights).refusal_code
        == "INVALID_INPUT"
    )


@pytest.mark.fast
def test_default_weights_sum_to_one() -> None:
    """The documented policy default satisfies Σ|w| = 1 (D-019)."""
    defaults = RiskWeights()
    total = (
        defaults.w_anomaly
        + defaults.w_drift
        + defaults.w_margin
        + defaults.w_quality
        + defaults.w_credit
    )
    assert total == pytest.approx(1.0)


@pytest.mark.fast
def test_deterministic_repeated_execution() -> None:
    """INV-8: identical inputs give a byte-identical risk record twice."""
    first = compute_risk(7.5, _safety(), AttributionVerdict.PART, 0.9)
    second = compute_risk(7.5, _safety(), AttributionVerdict.PART, 0.9)
    assert first == second
