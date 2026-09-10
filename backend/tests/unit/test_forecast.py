"""Unit tests for the two-point 168 h forecast (T-307, FR-302..304).

Implements TEST-DRIFT-004, TEST-DRIFT-006, and TEST-DRIFT-010 (known-answer
naming ``forecast_v168`` for QG-CORE-01) against DRIFT_SPEC § 4 and § 7.
Residual-adoption cases live in ``test_residual.py`` (TEST-DRIFT-005).
"""

from __future__ import annotations

import math

import pytest

from backend.core.forecast import forecast_v168


@pytest.mark.fast
def test_insufficient_data_when_a_readpoint_is_missing() -> None:
    """TEST-DRIFT-004: missing v0/v24 populates no forecast field."""
    for v0, v24 in ((None, 18.7), (12.1, None), (None, None)):
        res = forecast_v168(v0, v24, 3.06)
        assert res.refusal_code == "INSUFFICIENT_DATA"
        assert res.point is None
        assert res.baseline_linear is None
        assert res.shape_point is None
        assert res.phi_168 is None
        assert res.amplitude is None


@pytest.mark.fast
def test_nonfinite_inputs_are_invalid_not_missing() -> None:
    """NaN/inf readings refuse as INVALID with no forecast field populated."""
    res = forecast_v168(float("nan"), 18.7, 3.06)
    assert res.refusal_code == "INVALID_INPUT"
    assert res.point is None and res.baseline_linear is None
    res = forecast_v168(12.1, float("inf"), 3.06)
    assert res.refusal_code == "INVALID_INPUT"
    res = forecast_v168(12.1, 18.7, float("nan"))
    assert res.refusal_code == "INVALID_INPUT"
    assert res.point is None


@pytest.mark.fast
def test_forecast_v168_point_and_baseline_known_answer() -> None:
    """TEST-DRIFT-010: DRIFT_SPEC § 8 worked example recomputed by hand."""
    res = forecast_v168(12.1, 18.7, 3.06)
    assert res.refusal_code is None
    # amplitude 6.6; shape 12.1 + 6.6*3.06 = 32.296; linear 12.1 + 6.6*7 = 58.3.
    assert res.amplitude == pytest.approx(6.6)
    assert res.shape_point == pytest.approx(32.296)
    assert res.point == pytest.approx(32.296)
    assert res.baseline_linear == pytest.approx(58.3)
    assert res.residual_applied is False
    assert res.residual_correction == pytest.approx(0.0)
    assert res.censored is False
    for value in (res.point, res.baseline_linear, res.shape_point):
        assert value is not None and math.isfinite(value)


@pytest.mark.fast
def test_censored_v24_handled_conservatively() -> None:
    """TEST-DRIFT-006: a below-LOD v24 widens, never narrows, the forecast."""
    phi = 3.0
    censored = forecast_v168(10.0, 12.0, phi, v24_censored="below_lod")
    truth_like = forecast_v168(10.0, 11.0, phi)
    assert censored.refusal_code is None and truth_like.refusal_code is None
    assert censored.censored is True
    assert censored.warning is not None and "conservatively" in censored.warning
    assert censored.point is not None and truth_like.point is not None
    # The reporting bound is the largest value the truth can take: the bound
    # consumed as v24 sits above any lower truth for upward drift (phi > 0).
    assert censored.point >= truth_like.point
    # Same numeric input with and without the flag agrees (flag never narrows).
    plain = forecast_v168(10.0, 12.0, phi)
    assert plain.point == censored.point


@pytest.mark.fast
def test_unknown_censor_flag_is_invalid() -> None:
    """An undeclared censoring state refuses instead of guessing."""
    res = forecast_v168(10.0, 12.0, 3.0, v24_censored="smudged")  # type: ignore[arg-type]
    assert res.refusal_code == "INVALID_INPUT"
    assert res.point is None


@pytest.mark.fast
def test_deterministic_repeated_execution() -> None:
    """INV-8: identical inputs give an identical forecast record twice."""
    first = forecast_v168(12.1, 18.7, 3.06, residual_correction=1.1)
    second = forecast_v168(12.1, 18.7, 3.06, residual_correction=1.1)
    assert first == second
