"""Unit tests for adjusted boxplot and medcouple (T-302, TEST-STAT-006).

Pins Hubert & Vandervieren (2008) sign convention and worked example against
documented failure modes of naive implementations.
"""

from __future__ import annotations

import math

import pytest

from backend.core.constants import (
    ADJUSTED_BOXPLOT_K,
    ADJUSTED_BOXPLOT_MC_EXP_LOWER_NEG,
    ADJUSTED_BOXPLOT_MC_EXP_LOWER_POS,
    ADJUSTED_BOXPLOT_MC_EXP_UPPER_NEG,
    ADJUSTED_BOXPLOT_MC_EXP_UPPER_POS,
    TUKEY_MILD_MULTIPLIER,
)
from backend.core.robust import adjusted_boxplot, medcouple, quartiles


@pytest.mark.fast
def test_medcouple_sign_convention() -> None:
    """Hubert & Vandervieren (2008) worked example and sign convention (TEST-STAT-006).

    Failure mode: Naive implementations invert exponents (e.g. e^(+4*MC) on lower fence
    or e^(-3*MC) on upper fence for MC > 0), which erroneously tightens fences on the
    skewed tail and widens them on the short tail.

    Sign Convention Invariants:
      For MC > 0 (right-skewed):
        lower fence: Q1 - 1.5 * exp(-4 * MC) * IQR  (tightens: 1.5 * exp(-4*MC) < 1.5)
        upper fence: Q3 + 1.5 * exp(3 * MC) * IQR   (widens:   1.5 * exp(3*MC) > 1.5)
      For MC < 0 (left-skewed):
        lower fence: Q1 - 1.5 * exp(-3 * MC) * IQR  (widens: 1.5 * exp(-3*MC) > 1.5)
        upper fence: Q3 + 1.5 * exp(4 * MC) * IQR   (tightens: 1.5 * exp(4*MC) < 1.5)
    """
    # 1. Right-skewed distribution (log-normal-like tail)
    data_right = [1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.2, 3.0, 5.0, 10.0, 25.0]
    mc_pos = medcouple(data_right)
    assert mc_pos > 0.0, f"Expected positive medcouple for right-skewed data, got {mc_pos}"

    q1, _, q3 = quartiles(data_right)
    iqr = q3 - q1

    low_adj, high_adj = adjusted_boxplot(data_right, mc_value=mc_pos)

    # Verification: Upper fence widens compared to standard Tukey
    tukey_high = q3 + TUKEY_MILD_MULTIPLIER * iqr
    assert (
        high_adj > tukey_high
    ), "For MC > 0, adjusted upper fence must widen beyond standard Tukey"

    # Verification: Lower fence tightens compared to standard Tukey
    tukey_low = q1 - TUKEY_MILD_MULTIPLIER * iqr
    assert low_adj > tukey_low, "For MC > 0, adjusted lower fence must tighten towards Q1"

    # Exact formula validation
    expected_low = (
        q1 - ADJUSTED_BOXPLOT_K * math.exp(ADJUSTED_BOXPLOT_MC_EXP_LOWER_POS * mc_pos) * iqr
    )
    expected_high = (
        q3 + ADJUSTED_BOXPLOT_K * math.exp(ADJUSTED_BOXPLOT_MC_EXP_UPPER_POS * mc_pos) * iqr
    )
    assert low_adj == pytest.approx(expected_low)
    assert high_adj == pytest.approx(expected_high)

    # 2. Left-skewed distribution (negation / reflection of right-skewed)
    data_left = [-x for x in data_right]
    mc_neg = medcouple(data_left)
    assert mc_neg < 0.0, f"Expected negative medcouple for left-skewed data, got {mc_neg}"

    q1_l, _, q3_l = quartiles(data_left)
    iqr_l = q3_l - q1_l

    low_l, high_l = adjusted_boxplot(data_left, mc_value=mc_neg)

    # Verification: Lower fence widens compared to standard Tukey
    tukey_low_l = q1_l - TUKEY_MILD_MULTIPLIER * iqr_l
    assert low_l < tukey_low_l, "For MC < 0, adjusted lower fence must widen beyond standard Tukey"

    # Verification: Upper fence tightens compared to standard Tukey
    tukey_high_l = q3_l + TUKEY_MILD_MULTIPLIER * iqr_l
    assert high_l < tukey_high_l, "For MC < 0, adjusted upper fence must tighten towards Q3"

    # Exact formula validation
    expected_low_l = (
        q1_l - ADJUSTED_BOXPLOT_K * math.exp(ADJUSTED_BOXPLOT_MC_EXP_LOWER_NEG * mc_neg) * iqr_l
    )
    expected_high_l = (
        q3_l + ADJUSTED_BOXPLOT_K * math.exp(ADJUSTED_BOXPLOT_MC_EXP_UPPER_NEG * mc_neg) * iqr_l
    )
    assert low_l == pytest.approx(expected_low_l)
    assert high_l == pytest.approx(expected_high_l)


@pytest.mark.fast
def test_adjusted_boxplot_symmetric_reduces_to_tukey() -> None:
    """When MC == 0, adjusted boxplot reduces identically to Tukey fences (1.5 * IQR)."""
    # Symmetric data
    data_sym = [-10.0, -5.0, -2.0, 0.0, 2.0, 5.0, 10.0]
    mc = medcouple(data_sym)
    assert mc == pytest.approx(0.0, abs=1e-7)

    q1, _, q3 = quartiles(data_sym)
    iqr = q3 - q1

    low_adj, high_adj = adjusted_boxplot(data_sym, mc_value=0.0)
    assert low_adj == pytest.approx(q1 - 1.5 * iqr)
    assert high_adj == pytest.approx(q3 + 1.5 * iqr)
