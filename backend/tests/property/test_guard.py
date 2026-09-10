"""Property tests for the exchangeability guard (T-309, FR-308).

Implements TEST-CONF-006, naming ``check_exchangeability`` and ``psi`` for
QG-CORE-01: the PSI watch band degrades (WARN), novelty/shift voids (VOID),
and verdicts are deterministic and order-invariant. The guard never restores
the guarantee it voids (CONFORMAL_SPEC § 7, FINAL_STATUS L-04).
"""

from __future__ import annotations

import hypothesis.strategies as st
import numpy as np
import pytest
from hypothesis import given, settings

from backend.core.guard import check_exchangeability, psi


def _warn_pair() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Fixed-seed lot/calib pair with max PSI inside [0.10, 0.25] (WARN)."""
    lot_v0 = np.random.default_rng(101).normal(10.3, 1.0, 200)
    calib_v0 = np.random.default_rng(102).normal(10.0, 1.0, 2000)
    lot_d = np.random.default_rng(103).normal(2.0, 0.5, 200)
    calib_d = np.random.default_rng(104).normal(2.0, 0.5, 2000)
    return lot_v0, calib_v0, lot_d, calib_d


@pytest.mark.property
@settings(max_examples=60)
@given(
    shift=st.floats(min_value=3.0, max_value=8.0, allow_nan=False, allow_infinity=False),
    seed=st.integers(min_value=0, max_value=10000),
)
def test_check_exchangeability_and_psi_watch_warn_void(shift: float, seed: int) -> None:
    """TEST-CONF-006: psi bands drive WARN/VOID; verdicts are order-invariant."""
    lot_v0, calib_v0, lot_d, calib_d = _warn_pair()

    warn = check_exchangeability(
        lot_v0=lot_v0,
        lot_delta24=lot_d,
        calib_v0=calib_v0,
        calib_delta24=calib_d,
    )
    assert warn.verdict == "WARN"
    assert warn.guarantee_status == "DEGRADED"
    assert warn.signals_fired == ()
    assert warn.max_psi is not None and 0.10 <= warn.max_psi <= 0.25
    assert warn.warning is not None and "DEGRADED" in warn.warning

    # Direct psi wiring: identical samples score ~0; gross shift fires.
    assert psi(calib_v0, calib_v0) == pytest.approx(0.0, abs=1e-9)
    rng = np.random.default_rng(seed)
    shifted = rng.normal(10.0 + shift, 1.0, 200)
    assert psi(shifted, calib_v0) is not None
    assert psi(shifted, calib_v0) > 0.25  # type: ignore[operator]

    void = check_exchangeability(
        lot_v0=shifted,
        lot_delta24=lot_d,
        calib_v0=calib_v0,
        calib_delta24=calib_d,
        group_key="UNSEEN/group",
        calib_group_keys=["CMOS/iddq"],
    )
    assert void.verdict == "VOID"
    assert void.guarantee_status == "VOID"
    assert "group_novelty" in void.signals_fired

    # Order invariance + determinism: shuffling the lot never moves the verdict.
    perm = np.random.default_rng(seed + 1).permutation(len(lot_v0))
    replay = check_exchangeability(
        lot_v0=lot_v0[perm],
        lot_delta24=lot_d[perm],
        calib_v0=calib_v0,
        calib_delta24=calib_d,
    )
    assert replay.verdict == warn.verdict
    assert replay.signals_fired == warn.signals_fired
    assert replay == warn
