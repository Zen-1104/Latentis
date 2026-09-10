"""Unit tests for the PDA lot roll-up (T-311, FR-407).

Implements TEST-RISK-005 (hand-counted roll-up with both figures) and
TEST-RISK-007 (known-answer naming ``roll_up_lot`` for QG-CORE-01) against
RISK_SCORING_SPEC § 5.
"""

from __future__ import annotations

import pytest

from backend.core.risk import roll_up_lot


@pytest.mark.fast
def test_pda_rollup_and_second_figure() -> None:
    """TEST-RISK-005: hand-counted lot gives both PDA figures and REVIEW."""
    bands = ["REJECT"] + ["EARLY_WARNING"] + ["SAFE"] * 18
    res = roll_up_lot(bands)
    assert res.refusal_code is None
    assert res.n_tested == 20
    assert res.n_reject == 1
    assert res.n_early_warning == 1
    assert res.n_excluded == 0
    # 100*1/20 = 5.0: not above the 5.0 limit, inside (4.0, 5.0] -> REVIEW.
    assert res.pda_pct == pytest.approx(5.0)
    assert res.pda_pct_including_early_warning == pytest.approx(10.0)
    assert res.pda_limit_pct == pytest.approx(5.0)
    assert res.lot_verdict == "REVIEW"


@pytest.mark.fast
def test_roll_up_lot_fail_and_pass_rows() -> None:
    """TEST-RISK-007: roll_up_lot FAIL_LOT/PASS_LOT rows recomputed by hand."""
    failing = roll_up_lot(["REJECT", "REJECT", "SAFE"] + ["SAFE"] * 17)
    assert failing.refusal_code is None
    assert failing.n_tested == 20 and failing.n_reject == 2
    assert failing.pda_pct == pytest.approx(10.0)
    assert failing.lot_verdict == "FAIL_LOT"

    passing = roll_up_lot(["SAFE"] * 40)
    assert passing.n_tested == 40 and passing.n_reject == 0
    assert passing.pda_pct == pytest.approx(0.0)
    assert passing.pda_pct_including_early_warning == pytest.approx(0.0)
    assert passing.lot_verdict == "PASS_LOT"

    absolute = roll_up_lot(["SAFE", "SAFE", None], [False, True, False])
    assert absolute.n_tested == 2
    assert absolute.n_reject == 1
    assert absolute.n_excluded == 1
    assert absolute.pda_pct == pytest.approx(50.0)
    assert absolute.lot_verdict == "FAIL_LOT"


@pytest.mark.fast
def test_roll_up_refusals_and_invalid_bands() -> None:
    """Malformed lots refuse explicitly; exclusions are counted, not hidden."""
    empty = roll_up_lot([])
    assert empty.refusal_code == "INSUFFICIENT_DATA"
    assert empty.lot_verdict is None

    all_refused = roll_up_lot([None, None])
    assert all_refused.refusal_code == "INSUFFICIENT_DATA"
    assert all_refused.n_excluded == 2

    mismatched = roll_up_lot(["SAFE"], [True, False])
    assert mismatched.refusal_code == "INVALID_INPUT"

    unknown = roll_up_lot(["MAYBE"])
    assert unknown.refusal_code == "INVALID_INPUT"

    bad_limit = roll_up_lot(["SAFE"], None, -1.0)
    assert bad_limit.refusal_code == "INVALID_INPUT"
