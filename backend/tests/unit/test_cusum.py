"""Unit tests for two-sided tabular CUSUM persistent-shift evidence (T-408, D-038).

Implements TEST-CUSUM-001/002 (hand-computed known answers naming
``cusum_evidence`` for QG-CORE-01), 003/004/005/006/007 (behavioural), and
009 (advisory authority: CUSUM cannot change a verdict).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from backend.core.attribution import AttributionVerdict
from backend.core.cusum import cusum_evidence
from backend.core.recommend import recommend

REF = 10.0
SCALE = 2.0
K = 0.5
H = 4.0


@pytest.mark.fast
def test_cusum_positive_shift_hand_computed() -> None:
    """TEST-CUSUM-001: three 10.0 then nine 12.0 accumulate S_high to 4.5."""
    # z = 0,0,0 then nine 1.0 steps: S grows 0.5/step from step 4, reaching
    # 4.0 at index 10 (not > 4.0) and 4.5 at index 11 (signal).
    values = [10.0, 10.0, 10.0] + [12.0] * 9
    res = cusum_evidence(values, REF, SCALE, k=K, h=H)
    assert res.refusal_code is None
    assert res.n_observations == 12 and res.n_gaps == 0
    assert res.s_high == pytest.approx(4.5)
    assert res.s_low == pytest.approx(0.0)
    assert res.signal_high is True and res.signal_low is False
    assert res.first_crossing_high == 11
    assert res.first_crossing_low is None
    assert res.k == pytest.approx(K) and res.h == pytest.approx(H)
    assert res.warning is None


@pytest.mark.fast
def test_cusum_negative_shift_hand_computed() -> None:
    """TEST-CUSUM-002: the mirror series accumulates S_low to 4.5 instead."""
    values = [10.0, 10.0, 10.0] + [8.0] * 9
    res = cusum_evidence(values, REF, SCALE, k=K, h=H)
    assert res.refusal_code is None
    assert res.s_low == pytest.approx(4.5)
    assert res.s_high == pytest.approx(0.0)
    assert res.signal_low is True and res.signal_high is False
    assert res.first_crossing_low == 11
    assert res.first_crossing_high is None


@pytest.mark.fast
def test_cusum_stable_signal_never_signals() -> None:
    """TEST-CUSUM-003: sub-allowance wobble keeps both accumulators at zero."""
    values = [10.0, 10.5, 9.5, 10.2, 9.8, 10.1, 9.9, 10.0]
    res = cusum_evidence(values, REF, SCALE, k=K, h=H)
    assert res.refusal_code is None
    assert res.s_high == pytest.approx(0.0)
    assert res.s_low == pytest.approx(0.0)
    assert res.signal_high is False and res.signal_low is False
    assert res.first_crossing_high is None and res.first_crossing_low is None


@pytest.mark.fast
def test_cusum_transient_spike_is_not_persistent() -> None:
    """TEST-CUSUM-004: one +2 sigma spike peaks at 1.5 and decays to zero."""
    values = [10.0] * 4 + [14.0] + [10.0] * 6
    res = cusum_evidence(values, REF, SCALE, k=K, h=H)
    assert res.refusal_code is None
    assert res.n_observations == 11
    assert res.signal_high is False and res.signal_low is False
    assert res.first_crossing_high is None
    # The spike contributed 2.0 - 0.5 = 1.5, then six -0.5 steps erased it.
    assert res.s_high == pytest.approx(0.0)
    assert res.s_low == pytest.approx(0.0)


@pytest.mark.fast
def test_cusum_gaps_pause_and_count() -> None:
    """TEST-CUSUM-005: a gap pauses without resetting and shifts indices."""
    gapless = [10.0, 10.0, 10.0] + [12.0] * 9
    gapped = [10.0, 10.0, 10.0, None] + [12.0] * 9
    plain = cusum_evidence(gapless, REF, SCALE, k=K, h=H)
    res = cusum_evidence(gapped, REF, SCALE, k=K, h=H)
    assert res.refusal_code is None
    assert res.n_gaps == 1 and res.n_observations == 12
    assert res.s_high == pytest.approx(plain.s_high)
    assert res.first_crossing_high == 12
    assert res.warning is not None and "gap" in res.warning

    all_gaps = cusum_evidence([None, None, None, None], REF, SCALE)
    assert all_gaps.refusal_code == "INSUFFICIENT_DATA"
    assert all_gaps.n_observations == 0 and all_gaps.n_gaps == 4
    assert all_gaps.s_high is None and all_gaps.s_low is None


@pytest.mark.fast
def test_cusum_short_series_is_insufficient_data() -> None:
    """TEST-CUSUM-006: fewer than 3 effective observations refuse honestly."""
    for short in ([], [10.0], [10.0, 12.0], [10.0, None, None]):
        res = cusum_evidence(short, REF, SCALE, k=K, h=H)
        assert res.refusal_code == "INSUFFICIENT_DATA"
        assert res.s_high is None and res.s_low is None
        assert res.signal_high is False and res.signal_low is False
        assert res.warning is not None and "effective observations" in res.warning
    two_point = cusum_evidence([10.0, 12.0], REF, SCALE)
    assert two_point.n_observations == 2


@pytest.mark.fast
def test_cusum_nonfinite_refuses_invalid_input() -> None:
    """TEST-CUSUM-007: non-finite or non-numeric inputs emit no statistic."""
    bad_series: list[list[Any]] = [
        [10.0, float("nan"), 12.0, 12.0],
        [10.0, float("inf"), 12.0, 12.0],
        [10.0, "12.0", 12.0, 12.0],
        [10.0, True, 12.0, 12.0],
    ]
    for bad in bad_series:
        res = cusum_evidence(bad, REF, SCALE, k=K, h=H)
        assert res.refusal_code == "INVALID_INPUT"
        assert res.s_high is None and res.s_low is None

    assert cusum_evidence([10.0] * 4, float("nan"), SCALE).refusal_code == "INVALID_INPUT"
    str_ref: Any = "10.0"
    str_scale: Any = "2.0"
    assert cusum_evidence([10.0] * 4, str_ref, SCALE).refusal_code == "INVALID_INPUT"
    assert cusum_evidence([10.0] * 4, REF, str_scale).refusal_code == "INVALID_INPUT"
    assert cusum_evidence([10.0] * 4, REF, 0.0).refusal_code == "INVALID_INPUT"
    assert cusum_evidence([10.0] * 4, REF, -1.0).refusal_code == "INVALID_INPUT"
    assert cusum_evidence([10.0] * 4, REF, float("inf")).refusal_code == "INVALID_INPUT"
    assert cusum_evidence([10.0] * 4, REF, SCALE, k=0.0, h=H).refusal_code == "INVALID_INPUT"
    assert cusum_evidence([10.0] * 4, REF, SCALE, k=K, h=-1.0).refusal_code == "INVALID_INPUT"
    assert (
        cusum_evidence([10.0] * 4, REF, SCALE, k=float("nan"), h=H).refusal_code == "INVALID_INPUT"
    )
    str_k: Any = "0.5"
    assert cusum_evidence([10.0] * 4, REF, SCALE, k=str_k, h=H).refusal_code == "INVALID_INPUT"
    not_a_series: Any = 10.0
    assert cusum_evidence(not_a_series, REF, SCALE).refusal_code == "INVALID_INPUT"


@pytest.mark.fast
def test_cusum_cannot_change_a_verdict() -> None:
    """TEST-CUSUM-009: advisory authority — CUSUM evidence moves no verdict.

    Three independent pins: the result type carries no decision-named field,
    no decision module references CUSUM (AST scan), and the Phase 3
    recommendation chain is byte-identical with CUSUM evidence computed
    alongside it or ignored entirely.
    """
    series = [10.0, 10.0, 10.0] + [12.0] * 9
    evidence = cusum_evidence(series, REF, SCALE, k=K, h=H)
    assert evidence.signal_high is True
    for forbidden in ("verdict", "band", "recommendation", "risk_index", "disposition"):
        assert not hasattr(evidence, forbidden), f"CusumResult must not carry {forbidden}"

    core_dir = Path("backend/core")
    assert core_dir.is_dir()
    readers: list[str] = []
    for py_file in core_dir.glob("*.py"):
        if py_file.name in ("cusum.py", "__init__.py"):
            # cusum.py is the module itself; __init__.py only re-exports its
            # public names (plumbing, not a read edge into any decision path).
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name == "cusum" or name.startswith("cusum."):
                    readers.append(f"{py_file.name}: {name}")
                if name == "backend.core.cusum" or name.startswith("backend.core.cusum."):
                    readers.append(f"{py_file.name}: {name}")
    assert not readers, f"Decision modules must not import CUSUM: {readers}"

    first = recommend(
        band="WATCH",
        absolute_fail=False,
        z_primary=17.4,
        attribution=AttributionVerdict.PART,
        predicted_margin_pct=0.269,
    )
    _alongside = cusum_evidence(series, REF, SCALE, k=K, h=H)
    second = recommend(
        band="WATCH",
        absolute_fail=False,
        z_primary=17.4,
        attribution=AttributionVerdict.PART,
        predicted_margin_pct=0.269,
    )
    assert first == second
