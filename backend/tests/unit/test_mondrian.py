"""Unit tests for the Mondrian fallback ladder (T-308, FR-307).

Implements TEST-CONF-004: all four ladder levels including
INSUFFICIENT_CALIBRATION, with the reported level matching the level used.
"""

from __future__ import annotations

import pytest

from backend.core.conformal import conformal_upper
from backend.core.constants import MONDRIAN_LEVEL_INSUFFICIENT

ALPHA = 0.10


def _residuals(n: int, start: float = 0.0) -> list[float]:
    """Deterministic ascending residuals (order-statistic friendly)."""
    return [start + float(i) for i in range(n)]


@pytest.mark.fast
def test_fallback_ladder_and_reported_level() -> None:
    """TEST-CONF-004: levels 0..3 resolve to the first attainable grouping."""
    group = _residuals(60)
    param = _residuals(120, start=100.0)
    marginal = _residuals(300, start=1000.0)

    # Level 0: fine cell clears n_min=50 and the quantile is attainable.
    res = conformal_upper(
        0.0,
        [group, param, marginal],
        level_names=["CMOS/iddq", "iddq", "marginal"],
        alpha=ALPHA,
    )
    assert res.refusal_code is None and res.mondrian_level == 0
    assert res.mondrian_group == "CMOS/iddq" and res.n_cal == 60

    # Level 1: thin fine cell (n=10 < 50) falls back to the parameter cell.
    res = conformal_upper(
        0.0,
        [_residuals(10), param, marginal],
        level_names=["CMOS/iddq", "iddq", "marginal"],
        alpha=ALPHA,
    )
    assert res.refusal_code is None and res.mondrian_level == 1
    assert res.mondrian_group == "iddq" and res.n_cal == 120

    # Level 2: fine and parameter cells unattainable (k > n) -> marginal.
    # n=5 at alpha=0.10 needs k=ceil(6*0.9)=6 > 5.
    res = conformal_upper(
        0.0,
        [_residuals(5), _residuals(5, 50.0), marginal],
        level_names=["CMOS/iddq", "iddq", "marginal"],
        alpha=ALPHA,
    )
    assert res.refusal_code is None and res.mondrian_level == 2
    assert res.mondrian_group == "marginal" and res.n_cal == 300

    # Level 3: even the marginal cannot support alpha -> INFINITE.
    res = conformal_upper(
        0.0,
        [_residuals(5), _residuals(5, 50.0), _residuals(5, 500.0)],
        level_names=["CMOS/iddq", "iddq", "marginal"],
        alpha=ALPHA,
    )
    assert res.refusal_code == "INSUFFICIENT_CALIBRATION"
    assert res.bound_finite is False and res.upper is None
    assert res.mondrian_level == MONDRIAN_LEVEL_INSUFFICIENT
    assert res.attainable_alpha == pytest.approx(1.0 / 6.0)
