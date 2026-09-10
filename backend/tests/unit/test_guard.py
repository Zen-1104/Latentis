"""Unit tests for the six-signal exchangeability guard (T-309, FR-308).

Behavioural coverage of CONFORMAL_SPEC § 5.1-§ 5.2: each signal fires on its
own, PASS holds when nothing fires, and missing references degrade to
unevaluated warnings rather than crashes. The registered property test naming
``check_exchangeability`` and ``psi`` for QG-CORE-01 lives in
``backend/tests/property/test_guard.py`` (TEST-CONF-006).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from backend.core.guard import check_exchangeability, psi


def _base_lot(n: int = 120, seed: int = 30609) -> tuple[np.ndarray, np.ndarray]:
    """Lot v0 and delta_24 samples plus matching calibration references."""
    rng = np.random.default_rng(seed)
    v0 = rng.normal(loc=10.0, scale=1.0, size=n)
    delta = rng.normal(loc=2.0, scale=0.5, size=n)
    return v0, delta


def _pass_inputs() -> dict[str, Any]:
    """PASS-disciplined inputs: large same-distribution samples (PSI ~0.02)."""
    rng_lot = np.random.default_rng(1001)
    rng_cal = np.random.default_rng(2001)
    lot_v0 = rng_lot.normal(loc=10.0, scale=1.0, size=500)
    lot_d = rng_lot.normal(loc=2.0, scale=0.5, size=500)
    return {
        "lot_v0": lot_v0,
        "lot_delta24": lot_d,
        "calib_v0": rng_cal.normal(loc=10.0, scale=1.0, size=3000),
        "calib_delta24": rng_cal.normal(loc=2.0, scale=0.5, size=3000),
        "calib_lot_medians": rng_cal.normal(loc=10.0, scale=0.2, size=40),
        "lot_temperatures": np.full(500, 125.0),
        "calib_temperatures": np.full(3000, 125.0),
        "tester_id": "T-01",
        "calib_tester_ids": ["T-01", "T-02"],
        "group_key": "CMOS/iddq",
        "calib_group_keys": ["CMOS/iddq"],
    }


@pytest.mark.fast
def test_pass_when_nothing_fires() -> None:
    """Identical lot/calib distributions give PASS / VALID."""
    res = check_exchangeability(**_pass_inputs())
    assert res.verdict == "PASS"
    assert res.guarantee_status == "VALID"
    assert res.signals_fired == ()
    assert res.max_psi is not None and math.isfinite(res.max_psi)
    assert res.max_psi < 0.10


@pytest.mark.fast
def test_feature_shift_fires_on_shifted_lot() -> None:
    """A grossly shifted lot distribution fires the PSI signal to VOID."""
    lot_v0 = np.random.default_rng(30609).normal(loc=16.0, scale=1.0, size=120)
    lot_d = np.random.default_rng(30609).normal(loc=2.0, scale=0.5, size=120)
    calib_v0 = np.random.default_rng(30609).normal(loc=10.0, scale=1.0, size=800)
    calib_d = np.random.default_rng(30609).normal(loc=2.0, scale=0.5, size=800)
    assert psi(lot_v0, calib_v0) is not None
    assert psi(lot_v0, calib_v0) > 0.25  # type: ignore[operator]
    res = check_exchangeability(
        lot_v0=lot_v0,
        lot_delta24=lot_d,
        calib_v0=calib_v0,
        calib_delta24=calib_d,
    )
    assert res.verdict == "VOID"
    assert res.guarantee_status == "VOID"
    assert "feature_shift:v0" in res.signals_fired
    assert res.warning is not None and "does not restore" in res.warning


@pytest.mark.fast
def test_lot_centre_shift_fires() -> None:
    """A lot median far from the calibration medians fires to VOID."""
    lot_v0 = np.random.default_rng(30609).normal(loc=13.0, scale=0.2, size=120)
    lot_d = np.random.default_rng(30609).normal(loc=2.0, scale=0.5, size=120)
    calib_v0 = np.random.default_rng(30609).normal(loc=13.0, scale=0.2, size=800)
    calib_d = np.random.default_rng(30609).normal(loc=2.0, scale=0.5, size=800)
    calib_meds = np.random.default_rng(30609).normal(loc=10.0, scale=0.2, size=40)
    res = check_exchangeability(
        lot_v0=lot_v0,
        lot_delta24=lot_d,
        calib_v0=calib_v0,
        calib_delta24=calib_d,
        calib_lot_medians=calib_meds,
    )
    assert "lot_centre_shift" in res.signals_fired
    assert res.verdict == "VOID"


@pytest.mark.fast
def test_amplitude_shift_fires_on_ks() -> None:
    """A changed delta_24 distribution fires the KS signal to VOID."""
    lot_v0 = np.random.default_rng(30609).normal(loc=10.0, scale=1.0, size=200)
    lot_d = np.random.default_rng(30609).normal(loc=6.0, scale=0.5, size=200)
    calib_v0 = np.random.default_rng(30609).normal(loc=10.0, scale=1.0, size=800)
    calib_d = np.random.default_rng(30609).normal(loc=2.0, scale=0.5, size=800)
    res = check_exchangeability(
        lot_v0=lot_v0,
        lot_delta24=lot_d,
        calib_v0=calib_v0,
        calib_delta24=calib_d,
    )
    assert "amplitude_shift" in res.signals_fired
    assert res.verdict == "VOID"


@pytest.mark.fast
def test_temperature_outside_range_fires() -> None:
    """A hot lot mean outside the calibration range fires to VOID."""
    lot_v0, lot_d = _base_lot()
    res = check_exchangeability(
        lot_v0=lot_v0,
        lot_delta24=lot_d,
        calib_v0=np.random.default_rng(30609).normal(loc=10.0, scale=1.0, size=800),
        calib_delta24=np.random.default_rng(30609).normal(loc=2.0, scale=0.5, size=800),
        lot_temperatures=np.full(120, 140.0),
        calib_temperatures=np.random.default_rng(30609).normal(loc=125.0, scale=1.0, size=800),
    )
    assert "temperature_range" in res.signals_fired
    assert res.verdict == "VOID"


@pytest.mark.fast
def test_tester_and_group_novelty_fire() -> None:
    """Unseen tester and unseen group each force VOID on their own."""
    lot_v0, lot_d = _base_lot()
    kwargs: dict[str, Any] = {
        "lot_v0": lot_v0,
        "lot_delta24": lot_d,
        "calib_v0": np.random.default_rng(30609).normal(loc=10.0, scale=1.0, size=800),
        "calib_delta24": np.random.default_rng(30609).normal(loc=2.0, scale=0.5, size=800),
    }
    res_tester = check_exchangeability(
        **kwargs,
        tester_id="T-99",
        calib_tester_ids=["T-01", "T-02"],
    )
    assert "tester_novelty" in res_tester.signals_fired
    assert res_tester.verdict == "VOID"
    res_group = check_exchangeability(
        **kwargs,
        group_key="GAN/iddq",
        calib_group_keys=["CMOS/iddq"],
    )
    assert "group_novelty" in res_group.signals_fired
    assert res_group.verdict == "VOID"


@pytest.mark.fast
def test_missing_references_are_unevaluated_not_fired() -> None:
    """Absent references warn honestly instead of firing or crashing."""
    lot_v0, lot_d = _base_lot()
    res = check_exchangeability(lot_v0=lot_v0, lot_delta24=lot_d)
    assert res.verdict in ("PASS", "WARN")
    assert res.signals_fired == ()
    assert res.warning is not None and "unevaluated" in res.warning
    for signal in res.signals:
        assert signal.value is None or math.isfinite(signal.value)


@pytest.mark.fast
def test_guard_outputs_never_nonfinite() -> None:
    """No signal value, PSI, or summary is ever NaN/inf (INV-1)."""
    lot_v0, lot_d = _base_lot()
    calib_d = np.random.default_rng(30609).normal(loc=2.0, scale=0.5, size=800)
    res = check_exchangeability(
        lot_v0=np.concatenate([lot_v0, [float("inf"), float("nan")]]),
        lot_delta24=lot_d,
        calib_v0=np.random.default_rng(30609).normal(loc=10.0, scale=1.0, size=800),
        calib_delta24=calib_d,
        tester_id="T-01",
        calib_tester_ids=None,
    )
    assert res.max_psi is None or math.isfinite(res.max_psi)
    for signal in res.signals:
        assert signal.value is None or math.isfinite(signal.value)
