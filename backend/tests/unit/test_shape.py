"""Unit tests for the shape estimator scalar (T-306, FR-302).

Implements TEST-DRIFT-009 (known-answer naming ``estimate_phi`` for
QG-CORE-01) plus curve-evaluation, refusal, and determinism cases for
``phi_at`` across the DRIFT_SPEC § 4.2 families.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from backend.core.shape import estimate_phi, phi_at


@pytest.mark.fast
def test_estimate_phi_known_answer_median_ratio() -> None:
    """TEST-DRIFT-009: hand-computed median of empirical ratios is 3.0."""
    v0 = np.array([10.0, 10.0, 10.0, 10.0, 10.0])
    v24 = np.array([12.0, 14.0, 16.0, 18.0, 20.0])
    v168 = np.array([14.0, 20.0, 28.0, 38.0, 50.0])
    # Per-part ratios: 4/2=2.0, 10/4=2.5, 18/6=3.0, 28/8=3.5, 40/10=4.0.
    res = estimate_phi(v0, v24, v168)
    assert res.refusal_code is None
    assert res.phi_168 == pytest.approx(3.0)
    assert res.n_used == 5
    assert res.n_skipped_zero_amplitude == 0
    assert res.n_skipped_nonfinite == 0
    assert res.family_param == pytest.approx(math.log(3.0) / math.log(7.0))
    assert res.phi_168 is not None and math.isfinite(res.phi_168)


@pytest.mark.fast
def test_phi_at_anchors_and_families() -> None:
    """Curve anchors: Phi(0)=0, Phi(24)=1, linear Phi(168)=7 for all families."""
    assert phi_at(0.0, 3.0, family="power_law") == 0.0
    assert phi_at(24.0, 3.0, family="power_law") == 1.0
    assert phi_at(24.0, None, family="linear") == 1.0
    assert phi_at(24.0, None, family="log_time", family_param=48.0) == 1.0
    assert phi_at(24.0, None, family="saturating", family_param=48.0) == 1.0
    assert phi_at(168.0, None, family="linear") == pytest.approx(7.0)
    # Power-law anchor reproduces the fitted scalar at the horizon exactly.
    assert phi_at(168.0, 3.0, family="power_law") == pytest.approx(3.0)
    # Sub-linear physics: n < 1 over-predicts linearly (D-006 direction).
    assert phi_at(168.0, 3.0, family="power_law") < 7.0


@pytest.mark.fast
def test_phi_at_rejects_malformed_inputs() -> None:
    """Malformed times, families, and parameters raise instead of NaN."""
    with pytest.raises(ValueError):
        phi_at(-1.0, 3.0, family="power_law")
    with pytest.raises(ValueError):
        phi_at(float("nan"), 3.0, family="power_law")
    with pytest.raises(ValueError):
        phi_at(48.0, 3.0, family="unknown")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        phi_at(48.0, None, family="power_law")
    with pytest.raises(ValueError):
        phi_at(48.0, -2.0, family="power_law")
    with pytest.raises(ValueError):
        phi_at(48.0, None, family="log_time")
    with pytest.raises(ValueError):
        phi_at(48.0, None, family="saturating", family_param=0.0)
