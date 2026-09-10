"""Disposition rule table for LATENTIS numeric core (Phase 3, T-312).

Implements FR-406 and RISK_SCORING_SPEC § 6 (the system recommends, the human
disposes — CONCUR / OVERRIDE + reason / DEFER are the inspector's, recorded
downstream with the payload snapshot):

  - Total, ordered rule evaluation over the authoritative band, the
    absolute-limit verdict, the attribution verdict, the robust distance, the
    bound-based margin, and evidence-weakness flags. Every input combination
    maps to exactly one action with its triggering condition as text; the
    function never raises on valid enums and never returns NaN/inf (actions
    are categorical, margins travel alongside for the record).
  - Specified-table divergences, resolved conservatively and recorded in
    D-037 as PROPOSED spec amendments: the table has no WATCH row while
    TEST-REC-002 demands a MONITOR action (WATCH + quiet anomaly + PART maps
    there); the table labels the missing-input row INSUFFICIENT_DATA while
    TEST-REC-007 demands INSUFFICIENT_EVIDENCE (the executable oracle wins).
  - A REJECT band with an exonerating setup verdict still retests (the setup
    produced the signal); a REJECT band with PART or INDETERMINATE rejects
    (the bound crossing dominates when setup is not exonerated).
  - Severity follows ANOMALY_SPEC § 5 edges; the anomaly-alarm line for
    conflict detection is ANOMALOUS (4.5, "clearly separated"). ZONAL_REVIEW
    needs the Arrhenius-consistency flag (D-035: evaluated downstream); a
    ZONE verdict without it investigates rather than assumes.

Constraints:
  - No numeric literals outside 0, 1, 2 (severity edges imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from backend.core.attribution import AttributionVerdict
from backend.core.constants import (
    SEVERITY_ANOMALOUS_Z,
    SEVERITY_ELEVATED_Z,
    SEVERITY_SEVERE_Z,
)
from backend.core.safety import SafetyBand


class Recommendation(StrEnum):
    """System recommendation actions (RISK_SCORING_SPEC § 6)."""

    ACCEPT = "ACCEPT"
    MONITOR = "MONITOR"
    INVESTIGATE = "INVESTIGATE"
    EXTEND_BURN_IN = "EXTEND_BURN_IN"
    RETEST_DIFFERENT_SOCKET = "RETEST_DIFFERENT_SOCKET"
    ZONAL_REVIEW = "ZONAL_REVIEW"
    REJECT = "REJECT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Severity(StrEnum):
    """Anomaly severity bands (ANOMALY_SPEC § 5, presentation, not threshold)."""

    NOMINAL = "NOMINAL"
    ELEVATED = "ELEVATED"
    ANOMALOUS = "ANOMALOUS"
    SEVERE = "SEVERE"


@dataclass(frozen=True)
class RecommendationResult:
    """Immutable recommendation with its triggering condition as text."""

    action: Recommendation
    trigger: str
    severity: Severity | None = None


def _severity_of_z(abs_z: float) -> Severity:
    """Map |z| to its ANOMALY_SPEC § 5 presentation band (private helper)."""
    if abs_z >= SEVERITY_SEVERE_Z:
        return Severity.SEVERE
    if abs_z >= SEVERITY_ANOMALOUS_Z:
        return Severity.ANOMALOUS
    if abs_z >= SEVERITY_ELEVATED_Z:
        return Severity.ELEVATED
    return Severity.NOMINAL


def _verdict(value: AttributionVerdict | str | None) -> AttributionVerdict | None:
    """Coerce an attribution input to its verdict, or None when unknown."""
    if value is None:
        return None
    if isinstance(value, AttributionVerdict):
        return value
    try:
        return AttributionVerdict(str(value))
    except ValueError:
        return None


def recommend(
    band: SafetyBand | str | None,
    absolute_fail: bool,
    z_primary: float | None,
    attribution: AttributionVerdict | str | None,
    predicted_margin_pct: float | None,
    evidence_weak: bool = False,
    zone_arrhenius_consistent: bool = False,
) -> RecommendationResult:
    """Recommend the disposition for one part (RISK_SCORING_SPEC § 6).

    Evaluation order (first match wins): missing inputs → absolute failure →
    setup retest (SOCKET/TESTER) → zonal path → bound REJECT → extended
    burn-in (EARLY_WARNING with room) → monitor (WATCH, quiet) → investigate
    (conflict, weak evidence, or unresolved) → accept (SAFE, NOMINAL, strong).

    Args:
        band: Authoritative T-310 band (None when safety refused).
        absolute_fail: Absolute-limit verdict (FR-210 hard fail).
        z_primary: Primary robust distance (None when Module A refused).
        attribution: Authoritative T-305 verdict.
        predicted_margin_pct: Bound-based margin fraction (None when absent).
        evidence_weak: Any weakness flag (reduced power, censoring, small n).
        zone_arrhenius_consistent: Whether a ZONE offset is
            Arrhenius-consistent (unlocks ZONAL_REVIEW, D-035).

    Returns:
        RecommendationResult with the action, its trigger text, and the
        severity behind it (None when z was missing).
    """
    band_name = band if isinstance(band, str) else (band.value if band is not None else None)
    if band_name not in ("SAFE", "WATCH", "EARLY_WARNING", "REJECT"):
        return RecommendationResult(
            Recommendation.INSUFFICIENT_EVIDENCE,
            "band missing or refused: no recommendation without the bound-driven band",
        )
    verdict = _verdict(attribution)
    if verdict is None:
        return RecommendationResult(
            Recommendation.INSUFFICIENT_EVIDENCE,
            "attribution verdict missing or unknown: no recommendation without setup evidence",
        )
    if (
        z_primary is None
        or (isinstance(z_primary, bool))
        or not isinstance(z_primary, (int, float))
    ):
        return RecommendationResult(
            Recommendation.INSUFFICIENT_EVIDENCE,
            "primary robust distance missing: anomaly evidence required",
            None,
        )
    z_val = float(z_primary)
    if not math.isfinite(z_val):
        return RecommendationResult(
            Recommendation.INSUFFICIENT_EVIDENCE,
            "primary robust distance non-finite: anomaly evidence required",
            None,
        )
    if predicted_margin_pct is None:
        return RecommendationResult(
            Recommendation.INSUFFICIENT_EVIDENCE,
            "predicted margin missing: drift evidence required",
            _severity_of_z(abs(z_val)),
        )

    severity = _severity_of_z(abs(z_val))
    anomaly_alarm = abs(z_val) >= SEVERITY_ANOMALOUS_Z
    weak = bool(evidence_weak)
    zone_ok = bool(zone_arrhenius_consistent)

    if absolute_fail:
        return RecommendationResult(
            Recommendation.REJECT,
            "absolute limit violated: hard fail supersedes every other verdict (FR-210)",
            severity,
        )
    if verdict in (AttributionVerdict.SOCKET, AttributionVerdict.TESTER):
        return RecommendationResult(
            Recommendation.RETEST_DIFFERENT_SOCKET,
            f"attribution {verdict.value}: the setup produced the signal, retest elsewhere",
            severity,
        )
    if verdict is AttributionVerdict.ZONE:
        if zone_ok:
            return RecommendationResult(
                Recommendation.ZONAL_REVIEW,
                "zone shift coherent with recorded temperature: zonal limits apply",
                severity,
            )
        return RecommendationResult(
            Recommendation.INVESTIGATE,
            "zone shift without Arrhenius consistency: uncertainty reported, not assumed",
            severity,
        )
    if band_name == "REJECT":
        return RecommendationResult(
            Recommendation.REJECT,
            "conformal bound crosses the absolute limit and setup is not exonerated",
            severity,
        )
    if band_name == "EARLY_WARNING" and predicted_margin_pct > 0.0:
        return RecommendationResult(
            Recommendation.EXTEND_BURN_IN,
            "band == EARLY_WARNING and predicted_margin_pct > 0: more oven time resolves "
            "the ambiguity with evidence instead of a guess",
            severity,
        )
    if band_name == "WATCH" and not anomaly_alarm and verdict is AttributionVerdict.PART:
        return RecommendationResult(
            Recommendation.MONITOR,
            "band == WATCH with a quiet anomaly channel: watch, do not scrap",
            severity,
        )
    if (
        (anomaly_alarm and band_name in ("SAFE", "WATCH"))
        or (band_name == "WATCH" and verdict is AttributionVerdict.INDETERMINATE)
        or (band_name == "SAFE" and weak)
        or (verdict is AttributionVerdict.INDETERMINATE)
    ):
        return RecommendationResult(
            Recommendation.INVESTIGATE,
            "modules disagree, evidence is weak, or attribution is indeterminate: "
            "the conflict is reported rather than averaged away",
            severity,
        )
    if band_name == "SAFE" and severity is Severity.NOMINAL and not weak:
        return RecommendationResult(
            Recommendation.ACCEPT,
            "band SAFE with nominal anomaly evidence and strong provenance",
            severity,
        )
    return RecommendationResult(
        Recommendation.INVESTIGATE,
        "no acceptance criteria met: requires human review",
        severity,
    )
