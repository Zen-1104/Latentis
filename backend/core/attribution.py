"""Part / socket / zone / tester attribution for LATENTIS numeric core (Phase 3, T-305).

Implements FR-208, D-035, and ANOMALY_SPEC § 7 (our extension of wafer-space GDBN
into burn-in-oven space, D-CD-04):

  - ``z_part``: robust distance of the part vs its leave-one-out lot cohort,
    computed by the same ``dpat_limits`` decision function the detector uses.
  - ``z_socket`` / ``z_zone`` / ``z_tester``: robust distance of the part *within*
    each setup group (the "typical within its socket" check).
  - ``socket_median_offset_sigma`` and analogues: ``(median(group) - median(lot))``
    in lot robust-sigma (the "whole socket shifted coherently" check).
  - Socket coherence: at least ``MIN_COHORT_SIZE`` socket members flagged vs the
    lot at or above ``SEVERITY_ELEVATED_Z`` (TEST-ATTR-002 oracle).
  - Verdict table ``PART`` / ``SOCKET`` / ``ZONE`` / ``TESTER`` / ``INDETERMINATE``
    with claim-defeat (a bad part in a bad socket is ``PART``, RT-006 row 5) and
    tie-to-``INDETERMINATE`` (TEST-ATTR-005: never picked arbitrarily).
  - The T-304 ``RobustMahalanobisResult`` is consumed, never recomputed: the exact
    additive identity ``sum(c_q) == D²`` is re-verified within
    ``SUM_CHECK_TOLERANCE`` and any disagreement refuses with ``INVALID_INPUT``,
    so attribution cannot silently disagree with the joint decomposition (INV-5).

Threshold provenance (D-035): only ``ATTRIBUTION_SETUP_OFFSET_SIGMA_THRESHOLD``
is new; every other gate reuses a registered constant.

Constraints:
  - No numeric literals outside 0, 1, 2 (all thresholds imported from constants.py)
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01)
  - Never returns NaN or inf in decision-bearing outputs (ANOMALY_SPEC § 9)
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

import numpy as np
from scipy.stats import spearmanr

from backend.core.constants import (
    ATTRIBUTION_SETUP_OFFSET_SIGMA_THRESHOLD,
    DPAT_DEFAULT_K,
    MIN_COHORT_SIZE,
    SEVERITY_ELEVATED_Z,
    SUM_CHECK_TOLERANCE,
)
from backend.core.dpat import dpat_limits
from backend.core.multivariate import RobustMahalanobisResult
from backend.core.robust import robust_stats

AttributionRefusalCode = Literal[
    "INSUFFICIENT_COHORT",
    "NO_VARIATION",
    "INVALID_INPUT",
]


class AttributionVerdict(StrEnum):
    """Attribution verdict for an anomalous part (ANOMALY_SPEC § 7, FR-208)."""

    PART = "PART"
    SOCKET = "SOCKET"
    ZONE = "ZONE"
    TESTER = "TESTER"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class AttributionEvidence:
    """Computed evidence behind an attribution verdict.

    Every field used by the verdict rule is stored here, so the explanation is
    generated from the same values as the decision (INV-5). All floats are
    finite or None; this object never carries NaN or inf.
    """

    lot_n: int | None = None
    lot_median: float | None = None
    lot_robust_sigma: float | None = None
    z_part: float | None = None
    socket_n: int | None = None
    socket_median_offset_sigma: float | None = None
    z_socket: float | None = None
    socket_coherent_count: int | None = None
    zone_n: int | None = None
    zone_median_offset_sigma: float | None = None
    z_zone: float | None = None
    tester_n: int | None = None
    tester_median_offset_sigma: float | None = None
    z_tester: float | None = None
    tester_spearman_rho: float | None = None
    d2: float | None = None
    p_value: float | None = None
    top_parameter: str | None = None
    top_contribution: float | None = None
    top_share: float | None = None
    parameter_share: float | None = None
    setup_claims: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AttributionResult:
    """Complete, immutable attribution evaluation for one part."""

    verdict: AttributionVerdict
    evidence: AttributionEvidence
    refusal_code: AttributionRefusalCode | None = None
    warning: str | None = None


@dataclass(frozen=True)
class _GroupAssessment:
    """Internal per-group workup: offset evidence and within-group typicality."""

    n: int
    median: float
    offset_sigma: float | None
    z_within: float | None
    typical: bool | None
    coherent_count: int | None = None


def _finite_or_none(value: float | None) -> float | None:
    """Return a finite float, else None (never propagates NaN or inf)."""
    if value is None:
        return None
    try:
        finite_value = float(value)
    except (TypeError, ValueError):
        return None
    return finite_value if math.isfinite(finite_value) else None


def _clean_1d(values: Sequence[float] | np.ndarray | None) -> np.ndarray | None:
    """Return finite 1-D cohort values, None when the cohort is absent.

    Raises:
        ValueError: when the input is present but not one-dimensional
            (malformed cohort dimensions are INVALID_INPUT, never ravelled).
    """
    if values is None:
        return None
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"Expected 1-D cohort vector, got {arr.ndim}-D array")
    return arr[np.isfinite(arr)]


def _assess_group(
    cohort: Sequence[float] | np.ndarray | None,
    part_value: float,
    lot_median: float,
    lot_sigma: float,
    k: float,
    count_coherence: bool,
) -> _GroupAssessment | None:
    """Work up one setup group: median offset vs the lot and within-group typicality.

    Returns None when the group cohort is absent or too small to evaluate
    (the caller records it as unevaluated position metadata).
    """
    clean = _clean_1d(cohort)
    if clean is None or clean.size < MIN_COHORT_SIZE:
        return None

    stats = robust_stats(clean)
    group_median = stats.median
    offset = _finite_or_none((group_median - lot_median) / lot_sigma)

    if stats.refusal_code == "NO_VARIATION" or not (stats.robust_sigma > 0.0):
        # Zero-variation group: the median is exact; typicality is equality.
        is_typical = part_value == group_median
        z_within = 0.0 if is_typical else None
    else:
        scored = dpat_limits(clean, part_value=part_value, k=k)
        z_within = _finite_or_none(scored.z)
        is_typical = z_within is not None and abs(z_within) < SEVERITY_ELEVATED_Z

    coherent: int | None = None
    if count_coherence:
        deviations = (clean - lot_median) / lot_sigma
        coherent = int(
            np.sum(np.isfinite(deviations) & (np.abs(deviations) >= SEVERITY_ELEVATED_Z))
        )

    return _GroupAssessment(
        n=int(clean.size),
        median=float(group_median),
        offset_sigma=offset,
        z_within=z_within,
        typical=is_typical,
        coherent_count=coherent,
    )


def _tester_spearman_rho(
    tester_cohort: Sequence[float] | np.ndarray | None,
    tester_timestamps: Sequence[float] | np.ndarray | None,
) -> float | None:
    """Report Spearman association between tester values and read timestamps.

    Supporting evidence only (D-035): a fixed tester scale error is
    tester-attributable with no drift at all, so this never gates the verdict.
    """
    if tester_cohort is None or tester_timestamps is None:
        return None
    try:
        values = np.asarray(tester_cohort, dtype=np.float64).ravel()
        stamps = np.asarray(tester_timestamps, dtype=np.float64).ravel()
    except (TypeError, ValueError):
        return None
    if values.shape != stamps.shape:
        return None
    mask = np.isfinite(values) & np.isfinite(stamps)
    paired_values = values[mask]
    if paired_values.size < MIN_COHORT_SIZE:
        return None
    try:
        rho = float(spearmanr(paired_values, stamps[mask]).statistic)
    except (ValueError, TypeError):
        return None
    return _finite_or_none(rho)


def _invalid_input(warning: str) -> AttributionResult:
    """Build the canonical malformed-input refusal (INDETERMINATE, no numbers)."""
    return AttributionResult(
        verdict=AttributionVerdict.INDETERMINATE,
        evidence=AttributionEvidence(),
        refusal_code="INVALID_INPUT",
        warning=warning,
    )


def attribute(
    part_value: float,
    lot_cohort: Sequence[float] | np.ndarray,
    socket_cohort: Sequence[float] | np.ndarray | None = None,
    zone_cohort: Sequence[float] | np.ndarray | None = None,
    tester_cohort: Sequence[float] | np.ndarray | None = None,
    tester_timestamps: Sequence[float] | np.ndarray | None = None,
    mahalanobis_result: RobustMahalanobisResult | None = None,
    parameter: str | None = None,
    k: float = DPAT_DEFAULT_K,
) -> AttributionResult:
    """Attribute an anomaly to PART / SOCKET / ZONE / TESTER / INDETERMINATE.

    Implements the ANOMALY_SPEC § 7 decision table. All cohorts must already be
    leave-one-out (the part under test strictly excluded); values are the same
    decision-bearing readings the detector scored (INV-5).

    Args:
        part_value: Reading of the part under test.
        lot_cohort: Leave-one-out lot cohort readings (1-D, finite entries used).
        socket_cohort: Other parts in the same socket, across lots (leave-one-out).
        zone_cohort: Other parts in the same thermal zone (leave-one-out).
        tester_cohort: Other parts on the same tester, across lots (leave-one-out).
        tester_timestamps: Read timestamps paired with ``tester_cohort`` entries;
            reported as Spearman evidence only, never a verdict gate (D-035).
        mahalanobis_result: T-304 joint result for this part, consumed by
            reference: the additive identity is re-verified and any disagreement
            or non-finite joint value refuses with ``INVALID_INPUT``.
        parameter: Name of the parameter under attribution; selects its share
            from the joint contributions. Never gates the verdict (INV-2).
        k: DPAT window multiplier forwarded to the scoring function.

    Returns:
        AttributionResult with the verdict, the full computed evidence, and an
        explicit refusal code (never NaN or inf) on degenerate inputs.
    """
    notes: list[str] = []

    try:
        part_float = float(part_value)
    except (TypeError, ValueError):
        return _invalid_input("Candidate part reading is not a real number")
    if not math.isfinite(part_float):
        return _invalid_input("Candidate part reading contains a non-finite value (NaN/inf)")

    try:
        lot_clean = _clean_1d(lot_cohort)
    except ValueError as err:
        return _invalid_input(f"Malformed cohort dimensions: {err}")
    if lot_clean is None or lot_clean.size < MIN_COHORT_SIZE:
        lot_size = 0 if lot_clean is None else int(lot_clean.size)
        return AttributionResult(
            verdict=AttributionVerdict.INDETERMINATE,
            evidence=AttributionEvidence(lot_n=lot_size),
            refusal_code="INSUFFICIENT_COHORT",
            warning=(
                f"Lot cohort size n={lot_size} < {MIN_COHORT_SIZE}: "
                "no baseline to attribute against"
            ),
        )

    lot_stats = robust_stats(lot_clean)
    if lot_stats.refusal_code is not None or not (
        math.isfinite(lot_stats.robust_sigma) and lot_stats.robust_sigma > 0.0
    ):
        return AttributionResult(
            verdict=AttributionVerdict.INDETERMINATE,
            evidence=AttributionEvidence(
                lot_n=int(lot_clean.size),
                lot_median=_finite_or_none(lot_stats.median),
                lot_robust_sigma=0.0,
            ),
            refusal_code="NO_VARIATION",
            warning="Lot cohort has zero variation: offsets are undefined",
        )

    lot_median = float(lot_stats.median)
    lot_sigma = float(lot_stats.robust_sigma)
    z_part = _finite_or_none(dpat_limits(lot_clean, part_value=part_float, k=k).z)

    try:
        socket = _assess_group(socket_cohort, part_float, lot_median, lot_sigma, k, True)
        zone = _assess_group(zone_cohort, part_float, lot_median, lot_sigma, k, False)
        tester = _assess_group(tester_cohort, part_float, lot_median, lot_sigma, k, False)
    except ValueError as err:
        return _invalid_input(f"Malformed cohort dimensions: {err}")
    tester_rho = _tester_spearman_rho(tester_cohort, tester_timestamps)
    if tester_cohort is not None and tester_timestamps is not None and tester_rho is None:
        notes.append("tester timestamps unavailable or insufficient; drift evidence omitted")

    evidence_d2: float | None = None
    evidence_p: float | None = None
    top_parameter: str | None = None
    top_contribution: float | None = None
    top_share: float | None = None
    parameter_share: float | None = None
    if mahalanobis_result is not None:
        joint = mahalanobis_result
        if joint.refusal_code is not None:
            notes.append(f"Joint detector skipped ({joint.refusal_code}); univariate evidence only")
        else:
            joint_floats: list[float | None] = [joint.d2, joint.p_value]
            if joint.contributions is not None:
                for entry in joint.contributions:
                    joint_floats.extend(
                        [entry.contribution, entry.share, entry.delta, entry.weight]
                    )
            if any(v is not None and not math.isfinite(float(v)) for v in joint_floats):
                return AttributionResult(
                    verdict=AttributionVerdict.INDETERMINATE,
                    evidence=AttributionEvidence(
                        lot_n=int(lot_clean.size),
                        lot_median=lot_median,
                        lot_robust_sigma=lot_sigma,
                        z_part=z_part,
                    ),
                    refusal_code="INVALID_INPUT",
                    warning="Joint T-304 values are non-finite; refusing to attribute",
                )
            if (
                joint.d2 is not None
                and joint.contributions is not None
                and len(joint.contributions) > 0
            ):
                contrib_sum = sum(c.contribution for c in joint.contributions)
                if abs(contrib_sum - joint.d2) > SUM_CHECK_TOLERANCE:
                    return AttributionResult(
                        verdict=AttributionVerdict.INDETERMINATE,
                        evidence=AttributionEvidence(
                            lot_n=int(lot_clean.size),
                            lot_median=lot_median,
                            lot_robust_sigma=lot_sigma,
                            z_part=z_part,
                        ),
                        refusal_code="INVALID_INPUT",
                        warning=(
                            "Joint contributions disagree with D² beyond tolerance; "
                            "refusing to attribute from disagreeing values"
                        ),
                    )
                ranked = sorted(
                    joint.contributions,
                    key=lambda c: abs(c.contribution),
                    reverse=True,
                )
                top_parameter = str(ranked[0].parameter)
                top_contribution = float(ranked[0].contribution)
                top_share = float(ranked[0].share)
                if parameter is not None:
                    for entry in joint.contributions:
                        if entry.parameter == parameter:
                            parameter_share = float(entry.share)
                            break
            evidence_d2 = joint.d2
            evidence_p = joint.p_value

    def _setup_claim(offset: float | None, typical: bool | None, extra: bool) -> bool:
        return (
            offset is not None
            and abs(offset) >= ATTRIBUTION_SETUP_OFFSET_SIGMA_THRESHOLD
            and typical is True
            and extra
        )

    socket_claim = socket is not None and _setup_claim(
        socket.offset_sigma,
        socket.typical,
        socket.coherent_count is not None and socket.coherent_count >= MIN_COHORT_SIZE,
    )
    zone_claim = zone is not None and _setup_claim(zone.offset_sigma, zone.typical, True)
    tester_claim = tester is not None and _setup_claim(tester.offset_sigma, tester.typical, True)

    claims: list[str] = []
    if socket_claim:
        claims.append(AttributionVerdict.SOCKET.value)
    if zone_claim:
        claims.append(AttributionVerdict.ZONE.value)
    if tester_claim:
        claims.append(AttributionVerdict.TESTER.value)

    groups: dict[str, _GroupAssessment | None] = {
        "socket": socket,
        "zone": zone,
        "tester": tester,
    }
    evaluated = [name for name, group in groups.items() if group is not None]
    unevaluated = [name for name, group in groups.items() if group is None]

    def _evidence() -> AttributionEvidence:
        return AttributionEvidence(
            lot_n=int(lot_clean.size),
            lot_median=lot_median,
            lot_robust_sigma=lot_sigma,
            z_part=z_part,
            socket_n=None if socket is None else socket.n,
            socket_median_offset_sigma=None if socket is None else socket.offset_sigma,
            z_socket=None if socket is None else socket.z_within,
            socket_coherent_count=None if socket is None else socket.coherent_count,
            zone_n=None if zone is None else zone.n,
            zone_median_offset_sigma=None if zone is None else zone.offset_sigma,
            z_zone=None if zone is None else zone.z_within,
            tester_n=None if tester is None else tester.n,
            tester_median_offset_sigma=None if tester is None else tester.offset_sigma,
            z_tester=None if tester is None else tester.z_within,
            tester_spearman_rho=tester_rho,
            d2=evidence_d2,
            p_value=evidence_p,
            top_parameter=top_parameter,
            top_contribution=top_contribution,
            top_share=top_share,
            parameter_share=parameter_share,
            setup_claims=tuple(claims),
        )

    if not evaluated:
        notes.append("position metadata absent; part-only analysis")
        return AttributionResult(
            verdict=AttributionVerdict.INDETERMINATE,
            evidence=_evidence(),
            refusal_code=None,
            warning="; ".join(notes),
        )

    if len(claims) >= 2:
        notes.append(
            "conflicting setup evidence (" + ", ".join(claims) + "); declining to pick arbitrarily"
        )
        verdict = AttributionVerdict.INDETERMINATE
    elif len(claims) == 1:
        verdict = AttributionVerdict(claims[0])
    else:
        verdict = AttributionVerdict.PART
        if unevaluated:
            notes.append("not evaluated (metadata absent): " + ", ".join(unevaluated))

    return AttributionResult(
        verdict=verdict,
        evidence=_evidence(),
        refusal_code=None,
        warning="; ".join(notes) if notes else None,
    )
