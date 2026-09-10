"""Property tests for robust statistical estimators (T-302, TEST-STAT-003).

Pins invariant FR-202:
  f(c*x) = c * f(x) for median, IQR, MAD, and robust sigma (scale equivariance)
  f(x + c) = f(x) + c for median (shift equivariance)
  f(x + c) = f(x) for IQR, MAD, and robust sigma (shift invariance)
"""

from __future__ import annotations

import hypothesis.strategies as st
import numpy as np
import pytest
from hypothesis import given, settings

from backend.core.robust import (
    median,
    quartiles,
    robust_stats,
)


@pytest.mark.property
@settings(max_examples=100)
@given(
    arr=st.lists(
        st.floats(
            min_value=-500.0,
            max_value=500.0,
            allow_nan=False,
            allow_infinity=False,
            allow_subnormal=False,
        ).map(lambda v: round(v, 5)),
        min_size=4,
        max_size=50,
    ),
    c_shift=st.floats(
        min_value=-200.0,
        max_value=200.0,
        allow_nan=False,
        allow_infinity=False,
        allow_subnormal=False,
    ).map(lambda v: round(v, 4)),
    c_scale=st.floats(
        min_value=0.05,
        max_value=50.0,
        allow_nan=False,
        allow_infinity=False,
        allow_subnormal=False,
    ).map(lambda v: round(v, 4)),
)
def test_scale_and_shift_equivariance(
    arr: list[float],
    c_shift: float,
    c_scale: float,
) -> None:
    """Invariant: f(cx)=c*f(x) and f(x+c)=f(x)+c / f(x+c)=f(x).

    Satisfies TEST-STAT-003, FR-202.
    """
    x = np.array(arr, dtype=np.float64)

    # Base estimates
    res_base = robust_stats(x)
    med_base = median(x)
    q1_base, _, q3_base = quartiles(x)
    iqr_base = q3_base - q1_base
    mad_base = res_base.mad
    sigma_base = res_base.robust_sigma

    # --- Shift Equivariance / Invariance ---
    x_shifted = x + c_shift
    res_shifted = robust_stats(x_shifted)
    med_shifted = median(x_shifted)
    q1_s, _, q3_s = quartiles(x_shifted)
    iqr_shifted = q3_s - q1_s

    # Median shifts by c
    assert med_shifted == pytest.approx(med_base + c_shift, rel=1e-5, abs=1e-6)
    # Dispersion measures are shift-invariant
    assert iqr_shifted == pytest.approx(iqr_base, rel=1e-5, abs=1e-6)
    assert res_shifted.mad == pytest.approx(mad_base, rel=1e-5, abs=1e-6)
    assert res_shifted.robust_sigma == pytest.approx(sigma_base, rel=1e-5, abs=1e-6)

    # --- Scale Equivariance ---
    x_scaled = x * c_scale
    res_scaled = robust_stats(x_scaled)
    med_scaled = median(x_scaled)
    q1_c, _, q3_c = quartiles(x_scaled)
    iqr_scaled = q3_c - q1_c

    # Median, IQR, MAD, and robust_sigma scale by c_scale
    assert med_scaled == pytest.approx(c_scale * med_base, rel=1e-5, abs=1e-6)
    assert iqr_scaled == pytest.approx(c_scale * iqr_base, rel=1e-5, abs=1e-6)
    assert res_scaled.mad == pytest.approx(c_scale * mad_base, rel=1e-5, abs=1e-6)
    assert res_scaled.robust_sigma == pytest.approx(c_scale * sigma_base, rel=1e-5, abs=1e-6)
