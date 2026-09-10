"""Sensor/data-quality evidence for LATENTIS numeric core (Phase 4, T-409).

Implements FR-103, FR-104, FR-107, the RISK_SCORING_SPEC § 2.4 quality term,
and the ARCHITECTURE § 9 failure rows at core level (D-039):

  - ``assess_quality`` inspects one measurement series and emits itemised
    findings plus a bounded ``data_quality_score`` in ``[0, 1]`` — the
    producer the ``compute_risk(data_quality_score)`` contract requires.
    No deduction schedule exists in any authoritative spec, so the linear
    per-occurrence schedule over named ``QUALITY_DEDUCTION_*`` rates is an
    `assumed`, documented, sweepable configuration (D-039), not a discovered
    truth.
  - ``roll_up_quality`` aggregates per-part scores into the FR-104 lot figure
    as an explicit equal-weight mean with counted exclusions.
  - Invalid observations are counted and excluded, never imputed: no NaN →
    mean, no inf → clip, no missing → fabricated value. A suspicious
    measurement degrades evidence; it never becomes a component verdict —
    the result carries no verdict, band, or disposition field, no decision
    module may import this one, and socket/chamber/tester/zone effects stay
    owned by the existing attribution logic (reused, never re-derived here).
  - Series-level scope only: small cohorts, duplicate ingest rows, and unit
    validation are lot/ingest-level signals owned by the ingest and lot
    layers (FR-103/FR-108, T-502); duplicate *times* and censored *counts*
    are visible at series level and handled here.

Constraints:
  - No numeric literals outside 0, 1, 2 (rates, factors, gates imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
  - Never returns NaN or inf: overflow refuses with ``INVALID_INPUT``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from backend.core.constants import (
    QUALITY_DEDUCTION_CENSORED,
    QUALITY_DEDUCTION_DISCONTINUITY,
    QUALITY_DEDUCTION_DISORDER,
    QUALITY_DEDUCTION_FLATLINE,
    QUALITY_DEDUCTION_GAP,
    QUALITY_DEDUCTION_IMPOSSIBLE,
    QUALITY_DEDUCTION_MISSING,
    QUALITY_DEDUCTION_NON_FINITE,
    QUALITY_DISCONTINUITY_SIGMA,
    QUALITY_GAP_STEP_FACTOR,
)
from backend.core.robust import median

QualityFindingCode = Literal[
    "MISSING_OBSERVATION",
    "NON_FINITE_VALUE",
    "IMPOSSIBLE_VALUE",
    "CENSORED_READING",
    "FLATLINE",
    "TIMESTAMP_GAP",
    "TIMESTAMP_DISORDER",
    "DISCONTINUITY",
    "EMPTY_SERIES",
]

QualityRefusalCode = Literal["INVALID_INPUT",]

QualityRollupRefusalCode = Literal[
    "INSUFFICIENT_DATA",
    "INVALID_INPUT",
]

_FINDING_ACTIONS: dict[str, str] = {
    "MISSING_OBSERVATION": "absent observation counted; nothing imputed into decision arithmetic",
    "NON_FINITE_VALUE": "corrupt observation excluded from all evidence; counted in deduction",
    "IMPOSSIBLE_VALUE": "out-of-range observation excluded from the valid subsequence; counted",
    "CENSORED_READING": "censored reading retained as censored upstream; counted, never coerced",
    "FLATLINE": "stuck-sensor evidence recorded; component verdict unaffected",
    "TIMESTAMP_GAP": "unexpected time jump recorded; confidence reduced via deduction",
    "TIMESTAMP_DISORDER": "duplicate or backward time recorded; series order by index preserved",
    "DISCONTINUITY": "isolated spike recorded; sustained shifts belong to CUSUM/DPAT evidence",
    "EMPTY_SERIES": "no observations supplied: quality 0.0 with no valid evidence",
}


@dataclass(frozen=True)
class QualityFinding:
    """One machine-readable quality finding with its count and action."""

    code: QualityFindingCode
    count: int
    detail: str
    action: str


@dataclass(frozen=True)
class QualityResult:
    """Immutable per-series quality state: bounded score + itemised findings."""

    score: float | None
    findings: tuple[QualityFinding, ...]
    n_total: int
    n_valid: int
    n_censored: int
    scale: float | None
    lower_bound: float | None
    upper_bound: float | None
    times_given: bool
    refusal_code: QualityRefusalCode | None = None
    warning: str | None = None


@dataclass(frozen=True)
class QualityRollup:
    """Immutable FR-104 lot roll-up over per-part quality scores."""

    score: float | None
    n_parts: int
    n_excluded: int
    refusal_code: QualityRollupRefusalCode | None = None
    warning: str | None = None


def _is_real_number(candidate: object) -> bool:
    """True for int/float values the core accepts as numbers (no bool, no text)."""
    return isinstance(candidate, (int, float)) and not isinstance(
        candidate, (bool, str, bytes, bytearray)
    )


def _quality_refusal(
    warning: str,
    n_total: int,
    n_censored: int,
    times_given: bool,
) -> QualityResult:
    """Build the canonical malformed-input refusal (no score, no findings)."""
    return QualityResult(
        score=None,
        findings=(),
        n_total=n_total,
        n_valid=0,
        n_censored=n_censored,
        scale=None,
        lower_bound=None,
        upper_bound=None,
        times_given=times_given,
        refusal_code="INVALID_INPUT",
        warning=warning,
    )


def assess_quality(
    values: Sequence[float | None],
    times: Sequence[float | None] | None = None,
    scale: float | None = None,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
    n_censored: int = 0,
) -> QualityResult:
    """Assess one measurement series: findings plus a bounded quality score.

    Args:
        values: Time-ordered observations; ``None`` marks a missing
            observation (counted, never filled in). NaN/inf entries are
            corrupt data (counted, excluded). Anything else non-numeric
            refuses the whole assessment.
        times: Optional elapsed-hours axis aligned with ``values``; ``None``
            entries mark unknown times (gap findings). Omitted entirely the
            time checks are skipped. Length must match ``values``.
        scale: Optional caller-supplied dispersion (same unit as values;
            typically the lot robust sigma) enabling discontinuity detection.
            Omitted the check is skipped.
        lower_bound: Optional plausible-range floor; upper_bound: ceiling.
            Out-of-range observations are impossible values (counted,
            excluded from the valid subsequence). Both or neither may be
            omitted; a crossed range refuses.
        n_censored: Count of censored readings represented by this series
            (FR-107 metadata, not values). Must be an integer >= 0.

    Returns:
        QualityResult with ``score`` in ``[0, 1]`` (0.0 when nothing valid
        was observed), the fired findings in fixed code order, the effective
        counts, and the echoed assessment configuration — or an explicit
        ``INVALID_INPUT`` refusal carrying no score.
    """
    if isinstance(n_censored, bool) or not isinstance(n_censored, int):
        return _quality_refusal(
            f"n_censored must be an integer >= 0, got {n_censored!r}", 0, 0, times is not None
        )
    if n_censored < 0:
        return _quality_refusal(
            f"n_censored must be an integer >= 0, got {n_censored!r}", 0, 0, times is not None
        )

    lo_val: float | None = None
    hi_val: float | None = None
    for bound, name in ((lower_bound, "lower_bound"), (upper_bound, "upper_bound")):
        if bound is None:
            continue
        if not _is_real_number(bound):
            return _quality_refusal(
                f"{name} is not a real number: {bound!r}", 0, n_censored, times is not None
            )
        as_float = float(bound)
        if not math.isfinite(as_float):
            return _quality_refusal(
                f"{name} is non-finite (NaN/inf): {bound!r}", 0, n_censored, times is not None
            )
        if name == "lower_bound":
            lo_val = as_float
        else:
            hi_val = as_float
    if lo_val is not None and hi_val is not None and lo_val > hi_val:
        return _quality_refusal(
            f"plausible range crossed: {lower_bound!r} > {upper_bound!r}",
            0,
            n_censored,
            times is not None,
        )

    scale_val: float | None = None
    if scale is not None:
        if not _is_real_number(scale):
            return _quality_refusal(
                f"scale is not a real number: {scale!r}", 0, n_censored, times is not None
            )
        parsed_scale = float(scale)
        if not math.isfinite(parsed_scale) or parsed_scale <= 0.0:
            return _quality_refusal(
                f"scale must be finite and strictly positive, got {scale!r}",
                0,
                n_censored,
                times is not None,
            )
        scale_val = parsed_scale

    try:
        series = list(values)
    except TypeError:
        return _quality_refusal(
            "values is not a sequence of observations", 0, n_censored, times is not None
        )
    n_total = len(series)

    time_axis: list[float | None] | None = None
    if times is not None:
        try:
            raw_times = list(times)
        except TypeError:
            return _quality_refusal(
                "times is not a sequence aligned with values", n_total, n_censored, True
            )
        if len(raw_times) != n_total:
            return _quality_refusal(
                f"times length {len(raw_times)} does not match values length {n_total}",
                n_total,
                n_censored,
                True,
            )
        parsed_times: list[float | None] = []
        for stamp in raw_times:
            if stamp is None:
                parsed_times.append(None)
                continue
            if not _is_real_number(stamp):
                return _quality_refusal(
                    f"timestamp is not a real number: {stamp!r}", n_total, n_censored, True
                )
            stamp_val = float(stamp)
            if not math.isfinite(stamp_val):
                return _quality_refusal(
                    f"timestamp is non-finite (NaN/inf): {stamp!r}", n_total, n_censored, True
                )
            parsed_times.append(stamp_val)
        time_axis = parsed_times

    n_missing = 0
    n_nonfinite = 0
    n_impossible = 0
    positions: list[int] = []
    clean: list[float] = []
    for position, entry in enumerate(series):
        if entry is None:
            n_missing += 1
            continue
        if not _is_real_number(entry):
            return _quality_refusal(
                f"observation is not a real number: {entry!r}",
                n_total,
                n_censored,
                time_axis is not None,
            )
        observed = float(entry)
        if not math.isfinite(observed):
            n_nonfinite += 1
            continue
        if (lo_val is not None and observed < lo_val) or (hi_val is not None and observed > hi_val):
            n_impossible += 1
            continue
        positions.append(position)
        clean.append(observed)
    n_valid = len(clean)

    n_gap = 0
    n_disorder = 0
    if time_axis is not None:
        finite_stamps: list[tuple[int, float]] = [
            (index, stamp) for index, stamp in enumerate(time_axis) if stamp is not None
        ]
        n_gap += sum(1 for stamp in time_axis if stamp is None)
        positive_steps: list[float] = []
        for first, second in pairwise(finite_stamps):
            step = second[1] - first[1]
            if not math.isfinite(step):
                return _quality_refusal(
                    "timestamp step overflowed float64 finite range",
                    n_total,
                    n_censored,
                    True,
                )
            if step <= 0.0:
                n_disorder += 1
            else:
                positive_steps.append(step)
        if positive_steps:
            step_median = median(positive_steps)
            gate = QUALITY_GAP_STEP_FACTOR * step_median
            n_gap += sum(1 for step in positive_steps if step > gate)

    is_flatline = n_valid >= 2 and all(value == clean[0] for value in clean)

    n_discontinuity = 0
    discontinuity_indices: list[int] = []
    if scale_val is not None:
        # Interior indices only: range(1, n_valid - 1) is empty below three
        # valid points, so short series skip the check structurally.
        gate_disc = QUALITY_DISCONTINUITY_SIGMA * scale_val
        if not math.isfinite(gate_disc):
            return _quality_refusal(
                "discontinuity gate overflowed float64 finite range",
                n_total,
                n_censored,
                time_axis is not None,
            )
        for middle in range(1, n_valid - 1):
            down_step = clean[middle] - clean[middle - 1]
            up_step = clean[middle + 1] - clean[middle]
            if not (math.isfinite(down_step) and math.isfinite(up_step)):
                return _quality_refusal(
                    "valid-subsequence step overflowed float64 finite range",
                    n_total,
                    n_censored,
                    time_axis is not None,
                )
            if abs(down_step) > gate_disc and abs(up_step) > gate_disc:
                n_discontinuity += 1
                discontinuity_indices.append(positions[middle])

    counts: dict[QualityFindingCode, int] = {
        "MISSING_OBSERVATION": n_missing,
        "NON_FINITE_VALUE": n_nonfinite,
        "IMPOSSIBLE_VALUE": n_impossible,
        "CENSORED_READING": n_censored,
        "FLATLINE": 1 if is_flatline else 0,
        "TIMESTAMP_GAP": n_gap,
        "TIMESTAMP_DISORDER": n_disorder,
        "DISCONTINUITY": n_discontinuity,
        "EMPTY_SERIES": 1 if n_total == 0 else 0,
    }
    rates: dict[QualityFindingCode, float] = {
        "MISSING_OBSERVATION": QUALITY_DEDUCTION_MISSING,
        "NON_FINITE_VALUE": QUALITY_DEDUCTION_NON_FINITE,
        "IMPOSSIBLE_VALUE": QUALITY_DEDUCTION_IMPOSSIBLE,
        "CENSORED_READING": QUALITY_DEDUCTION_CENSORED,
        "FLATLINE": QUALITY_DEDUCTION_FLATLINE,
        "TIMESTAMP_GAP": QUALITY_DEDUCTION_GAP,
        "TIMESTAMP_DISORDER": QUALITY_DEDUCTION_DISORDER,
        "DISCONTINUITY": QUALITY_DEDUCTION_DISCONTINUITY,
        "EMPTY_SERIES": 0.0,
    }
    deductions = 0.0
    for code, count in counts.items():
        if code == "EMPTY_SERIES":
            continue
        deductions += count * rates[code]
    if n_valid == 0:
        score = 0.0
    else:
        score = 1.0 - deductions
        if score < 0.0:
            score = 0.0

    findings: list[QualityFinding] = []
    for code in (
        "EMPTY_SERIES",
        "MISSING_OBSERVATION",
        "NON_FINITE_VALUE",
        "IMPOSSIBLE_VALUE",
        "CENSORED_READING",
        "FLATLINE",
        "TIMESTAMP_GAP",
        "TIMESTAMP_DISORDER",
        "DISCONTINUITY",
    ):
        fired: QualityFindingCode = code
        if counts[fired] <= 0:
            continue
        if fired == "FLATLINE":
            detail = f"all {n_valid} valid observations exactly equal"
        elif fired == "EMPTY_SERIES":
            detail = "series contains no observations"
        elif fired == "DISCONTINUITY":
            detail = f"isolated spikes confirmed at series indices {discontinuity_indices}"
        elif fired == "TIMESTAMP_GAP":
            detail = f"{counts[fired]} unexpected timestamp jumps vs the series cadence"
        elif fired == "TIMESTAMP_DISORDER":
            detail = f"{counts[fired]} duplicate or backward timestamp steps"
        elif fired == "CENSORED_READING":
            detail = f"{counts[fired]} censored readings counted, none coerced"
        elif fired == "IMPOSSIBLE_VALUE":
            detail = f"{counts[fired]} observations outside [{lo_val}, {hi_val}]"
        elif fired == "NON_FINITE_VALUE":
            detail = f"{counts[fired]} NaN/inf observations excluded"
        else:
            detail = f"{counts[fired]} absent observations; nothing imputed"
        findings.append(
            QualityFinding(
                code=fired, count=counts[fired], detail=detail, action=_FINDING_ACTIONS[fired]
            )
        )

    warning: str | None = None
    if n_valid == 0 and n_total > 0:
        warning = "no valid observations: score 0.0 with defects itemised, nothing imputed"
    return QualityResult(
        score=score,
        findings=tuple(findings),
        n_total=n_total,
        n_valid=n_valid,
        n_censored=n_censored,
        scale=scale_val,
        lower_bound=lo_val,
        upper_bound=hi_val,
        times_given=time_axis is not None,
        refusal_code=None,
        warning=warning,
    )


def roll_up_quality(scores: Sequence[float | None]) -> QualityRollup:
    """Aggregate per-part quality scores into the FR-104 lot figure.

    Explicit equal-weight mean over the assessable parts; ``None`` entries
    are excluded with a count (never diluted, never imputed). Anything that
    is not a finite score in ``[0, 1]`` refuses the whole roll-up.

    Args:
        scores: Per-part ``data_quality_score`` values; ``None`` marks a
            part with no assessable score (excluded, counted).

    Returns:
        QualityRollup with the mean score, the part counts, and the
        exclusion tally — or an explicit refusal when nothing assessable
        was supplied (``INSUFFICIENT_DATA``) or an entry is malformed
        (``INVALID_INPUT``).
    """
    try:
        entries = list(scores)
    except TypeError:
        return QualityRollup(
            score=None,
            n_parts=0,
            n_excluded=0,
            refusal_code="INVALID_INPUT",
            warning="scores is not a sequence of per-part quality scores",
        )
    usable: list[float] = []
    n_excluded = 0
    for entry in entries:
        if entry is None:
            n_excluded += 1
            continue
        if not _is_real_number(entry):
            return QualityRollup(
                score=None,
                n_parts=len(entries),
                n_excluded=n_excluded,
                refusal_code="INVALID_INPUT",
                warning=f"lot score entry is not a real number: {entry!r}",
            )
        value = float(entry)
        if not math.isfinite(value) or value < 0.0 or value > 1.0:
            return QualityRollup(
                score=None,
                n_parts=len(entries),
                n_excluded=n_excluded,
                refusal_code="INVALID_INPUT",
                warning=f"lot score entry must lie in [0, 1], got {entry!r}",
            )
        usable.append(value)
    if not usable:
        return QualityRollup(
            score=None,
            n_parts=len(entries),
            n_excluded=n_excluded,
            refusal_code="INSUFFICIENT_DATA",
            warning="no assessable part scores supplied: no lot figure",
        )
    mean_score = sum(usable) / len(usable)
    if not math.isfinite(mean_score):
        return QualityRollup(
            score=None,
            n_parts=len(entries),
            n_excluded=n_excluded,
            refusal_code="INVALID_INPUT",
            warning="lot score mean overflowed float64 finite range",
        )
    warning_result: str | None = None
    if n_excluded > 0:
        warning_result = f"{n_excluded} of {len(entries)} parts excluded (no assessable score)"
    return QualityRollup(
        score=mean_score,
        n_parts=len(entries),
        n_excluded=n_excluded,
        refusal_code=None,
        warning=warning_result,
    )
