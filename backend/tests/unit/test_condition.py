"""Unit tests for minimal condition-aware context (T-410, D-040).

Implements TEST-COND-001 (hand-computed Arrhenius factor naming
``arrhenius_af`` for QG-CORE-01) and TEST-COND-002 (hand-derived
consistency truth table naming ``zone_arrhenius_consistent``).
"""

from __future__ import annotations

import inspect
import math
from typing import Any

import pytest

from backend.core.attribution import AttributionVerdict
from backend.core.condition import arrhenius_af, zone_arrhenius_consistent
from backend.core.risk import compute_risk
from backend.core.safety import evaluate_safety

EA = 0.7
T_REF = 125.0
T_HOT = 135.0
T_COOL = 115.0


@pytest.mark.fast
def test_arrhenius_af_hand_computed() -> None:
    """TEST-COND-001: Ea 0.7 eV from 125 C to 135 C gives AF ~1.6485."""
    # Tr = 398.15 K, Tz = 408.15 K; 1/Tr ~= 0.00251162, 1/Tz ~= 0.00245008;
    # diff ~= 6.1537e-05; Ea/k ~= 8123.16; exponent ~= 0.49987;
    # AF = e^0.49987 ~= 1.6485.
    af = arrhenius_af(T_HOT, T_REF, EA)
    assert af is not None and math.isfinite(af)
    assert af == pytest.approx(1.6485, abs=1e-3)
    assert af > 1.0

    assert arrhenius_af(T_REF, T_REF, EA) == 1.0

    cooler = arrhenius_af(T_COOL, T_REF, EA)
    assert cooler is not None and 0.0 < cooler < 1.0

    assert arrhenius_af(T_HOT, T_REF, 0.0) is None
    assert arrhenius_af(T_HOT, T_REF, -0.5) is None
    assert arrhenius_af(-273.15, T_REF, EA) is None
    assert arrhenius_af(-300.0, T_REF, EA) is None
    assert arrhenius_af(float("nan"), T_REF, EA) is None
    assert arrhenius_af(T_HOT, T_REF, float("inf")) is None
    text_temp: Any = "135.0"
    assert arrhenius_af(text_temp, T_REF, EA) is None
    assert arrhenius_af(None, T_REF, EA) is None
    assert arrhenius_af(T_HOT, None, EA) is None
    assert arrhenius_af(T_HOT, T_REF, None) is None
    # Deep-cryogenic zone against room reference underflows float64: the
    # true AF is positive but unrepresentable, so the function refuses.
    assert arrhenius_af(-259.0, 0.0, 1.0) is None


@pytest.mark.fast
def test_zone_consistency_truth_table() -> None:
    """TEST-COND-002: hotter/cooler/equal temps against agreeing/opposing shifts."""
    hot_agree = zone_arrhenius_consistent(T_HOT, T_REF, EA, 2.0, 1)
    assert hot_agree.refusal_code is None
    assert hot_agree.consistent is True
    assert hot_agree.af is not None and hot_agree.af == pytest.approx(1.6485, abs=1e-3)

    hot_oppose = zone_arrhenius_consistent(T_HOT, T_REF, EA, -2.0, 1)
    assert hot_oppose.consistent is False

    cool_agree = zone_arrhenius_consistent(T_COOL, T_REF, EA, -2.0, 1)
    assert cool_agree.consistent is True

    cool_oppose = zone_arrhenius_consistent(T_COOL, T_REF, EA, 2.0, 1)
    assert cool_oppose.consistent is False

    # Shrinking-parameter convention (direction -1) mirrors exactly.
    assert zone_arrhenius_consistent(T_HOT, T_REF, EA, -2.0, -1).consistent is True
    assert zone_arrhenius_consistent(T_HOT, T_REF, EA, 2.0, -1).consistent is False

    # No thermal difference: explicitly insufficient, never a guessed boolean.
    equal = zone_arrhenius_consistent(T_REF, T_REF, EA, 2.0, 1)
    assert equal.consistent is None and equal.refusal_code == "INSUFFICIENT_DATA"
    assert equal.af == 1.0

    # No shift observed despite a thermal difference: the explanation fails.
    assert zone_arrhenius_consistent(T_HOT, T_REF, EA, 0.0, 1).consistent is False

    # Missing metadata degrades; malformed metadata refuses.
    assert zone_arrhenius_consistent(None, T_REF, EA, 2.0, 1).refusal_code == ("INSUFFICIENT_DATA")
    assert zone_arrhenius_consistent(T_HOT, T_REF, EA, None, 1).refusal_code == (
        "INSUFFICIENT_DATA"
    )
    bad_direction: Any = 0
    assert zone_arrhenius_consistent(T_HOT, T_REF, EA, 2.0, bad_direction).refusal_code == (
        "INVALID_INPUT"
    )
    bool_direction: Any = True
    assert zone_arrhenius_consistent(T_HOT, T_REF, EA, 2.0, bool_direction).refusal_code == (
        "INVALID_INPUT"
    )
    assert zone_arrhenius_consistent(T_HOT, T_REF, 0.0, 2.0, 1).refusal_code == ("INVALID_INPUT")
    assert zone_arrhenius_consistent(-300.0, T_REF, EA, 2.0, 1).refusal_code == ("INVALID_INPUT")
    assert zone_arrhenius_consistent(T_HOT, T_REF, EA, float("nan"), 1).refusal_code == (
        "INVALID_INPUT"
    )

    # The predicate reads screening-time conditions only: no late-read-point
    # parameter exists on either signature (RT-002 name-scan spirit).
    for fn in (arrhenius_af, zone_arrhenius_consistent):
        for name in inspect.signature(fn).parameters:
            assert "96" not in name and "168" not in name

    # Specified integration: a consistent ZONE earns exactly the half credit,
    # and the band echoes untouched either way.
    safety = evaluate_safety(12.1, 39.8, 32.3, 18.7, 50.0)
    with_credit = compute_risk(
        7.5, safety, AttributionVerdict.ZONE, 0.9, zone_arrhenius_consistent=True
    )
    without_credit = compute_risk(
        7.5, safety, AttributionVerdict.ZONE, 0.9, zone_arrhenius_consistent=False
    )
    assert with_credit.band == without_credit.band == safety.band
    credit_terms = [comp for comp in with_credit.components if comp.name == "attribution_credit"]
    plain_terms = [comp for comp in without_credit.components if comp.name == "attribution_credit"]
    assert len(credit_terms) == 1 and len(plain_terms) == 1
    assert credit_terms[0].raw == pytest.approx(0.5)
    assert plain_terms[0].raw == pytest.approx(0.0)
