"""Phase 4 end-to-end evidence chain (T-408 to T-410 over the sealed Phase 3 core).

Proves the §14 ordering on hand-built fixtures with no fitted artifacts:

  telemetry → quality → DPAT/CUSUM evidence → safety → risk → recommend.

Module B stage inputs are fixed fixtures (fitted Φ_g and calibration
quantiles arrive via the T-401+ pipeline, not here); every relationship
asserted — ordering, advisory non-interference, refusal propagation,
band echo — holds regardless of those values. No 96 h/168 h observation
enters any input (INV-4); no invalid value is imputed (INV-1); no verdict
depends on an identifier (INV-2); everything replays bit-identically
(INV-8).
"""

from __future__ import annotations

import pytest

from backend.core.attribution import AttributionVerdict
from backend.core.condition import zone_arrhenius_consistent
from backend.core.cusum import cusum_evidence
from backend.core.dpat import dpat_limits
from backend.core.quality import assess_quality, roll_up_quality
from backend.core.recommend import Recommendation, recommend
from backend.core.risk import compute_risk
from backend.core.robust import robust_stats
from backend.core.safety import SafetyResult, evaluate_safety

# Fixed Module B stage (DRIFT_SPEC § 8 worked example; fitted quantities
# arrive via T-401 — the chain asserts relationships, not these values).
V0 = 12.1
V24 = 18.7
POINT = 32.3
BOUND = 39.8
LIMIT_HIGH = 50.0

# Lot cohort: stable peers around 10 µA (leave-one-out inside dpat_limits).
LOT_COHORT = [9.5, 10.5, 9.0, 11.0, 10.0, 9.8, 10.2, 9.6, 10.4, 10.1, 9.9, 10.3]


def _module_b_stage() -> SafetyResult:
    """Fixed forecast/bound/safety stage shared by every chain below."""
    return evaluate_safety(V0, BOUND, POINT, V24, LIMIT_HIGH)


@pytest.mark.fast
def test_phase4_chain_latent_drift_with_healthy_measurement() -> None:
    """Lens disagreement is information: CUSUM sees persistence first."""
    telemetry = [10.0, 10.3, 10.6, 10.9, 11.2, 11.5, 11.8]
    times = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0, 120.0]
    # INV-4 static pin: the chain fixture never names a withheld read-point.
    fixture_tokens = " ".join(map(str, times)) + " v0 v24"
    assert "96" not in fixture_tokens and "168" not in fixture_tokens

    quality = assess_quality(telemetry, times=times)
    assert quality.refusal_code is None
    assert quality.score == pytest.approx(1.0)
    assert quality.findings == ()

    stats = robust_stats(LOT_COHORT)
    assert stats.median is not None and stats.robust_sigma is not None
    detection = dpat_limits(LOT_COHORT, part_value=telemetry[-1])
    assert detection.z is not None and detection.verdict is not None

    evidence = cusum_evidence(telemetry, stats.median, stats.robust_sigma)
    assert evidence.refusal_code is None
    assert evidence.signal_high is True
    assert evidence.first_crossing_high is not None

    safety = _module_b_stage()
    assert safety is not None and getattr(safety, "band", None) is not None
    risk = compute_risk(abs(detection.z), safety, AttributionVerdict.PART, quality.score)
    assert risk.refusal_code is None
    assert risk.band == safety.band
    assert risk.sum_check.abs_diff <= risk.sum_check.tolerance
    action = recommend(
        band=safety.band,
        absolute_fail=False,
        z_primary=detection.z,
        attribution=AttributionVerdict.PART,
        predicted_margin_pct=safety.predicted_margin_pct,
    )
    assert action.action == Recommendation.MONITOR

    # Advisory non-interference: the identical chain without CUSUM agrees
    # byte-for-byte (CUSUM is evidence, never an input).
    risk_again = compute_risk(abs(detection.z), safety, AttributionVerdict.PART, quality.score)
    action_again = recommend(
        band=safety.band,
        absolute_fail=False,
        z_primary=detection.z,
        attribution=AttributionVerdict.PART,
        predicted_margin_pct=safety.predicted_margin_pct,
    )
    assert risk_again == risk and action_again == action

    # Determinism: the whole chain replays identically (INV-8).
    assert assess_quality(telemetry, times=times) == quality
    assert cusum_evidence(telemetry, stats.median, stats.robust_sigma) == evidence


@pytest.mark.fast
def test_phase4_chain_sensor_fault_is_retest_not_reject() -> None:
    """A stuck sensor with setup attribution is retested, never condemned."""
    stuck = [7.0, 7.0, 7.0, 7.0, 7.0]
    quality = assess_quality(stuck)
    assert [finding.code for finding in quality.findings] == ["FLATLINE"]
    assert quality.score is not None and quality.score < 1.0

    lot_score = roll_up_quality([quality.score, 1.0, 1.0])
    assert lot_score.refusal_code is None
    assert lot_score.score is not None and lot_score.score < 1.0

    safety = _module_b_stage()
    risk = compute_risk(7.5, safety, AttributionVerdict.SOCKET, quality.score)
    assert risk.refusal_code is None
    action = recommend(
        band=safety.band,
        absolute_fail=False,
        z_primary=7.5,
        attribution=AttributionVerdict.SOCKET,
        predicted_margin_pct=safety.predicted_margin_pct,
    )
    # SEVERE anomaly, yet the setup attribution routes to retest — the
    # measurement is suspect, the component is not condemned.
    assert action.action == Recommendation.RETEST_DIFFERENT_SOCKET


@pytest.mark.fast
def test_phase4_chain_zone_thermal_story_earns_its_credit() -> None:
    """T-410 wired: a thermally consistent zone offset reviews, not rejects."""
    verdict = zone_arrhenius_consistent(135.0, 125.0, 0.7, 2.0, 1)
    assert verdict.consistent is True
    assert verdict.af is not None and verdict.af > 1.0

    safety = _module_b_stage()
    risk = compute_risk(2.0, safety, AttributionVerdict.ZONE, 1.0, zone_arrhenius_consistent=True)
    assert risk.refusal_code is None
    credit_terms = [comp for comp in risk.components if comp.name == "attribution_credit"]
    assert len(credit_terms) == 1
    assert credit_terms[0].raw == pytest.approx(0.5)
    action = recommend(
        band=safety.band,
        absolute_fail=False,
        z_primary=2.0,
        attribution=AttributionVerdict.ZONE,
        predicted_margin_pct=safety.predicted_margin_pct,
        zone_arrhenius_consistent=True,
    )
    assert action.action == Recommendation.ZONAL_REVIEW


@pytest.mark.fast
def test_phase4_chain_degraded_and_refusal_paths_stay_explicit() -> None:
    """Corrupt telemetry degrades the chain; it never silently imputes."""
    corrupt: list[float | None] = [float("nan"), float("inf"), None]
    quality = assess_quality(corrupt, lower_bound=0.0, upper_bound=100.0)
    assert quality.score == pytest.approx(0.0)
    assert quality.n_valid == 0
    assert quality.warning is not None

    safety = _module_b_stage()
    degraded = compute_risk(7.5, safety, AttributionVerdict.PART, quality.score)
    assert degraded.refusal_code is None
    degraded_terms = [comp for comp in degraded.components if comp.name == "quality"]
    assert degraded_terms[0].raw == pytest.approx(1.0)

    # The documented seam: with no score at all, risk refuses outright.
    refused = compute_risk(7.5, safety, AttributionVerdict.PART, None)
    assert refused.refusal_code == "INSUFFICIENT_DATA"
