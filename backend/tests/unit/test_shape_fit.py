"""Unit tests for group shape fitting on training lots (T-306, FR-302).

Implements TEST-DRIFT-003 plus degenerate, malformed, and determinism cases
against DRIFT_SPEC § 4 and the D-036 estimation rule (robust median of
per-part empirical ratios, train-lots-only provenance).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from backend.core.shape import estimate_phi


def _trajectories() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Five hand-computed training trajectories with ratios 2..4 (median 3)."""
    v0 = np.array([10.0, 10.0, 10.0, 10.0, 10.0])
    v24 = np.array([12.0, 14.0, 16.0, 18.0, 20.0])
    v168 = np.array([14.0, 20.0, 28.0, 38.0, 50.0])
    lots = ["LOT-A", "LOT-A", "LOT-A", "LOT-A", "LOT-A"]
    return v0, v24, v168, lots


@pytest.mark.fast
def test_group_shape_fitted_on_train_lots_only() -> None:
    """TEST-DRIFT-003: recorded lots are a subset of the train lots."""
    v0 = np.array([10.0, 10.0, 10.0, 50.0, 50.0, 50.0])
    v24 = np.array([12.0, 14.0, 16.0, 52.0, 54.0, 56.0])
    v168 = np.array([14.0, 20.0, 28.0, 100.0, 120.0, 140.0])
    lots = ["TRAIN-1", "TRAIN-1", "TRAIN-1", "HELDOUT-9", "HELDOUT-9", "HELDOUT-9"]

    res = estimate_phi(v0, v24, v168, lot_ids=lots, train_lot_ids=["TRAIN-1"])

    assert res.refusal_code is None
    assert res.phi_168 is not None
    assert res.lots_used is not None
    assert set(res.lots_used) <= {"TRAIN-1"}
    assert res.n_excluded_by_train_filter == 3
    assert res.n_used == 3
    # Train-only ratios are 2.0, 2.5, 3.0 -> median 2.5 (held-out excluded).
    assert res.phi_168 == pytest.approx(2.5)


@pytest.mark.fast
def test_train_filter_without_lot_ids_is_invalid() -> None:
    """A train allow-list without lot identities cannot enforce the leak rule."""
    v0, v24, v168, _ = _trajectories()
    res = estimate_phi(v0, v24, v168, train_lot_ids=["TRAIN-1"])
    assert res.refusal_code == "INVALID_INPUT"
    assert res.phi_168 is None


@pytest.mark.fast
def test_zero_amplitude_parts_skipped_not_fatal() -> None:
    """Zero 24 h amplitude carries no shape information; others still fit."""
    v0 = np.array([10.0, 10.0, 10.0, 10.0, 10.0])
    v24 = np.array([10.0, 14.0, 16.0, 18.0, 20.0])
    v168 = np.array([10.0, 20.0, 28.0, 38.0, 50.0])
    res = estimate_phi(v0, v24, v168)
    assert res.refusal_code is None
    assert res.n_skipped_zero_amplitude == 1
    assert res.n_used == 4
    assert res.phi_168 is not None and math.isfinite(res.phi_168)


@pytest.mark.fast
def test_all_zero_amplitude_is_no_variation() -> None:
    """A cohort with no drift amplitude leaves the shape unidentifiable."""
    v0 = np.full(5, 10.0)
    v24 = np.full(5, 10.0)
    v168 = np.array([11.0, 12.0, 13.0, 14.0, 15.0])
    res = estimate_phi(v0, v24, v168)
    assert res.refusal_code == "NO_VARIATION"
    assert res.phi_168 is None


@pytest.mark.fast
def test_insufficient_cohort_refuses() -> None:
    """Fewer than three usable trajectories cannot support a shape fit."""
    res = estimate_phi(
        np.array([10.0, 10.0]),
        np.array([12.0, 14.0]),
        np.array([14.0, 20.0]),
    )
    assert res.refusal_code == "INSUFFICIENT_COHORT"
    assert res.phi_168 is None


@pytest.mark.fast
def test_nonfinite_entries_skipped_with_counts() -> None:
    """NaN/inf readings never enter the median; the counts say so."""
    v0 = np.array([10.0, 10.0, 10.0, 10.0, 10.0])
    v24 = np.array([12.0, 14.0, np.nan, 18.0, 20.0])
    v168 = np.array([14.0, 20.0, 28.0, np.inf, 50.0])
    res = estimate_phi(v0, v24, v168)
    assert res.n_skipped_nonfinite == 2
    assert res.n_used == 3
    assert res.phi_168 is not None and math.isfinite(res.phi_168)


@pytest.mark.fast
def test_length_mismatch_and_bad_family_are_invalid() -> None:
    """Malformed trajectory vectors and unknown families refuse explicitly."""
    bad_len = estimate_phi(np.array([1.0, 2.0]), np.array([1.0]), np.array([1.0, 2.0]))
    assert bad_len.refusal_code == "INVALID_INPUT"
    v0, v24, v168, _ = _trajectories()
    bad_family = estimate_phi(v0, v24, v168, family="polynomial")  # type: ignore[arg-type]
    assert bad_family.refusal_code == "INVALID_INPUT"


@pytest.mark.fast
def test_deterministic_repeated_execution() -> None:
    """INV-8: the same trajectories give a byte-identical estimate twice."""
    v0, v24, v168, lots = _trajectories()
    first = estimate_phi(v0, v24, v168, lot_ids=lots)
    second = estimate_phi(v0, v24, v168, lot_ids=lots)
    assert first == second


@pytest.mark.fast
def test_row_permutation_invariance() -> None:
    """The median fit does not depend on trajectory order (INV-2 spirit)."""
    v0, v24, v168, _ = _trajectories()
    order = np.array([4, 2, 0, 3, 1])
    res = estimate_phi(v0, v24, v168)
    permuted = estimate_phi(v0[order], v24[order], v168[order])
    assert res.phi_168 == permuted.phi_168
