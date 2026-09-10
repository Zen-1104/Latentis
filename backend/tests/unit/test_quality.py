"""Unit tests for sensor/data-quality evidence (T-409, D-039).

Implements TEST-QUAL-001/002/003/004/005 (defect behaviour), 007 (bounded
score battery incl. the ordered defect chain), 008 (per-part state incl.
the hand-computed combination), 009 (lot roll-up), 010 (never-imputed),
and 011 (risk/refusal integration) — all naming ``assess_quality`` /
``roll_up_quality`` for QG-CORE-01.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from typing import Any

import pytest

from backend.core.attribution import AttributionVerdict
from backend.core.quality import assess_quality, roll_up_quality
from backend.core.recommend import recommend
from backend.core.risk import compute_risk
from backend.core.safety import evaluate_safety


@pytest.mark.fast
def test_missing_data_degrades_without_imputation() -> None:
    """TEST-QUAL-001: absent observations deduct and are never filled in."""
    one_missing = assess_quality([10.0, None, 12.0, 12.0])
    assert one_missing.refusal_code is None
    assert one_missing.n_total == 4 and one_missing.n_valid == 3
    assert one_missing.score == pytest.approx(0.95)
    codes = [finding.code for finding in one_missing.findings]
    assert codes == ["MISSING_OBSERVATION"]
    assert one_missing.findings[0].count == 1

    two_missing = assess_quality([10.0, None, None, 12.0])
    assert two_missing.score == pytest.approx(0.90)
    assert two_missing.findings[0].count == 2
    assert two_missing.n_valid == 2


@pytest.mark.fast
def test_flatline_is_sensor_concern_not_part_failure() -> None:
    """TEST-QUAL-002: a stuck sensor degrades evidence; the part is not condemned.

    Three pins: the flatline finding with the hand-computed score, no
    verdict/disposition field on the result type, and no decision module
    importing quality (AST import-edge scan, mirroring TEST-CUSUM-009).
    """
    res = assess_quality([7.0, 7.0, 7.0, 7.0, 7.0])
    assert res.refusal_code is None
    assert res.score == pytest.approx(0.75)
    assert [finding.code for finding in res.findings] == ["FLATLINE"]
    assert res.n_valid == 5

    single = assess_quality([7.0])
    assert single.score == pytest.approx(1.0)
    assert single.findings == ()

    for forbidden in ("verdict", "band", "recommendation", "risk_index", "disposition"):
        assert not hasattr(res, forbidden), f"QualityResult must not carry {forbidden}"

    core_dir = Path("backend/core")
    assert core_dir.is_dir()
    readers: list[str] = []
    for py_file in core_dir.glob("*.py"):
        if py_file.name in ("quality.py", "__init__.py"):
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name == "quality" or name.startswith("quality."):
                    readers.append(f"{py_file.name}: {name}")
                if name == "backend.core.quality" or name.startswith("backend.core.quality."):
                    readers.append(f"{py_file.name}: {name}")
    assert not readers, f"Decision modules must not import quality: {readers}"


@pytest.mark.fast
def test_nonfinite_impossible_values_refused() -> None:
    """TEST-QUAL-003: corrupt/out-of-range data is excluded, never coerced."""
    nan_case = assess_quality([10.0, float("nan"), 12.0])
    assert nan_case.score == pytest.approx(0.90)
    assert [finding.code for finding in nan_case.findings] == ["NON_FINITE_VALUE"]
    assert nan_case.n_valid == 2

    inf_case = assess_quality([10.0, float("inf"), 12.0])
    assert [finding.code for finding in inf_case.findings] == ["NON_FINITE_VALUE"]

    lone_impossible = assess_quality([-5.0], lower_bound=0.0, upper_bound=100.0)
    assert lone_impossible.score == pytest.approx(0.0)
    assert [finding.code for finding in lone_impossible.findings] == ["IMPOSSIBLE_VALUE"]
    assert lone_impossible.n_valid == 0
    assert lone_impossible.warning is not None

    junk_series: list[Any] = [10.0, "12.0", 12.0]
    assert assess_quality(junk_series, lower_bound=0.0).refusal_code == "INVALID_INPUT"
    bool_series: list[Any] = [10.0, True, 12.0]
    assert assess_quality(bool_series).refusal_code == "INVALID_INPUT"
    not_a_series: Any = 10.0
    assert assess_quality(not_a_series).refusal_code == "INVALID_INPUT"

    assert assess_quality([10.0], lower_bound=100.0, upper_bound=0.0).refusal_code == (
        "INVALID_INPUT"
    )
    bad_bound: Any = "0.0"
    assert assess_quality([10.0], lower_bound=bad_bound).refusal_code == "INVALID_INPUT"
    assert assess_quality([10.0], lower_bound=float("nan")).refusal_code == "INVALID_INPUT"
    assert assess_quality([10.0], scale=0.0).refusal_code == "INVALID_INPUT"
    assert assess_quality([10.0], scale=-1.0).refusal_code == "INVALID_INPUT"
    bad_scale: Any = "2.0"
    assert assess_quality([10.0], scale=bad_scale).refusal_code == "INVALID_INPUT"
    assert assess_quality([10.0], n_censored=-1).refusal_code == "INVALID_INPUT"
    bool_censored: Any = True
    assert assess_quality([10.0], n_censored=bool_censored).refusal_code == "INVALID_INPUT"
    float_censored: Any = 2.5
    assert assess_quality([10.0], n_censored=float_censored).refusal_code == "INVALID_INPUT"


@pytest.mark.fast
def test_timestamp_gap_flagged() -> None:
    """TEST-QUAL-004: unexpected jumps and disorder are time findings."""
    one_gap = assess_quality([1.0, 2.0, 3.0, 4.0, 5.0], times=[0.0, 24.0, 48.0, 200.0, 224.0])
    assert one_gap.refusal_code is None
    assert one_gap.score == pytest.approx(0.95)
    assert [finding.code for finding in one_gap.findings] == ["TIMESTAMP_GAP"]
    assert one_gap.findings[0].count == 1
    assert one_gap.times_given is True

    # Steps 10, 90, 10, 90 against median 50: both 90s exceed 1.5 x 50.
    two_gaps = assess_quality([1.0, 2.0, 3.0, 4.0, 5.0], times=[0.0, 10.0, 100.0, 110.0, 200.0])
    assert two_gaps.score == pytest.approx(0.90)
    assert two_gaps.findings[0].count == 2

    # The nominal burn-in grid (24, 72, 72 against median 72) is not a gap.
    nominal = assess_quality([1.0, 2.0, 3.0, 4.0], times=[0.0, 24.0, 96.0, 168.0])
    assert nominal.score == pytest.approx(1.0)
    assert nominal.findings == ()

    # Unknown timestamps are gap occurrences, not silent skips.
    unknown_time = assess_quality([1.0, 2.0, 3.0], times=[0.0, None, 48.0])
    assert unknown_time.score == pytest.approx(0.95)
    assert [finding.code for finding in unknown_time.findings] == ["TIMESTAMP_GAP"]

    # Duplicate time is disorder, not a gap.
    duplicate = assess_quality([1.0, 2.0, 3.0, 4.0], times=[0.0, 24.0, 24.0, 48.0])
    assert duplicate.score == pytest.approx(0.95)
    assert [finding.code for finding in duplicate.findings] == ["TIMESTAMP_DISORDER"]

    # Time checks skipped entirely when no axis is supplied.
    assert assess_quality([1.0, 2.0, 3.0]).times_given is False

    short_times: Any = [0.0, 24.0]
    assert assess_quality([1.0, 2.0, 3.0], times=short_times).refusal_code == "INVALID_INPUT"
    nan_time: Any = [0.0, float("nan"), 48.0]
    assert assess_quality([1.0, 2.0, 3.0], times=nan_time).refusal_code == "INVALID_INPUT"


@pytest.mark.fast
def test_abrupt_discontinuity_investigated() -> None:
    """TEST-QUAL-005: an isolated spike is a finding; a level shift is not."""
    spike = assess_quality([10.0, 10.0, 10.0, 50.0, 10.0, 10.0], scale=2.0)
    assert spike.refusal_code is None
    assert spike.score == pytest.approx(0.90)
    assert [finding.code for finding in spike.findings] == ["DISCONTINUITY"]
    assert spike.findings[0].count == 1
    assert "3" in spike.findings[0].detail

    # A sustained level change is shift evidence (CUSUM/DPAT), not a glitch.
    level = assess_quality([10.0, 10.0, 10.0, 50.0, 50.0, 50.0], scale=2.0)
    assert level.score == pytest.approx(1.0)
    assert level.findings == ()

    # Without a caller scale the check is skipped, never guessed.
    assert assess_quality([10.0, 10.0, 10.0, 50.0, 10.0, 10.0]).findings == ()


@pytest.mark.fast
def test_quality_score_bounded() -> None:
    """TEST-QUAL-007: every emitted score lies in [0, 1], edges included."""
    assert assess_quality([10.0, 12.0, 11.0]).score == pytest.approx(1.0)
    assert assess_quality([10.0, 12.0, 11.0]).findings == ()

    assert assess_quality([10.0]).score == pytest.approx(1.0)

    empty = assess_quality([])
    assert empty.score == pytest.approx(0.0)
    assert [finding.code for finding in empty.findings] == ["EMPTY_SERIES"]

    # Sixteen missing plus a flatline deduct 1.05 past zero: the floor holds.
    floored = assess_quality([5.0] * 5 + [None] * 16)
    assert floored.score == 0.0
    assert floored.score is not None and 0.0 <= floored.score <= 1.0
    assert [finding.code for finding in floored.findings] == [
        "MISSING_OBSERVATION",
        "FLATLINE",
    ]

    # Ordered defect chain: each added defect class weakly lowers the score.
    base = assess_quality([10.0, 12.0, 11.0, 13.0])
    one_defect = assess_quality([10.0, None, 12.0, 11.0, 13.0])
    two_defects = assess_quality([10.0, None, float("nan"), 11.0, 13.0])
    assert base.score is not None and one_defect.score is not None
    assert two_defects.score is not None
    assert base.score == pytest.approx(1.0)
    assert one_defect.score == pytest.approx(0.95)
    assert two_defects.score == pytest.approx(0.85)
    assert base.score >= one_defect.score >= two_defects.score


@pytest.mark.fast
def test_per_part_quality_state() -> None:
    """TEST-QUAL-008: hand-computed combination with structure and echo."""
    # 1 missing (0.05) + 1 non-finite (0.10) + 1 impossible (0.10) +
    # 1 isolated spike (0.10) = 0.35 -> score 0.65 over 7 valid points.
    values: list[Any] = [10.0, None, 12.0, float("nan"), 200.0, 10.0, 10.0, 60.0, 10.0, 10.0]
    res = assess_quality(values, lower_bound=0.0, upper_bound=100.0, scale=2.0)
    assert res.refusal_code is None
    assert res.n_total == 10 and res.n_valid == 7 and res.n_censored == 0
    assert res.score == pytest.approx(0.65)
    assert [finding.code for finding in res.findings] == [
        "MISSING_OBSERVATION",
        "NON_FINITE_VALUE",
        "IMPOSSIBLE_VALUE",
        "DISCONTINUITY",
    ]
    assert [finding.count for finding in res.findings] == [1, 1, 1, 1]
    for finding in res.findings:
        assert finding.detail.strip() and finding.action.strip()
    assert res.scale == pytest.approx(2.0)
    assert res.lower_bound == pytest.approx(0.0) and res.upper_bound == pytest.approx(100.0)
    assert res.times_given is False

    # Flatline and missing combine: the valid subsequence stays constant.
    combo_flat = assess_quality([5.0, 5.0, None, 5.0])
    assert combo_flat.score == pytest.approx(0.70)
    assert [finding.code for finding in combo_flat.findings] == [
        "MISSING_OBSERVATION",
        "FLATLINE",
    ]

    # Censored metadata counts lightly without filling any value in.
    censored = assess_quality([10.0, 12.0, 11.0], n_censored=2)
    assert censored.score == pytest.approx(0.96)
    assert [finding.code for finding in censored.findings] == ["CENSORED_READING"]
    assert censored.findings[0].count == 2


@pytest.mark.fast
def test_lot_quality_roll_up() -> None:
    """TEST-QUAL-009: explicit equal-weight mean with counted exclusions."""
    roll = roll_up_quality([0.9, 0.8, None])
    assert roll.refusal_code is None
    assert roll.score == pytest.approx(0.85)
    assert roll.n_parts == 3 and roll.n_excluded == 1
    assert roll.warning is not None

    clean = roll_up_quality([1.0, 1.0, 1.0])
    assert clean.score == pytest.approx(1.0)
    assert clean.warning is None

    assert roll_up_quality([]).refusal_code == "INSUFFICIENT_DATA"
    assert roll_up_quality([None, None]).refusal_code == "INSUFFICIENT_DATA"
    assert roll_up_quality([None, None]).score is None

    bad_entry: list[Any] = [0.5, float("nan")]
    assert roll_up_quality(bad_entry).refusal_code == "INVALID_INPUT"
    over_entry: list[Any] = [0.5, 1.5]
    assert roll_up_quality(over_entry).refusal_code == "INVALID_INPUT"
    bool_entry: list[Any] = [True]
    assert roll_up_quality(bool_entry).refusal_code == "INVALID_INPUT"
    not_a_sequence: Any = 0.9
    assert roll_up_quality(not_a_sequence).refusal_code == "INVALID_INPUT"


@pytest.mark.fast
def test_invalid_values_never_imputed() -> None:
    """TEST-QUAL-010: corrupt input is counted and excluded; nothing is filled in."""
    values: list[Any] = [float("nan"), float("inf"), None]
    res = assess_quality(values, lower_bound=0.0, upper_bound=100.0)
    assert res.refusal_code is None
    assert res.score == pytest.approx(0.0)
    assert res.n_valid == 0
    assert [finding.code for finding in res.findings] == [
        "MISSING_OBSERVATION",
        "NON_FINITE_VALUE",
    ]
    assert res.findings[1].count == 2
    assert res.warning is not None

    # Structural pin: the result carries counts and a score only — no field
    # can smuggle a replacement observation value.
    field_names = {field.name for field in dataclasses.fields(res)}
    assert field_names == {
        "score",
        "findings",
        "n_total",
        "n_valid",
        "n_censored",
        "scale",
        "lower_bound",
        "upper_bound",
        "times_given",
        "refusal_code",
        "warning",
    }


@pytest.mark.fast
def test_quality_feeds_risk_refusal_contract() -> None:
    """TEST-QUAL-011: a produced score flows into risk_quality; the band never moves."""
    safety = evaluate_safety(12.1, 39.8, 32.3, 18.7, 50.0)
    degraded = compute_risk(7.5, safety, AttributionVerdict.PART, 0.65)
    pristine = compute_risk(7.5, safety, AttributionVerdict.PART, 1.0)
    assert degraded.refusal_code is None and pristine.refusal_code is None
    assert degraded.band == pristine.band == safety.band
    quality_terms = [comp for comp in degraded.components if comp.name == "quality"]
    assert len(quality_terms) == 1
    assert quality_terms[0].raw == pytest.approx(0.35)
    pristine_terms = [comp for comp in pristine.components if comp.name == "quality"]
    assert pristine_terms[0].raw == pytest.approx(0.0)

    # The chain below quality is untouched by its presence or absence.
    first = recommend(
        band=safety.band,
        absolute_fail=False,
        z_primary=7.5,
        attribution=AttributionVerdict.PART,
        predicted_margin_pct=safety.predicted_margin_pct,
    )
    _ = assess_quality([10.0, None, 12.0, 12.0])
    second = recommend(
        band=safety.band,
        absolute_fail=False,
        z_primary=7.5,
        attribution=AttributionVerdict.PART,
        predicted_margin_pct=safety.predicted_margin_pct,
    )
    assert first == second
