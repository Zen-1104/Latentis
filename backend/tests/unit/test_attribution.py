"""Unit tests for part / socket / zone / tester attribution (T-305, FR-208).

Implements TEST-ATTR-001..006 against ANOMALY_SPEC § 7 and the D-035 decision
table, plus degenerate, malformed, and joint-consistency edge cases. The
multivariate link consumes the T-304 public contract (RobustMahalanobisResult)
and never recomputes D².
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from backend.core.attribution import (
    AttributionResult,
    AttributionVerdict,
    attribute,
)
from backend.core.constants import (
    ATTRIBUTION_SETUP_OFFSET_SIGMA_THRESHOLD,
    SUM_CHECK_TOLERANCE,
)
from backend.core.multivariate import contributions, mahalanobis


def _assert_evidence_finite(result: AttributionResult) -> None:
    """Every float in the evidence must be finite or None (never NaN/inf)."""
    evidence = result.evidence
    for field_info in dataclasses.fields(evidence):
        value = getattr(evidence, field_info.name)
        if isinstance(value, float):
            assert math.isfinite(value), f"evidence.{field_info.name} is non-finite"
        elif isinstance(value, tuple):
            for item in value:
                assert isinstance(item, str), f"evidence.{field_info.name} holds {item!r}"


def _lot_cohort(seed: int = 11, n: int = 60) -> np.ndarray:
    return np.random.default_rng(seed).normal(loc=10.0, scale=1.0, size=n)


@pytest.mark.fast
def test_part_attribution() -> None:
    """TEST-ATTR-001: socket and zone offsets below threshold -> PART."""
    lot = _lot_cohort()
    socket = np.random.default_rng(12).normal(loc=10.1, scale=0.5, size=12)
    zone = np.random.default_rng(13).normal(loc=9.9, scale=1.0, size=25)
    tester = np.random.default_rng(14).normal(loc=10.0, scale=1.0, size=30)

    res = attribute(
        part_value=18.0,
        lot_cohort=lot,
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
    )

    assert res.verdict == AttributionVerdict.PART
    assert res.refusal_code is None
    assert res.warning is None
    assert res.evidence.setup_claims == ()
    assert res.evidence.z_part is not None and res.evidence.z_part > 6.0
    assert res.evidence.socket_median_offset_sigma is not None
    assert abs(res.evidence.socket_median_offset_sigma) < 2.0
    assert res.evidence.zone_median_offset_sigma is not None
    assert abs(res.evidence.zone_median_offset_sigma) < 2.0
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_socket_attribution() -> None:
    """TEST-ATTR-002: >=3 socket members flagged + socket offset above threshold -> SOCKET."""
    lot = _lot_cohort()
    socket = np.random.default_rng(22).normal(loc=15.0, scale=0.5, size=12)
    zone = np.random.default_rng(23).normal(loc=10.0, scale=1.0, size=25)
    tester = np.random.default_rng(24).normal(loc=10.0, scale=1.0, size=30)

    res = attribute(
        part_value=15.1,
        lot_cohort=lot,
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
    )

    assert res.verdict == AttributionVerdict.SOCKET
    assert res.refusal_code is None
    assert res.evidence.setup_claims == ("SOCKET",)
    assert res.evidence.socket_coherent_count is not None
    assert res.evidence.socket_coherent_count >= 3
    assert res.evidence.socket_median_offset_sigma is not None
    assert res.evidence.socket_median_offset_sigma >= 2.0
    assert res.evidence.z_socket is not None and abs(res.evidence.z_socket) < 3.0
    assert res.evidence.z_part is not None and res.evidence.z_part > 3.0
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_zone_attribution() -> None:
    """TEST-ATTR-003: thermal-zone median offset dominant -> ZONE."""
    lot = _lot_cohort()
    socket = np.random.default_rng(32).normal(loc=10.0, scale=0.5, size=12)
    zone = np.random.default_rng(33).normal(loc=14.0, scale=1.0, size=25)
    tester = np.random.default_rng(34).normal(loc=10.0, scale=1.0, size=30)

    res = attribute(
        part_value=14.1,
        lot_cohort=lot,
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
    )

    assert res.verdict == AttributionVerdict.ZONE
    assert res.refusal_code is None
    assert res.evidence.setup_claims == ("ZONE",)
    assert res.evidence.zone_median_offset_sigma is not None
    assert res.evidence.socket_median_offset_sigma is not None
    assert res.evidence.tester_median_offset_sigma is not None
    assert abs(res.evidence.zone_median_offset_sigma) > abs(res.evidence.socket_median_offset_sigma)
    assert abs(res.evidence.zone_median_offset_sigma) > abs(res.evidence.tester_median_offset_sigma)
    assert res.evidence.z_zone is not None and abs(res.evidence.z_zone) < 3.0
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_tester_attribution() -> None:
    """TEST-ATTR-004: tester-level shift present across lots -> TESTER."""
    lot = _lot_cohort()
    socket = np.random.default_rng(42).normal(loc=10.0, scale=0.5, size=12)
    zone = np.random.default_rng(43).normal(loc=10.0, scale=1.0, size=25)
    tester_raw = np.random.default_rng(44).normal(loc=14.0, scale=1.0, size=30)
    order = np.argsort(tester_raw)
    tester = tester_raw[order]
    timestamps = np.arange(tester.size, dtype=np.float64)

    res = attribute(
        part_value=14.05,
        lot_cohort=lot,
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
        tester_timestamps=timestamps,
    )

    assert res.verdict == AttributionVerdict.TESTER
    assert res.refusal_code is None
    assert res.evidence.setup_claims == ("TESTER",)
    assert res.evidence.tester_median_offset_sigma is not None
    assert res.evidence.tester_median_offset_sigma >= 2.0
    assert res.evidence.z_tester is not None and abs(res.evidence.z_tester) < 3.0
    assert res.evidence.tester_spearman_rho is not None
    assert res.evidence.tester_spearman_rho > 0.99
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_indeterminate_when_evidence_conflicts() -> None:
    """TEST-ATTR-005: socket and zone both claim -> INDETERMINATE, never arbitrary."""
    lot = _lot_cohort()
    socket = np.random.default_rng(52).normal(loc=15.0, scale=0.5, size=12)
    zone = np.random.default_rng(53).normal(loc=15.0, scale=1.0, size=25)
    tester = np.random.default_rng(54).normal(loc=10.0, scale=1.0, size=30)

    res = attribute(
        part_value=15.1,
        lot_cohort=lot,
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
    )

    assert res.verdict == AttributionVerdict.INDETERMINATE
    assert res.refusal_code is None
    assert set(res.evidence.setup_claims) == {"SOCKET", "ZONE"}
    assert res.warning is not None and "conflicting" in res.warning
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_attribute_known_answer_offsets() -> None:
    """TEST-ATTR-006 (known-answer): hand-computed medians, sigma, z, and offsets.

    Hand derivation (Type-7 quartiles, n=20: ten 10.0s then ten 11.0s):
      median = (10 + 11) / 2 = 10.5; Q1 = 10.0; Q3 = 11.0; IQR = 1.0
      robust_sigma = IQR / 1.35 = 1 / 1.35
      z_part = (16.0 - 10.5) / robust_sigma = 5.5 * 1.35 = 7.425
      socket median 10.4 -> offset = (10.4 - 10.5) / robust_sigma = -0.135
      zone/tester medians 10.5 -> offsets 0.0
    All offsets are below the 2.0 setup gate, so the verdict is PART.
    """
    lot = np.array([10.0] * 10 + [11.0] * 10)
    socket = np.array([10.2, 10.3, 10.4, 10.5, 10.6])
    zone = np.array([10.1, 10.3, 10.5, 10.5, 10.7, 10.9])
    tester = np.array([9.9, 10.2, 10.5, 10.8, 11.1])

    res = attribute(
        part_value=16.0,
        lot_cohort=lot,
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
    )

    assert res.verdict == AttributionVerdict.PART
    assert res.refusal_code is None
    assert res.evidence.lot_n == 20
    assert res.evidence.lot_median == 10.5
    assert res.evidence.lot_robust_sigma is not None
    assert abs(res.evidence.lot_robust_sigma - 1.0 / 1.35) < 1e-12
    assert res.evidence.z_part is not None
    assert abs(res.evidence.z_part - 7.425) < 1e-9
    assert res.evidence.socket_median_offset_sigma is not None
    assert abs(res.evidence.socket_median_offset_sigma - (-0.135)) < 1e-9
    assert res.evidence.zone_median_offset_sigma is not None
    assert abs(res.evidence.zone_median_offset_sigma - 0.0) < 1e-9
    assert res.evidence.tester_median_offset_sigma is not None
    assert abs(res.evidence.tester_median_offset_sigma - 0.0) < 1e-9
    assert res.evidence.socket_n == 5
    assert res.evidence.zone_n == 6
    assert res.evidence.tester_n == 5
    assert res.evidence.setup_claims == ()
    assert ATTRIBUTION_SETUP_OFFSET_SIGMA_THRESHOLD == 2.0
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_bad_part_in_bad_socket_is_part() -> None:
    """RT-006 row 5 analogue: shifted socket but part is an outlier within it -> PART."""
    lot = _lot_cohort()
    socket = np.random.default_rng(62).normal(loc=15.0, scale=0.5, size=12)
    zone = np.random.default_rng(63).normal(loc=10.0, scale=1.0, size=25)
    tester = np.random.default_rng(64).normal(loc=10.0, scale=1.0, size=30)

    res = attribute(
        part_value=20.0,
        lot_cohort=lot,
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
    )

    assert res.verdict == AttributionVerdict.PART
    assert res.evidence.setup_claims == ()
    assert res.evidence.socket_median_offset_sigma is not None
    assert res.evidence.socket_median_offset_sigma >= 2.0
    assert res.evidence.z_socket is not None and abs(res.evidence.z_socket) >= 3.0
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_indeterminate_when_metadata_absent() -> None:
    """No position metadata at all -> INDETERMINATE with part-only warning."""
    res = attribute(part_value=18.0, lot_cohort=_lot_cohort())

    assert res.verdict == AttributionVerdict.INDETERMINATE
    assert res.refusal_code is None
    assert res.warning is not None and "position metadata absent" in res.warning
    assert res.evidence.setup_claims == ()
    assert res.evidence.socket_n is None
    assert res.evidence.zone_n is None
    assert res.evidence.tester_n is None
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_joint_only_correlated_case_stays_part_with_consistent_d2() -> None:
    """Joint-only anomaly (marginals pass, D² huge) with clean setup -> PART.

    The attribution copies the T-304 D² and top contributor by reference and
    re-verifies the additive identity instead of recomputing it.
    """
    rng = np.random.default_rng(202)
    corr = 0.95
    cov = np.array([[1.0, corr], [corr, 1.0]])
    cohort = rng.multivariate_normal([0.0, 0.0], cov, size=50)
    part = np.array([2.0, -2.0])
    names = ["param_x", "param_y"]

    joint = mahalanobis(cohort, part_value=part, parameter_names=names)
    assert joint.refusal_code is None
    assert joint.d2 is not None and joint.d2 > 50.0

    socket = np.random.default_rng(72).normal(loc=0.0, scale=0.5, size=12)
    zone = np.random.default_rng(73).normal(loc=0.0, scale=1.0, size=25)
    tester = np.random.default_rng(74).normal(loc=0.0, scale=1.0, size=30)

    res = attribute(
        part_value=float(part[0]),
        lot_cohort=cohort[:, 0],
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
        mahalanobis_result=joint,
        parameter="param_x",
    )

    assert res.verdict == AttributionVerdict.PART
    assert res.refusal_code is None
    assert res.evidence.d2 == joint.d2
    assert res.evidence.p_value == joint.p_value
    assert joint.contributions is not None
    contrib_sum = sum(c.contribution for c in joint.contributions)
    assert abs(contrib_sum - joint.d2) <= SUM_CHECK_TOLERANCE
    assert res.evidence.top_parameter in ("param_x", "param_y")
    assert res.evidence.top_contribution is not None and res.evidence.top_contribution > 0.0
    assert res.evidence.parameter_share is not None
    expected_share = joint.contributions[0].share
    assert abs(res.evidence.parameter_share - expected_share) <= SUM_CHECK_TOLERANCE
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_positive_and_negative_contributions_preserved() -> None:
    """Signed T-304 contributions (one negative) travel into the evidence unchanged."""
    loc = [0.0, 0.0]
    prec = [[2.0, -1.0], [-1.0, 1.0]]
    # delta = [2.0, 0.5]; w = [3.5, -1.5]; c = [7.0, -0.75]; D² = 6.25
    contribs = contributions([2.0, 0.5], loc, prec, parameter_names=["p_a", "p_b"])
    assert abs(contribs[0].contribution - 7.0) < 1e-12
    assert abs(contribs[1].contribution - (-0.75)) < 1e-12

    joint = mahalanobis(
        np.random.default_rng(82).normal(size=(30, 2)),
        part_value=[0.0, 0.0],
    )
    assert joint.refusal_code is None
    joint_fixed = dataclasses.replace(joint, d2=6.25, p_value=0.05, contributions=contribs)

    res = attribute(
        part_value=18.0,
        lot_cohort=_lot_cohort(),
        socket_cohort=np.random.default_rng(83).normal(loc=10.0, scale=0.5, size=12),
        zone_cohort=np.random.default_rng(84).normal(loc=10.0, scale=1.0, size=25),
        tester_cohort=np.random.default_rng(85).normal(loc=10.0, scale=1.0, size=30),
        mahalanobis_result=joint_fixed,
        parameter="p_b",
    )

    assert res.verdict == AttributionVerdict.PART
    assert res.evidence.d2 == 6.25
    assert res.evidence.top_parameter == "p_a"
    assert res.evidence.top_contribution is not None
    assert abs(res.evidence.top_contribution - 7.0) < 1e-12
    assert res.evidence.parameter_share is not None
    assert abs(res.evidence.parameter_share - (-0.75 / 6.25)) < 1e-12
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_parameter_ordering_is_positional() -> None:
    """Swapping names without moving columns moves the attribution lookup with them."""
    rng = np.random.default_rng(92)
    cohort = rng.normal(loc=[10.0, 20.0], scale=[1.0, 2.0], size=(40, 2))
    candidate = np.array([10.2, 28.0])

    joint_ab = mahalanobis(cohort, part_value=candidate, parameter_names=["a_col", "b_col"])
    joint_ba = mahalanobis(cohort, part_value=candidate, parameter_names=["b_col", "a_col"])
    assert joint_ab.refusal_code is None and joint_ba.refusal_code is None

    lot = _lot_cohort(seed=93)
    socket = rng.normal(loc=10.0, scale=0.5, size=12)
    zone = rng.normal(loc=10.0, scale=1.0, size=25)
    tester = rng.normal(loc=10.0, scale=1.0, size=30)

    res_ab = attribute(
        part_value=18.0,
        lot_cohort=lot,
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
        mahalanobis_result=joint_ab,
        parameter="b_col",
    )
    res_ba = attribute(
        part_value=18.0,
        lot_cohort=lot,
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
        mahalanobis_result=joint_ba,
        parameter="b_col",
    )

    assert res_ab.verdict == res_ba.verdict == AttributionVerdict.PART
    assert joint_ab.contributions is not None and joint_ba.contributions is not None
    # "b_col" sits at index 1 in the first naming and index 0 in the second.
    assert res_ab.evidence.parameter_share == joint_ab.contributions[1].share
    assert res_ba.evidence.parameter_share == joint_ba.contributions[0].share
    assert res_ab.evidence.top_parameter == joint_ab.contributions[1].parameter
    _assert_evidence_finite(res_ab)
    _assert_evidence_finite(res_ba)


@pytest.mark.fast
def test_tampered_joint_contributions_refused() -> None:
    """Perturbed contributions disagreeing with D² refuse with INVALID_INPUT."""
    rng = np.random.default_rng(102)
    cohort = rng.normal(size=(30, 2))
    joint = mahalanobis(cohort, part_value=[3.0, -3.0], parameter_names=["x", "y"])
    assert joint.refusal_code is None
    assert joint.contributions is not None and joint.d2 is not None

    tampered_first = dataclasses.replace(
        joint.contributions[0],
        contribution=joint.contributions[0].contribution + 0.5,
    )
    tampered = dataclasses.replace(joint, contributions=(tampered_first, *joint.contributions[1:]))

    res = attribute(
        part_value=18.0,
        lot_cohort=_lot_cohort(),
        socket_cohort=rng.normal(loc=10.0, scale=0.5, size=12),
        zone_cohort=rng.normal(loc=10.0, scale=1.0, size=25),
        tester_cohort=rng.normal(loc=10.0, scale=1.0, size=30),
        mahalanobis_result=tampered,
    )

    assert res.verdict == AttributionVerdict.INDETERMINATE
    assert res.refusal_code == "INVALID_INPUT"
    assert res.warning is not None and "disagree" in res.warning
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_joint_refusal_degrades_to_univariate() -> None:
    """A skipped joint detector (n < 5p) is reported, not fatal, to attribution."""
    rng = np.random.default_rng(112)
    thin = rng.normal(size=(8, 3))
    joint = mahalanobis(thin, part_value=[5.0, 5.0, 5.0])
    assert joint.refusal_code == "INSUFFICIENT_SAMPLE_RATIO"

    res = attribute(
        part_value=18.0,
        lot_cohort=_lot_cohort(),
        socket_cohort=rng.normal(loc=10.0, scale=0.5, size=12),
        zone_cohort=rng.normal(loc=10.0, scale=1.0, size=25),
        tester_cohort=rng.normal(loc=10.0, scale=1.0, size=30),
        mahalanobis_result=joint,
    )

    assert res.verdict == AttributionVerdict.PART
    assert res.refusal_code is None
    assert res.evidence.d2 is None
    assert res.warning is not None and "INSUFFICIENT_SAMPLE_RATIO" in res.warning
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_degenerate_inputs_refuse_without_nan_or_inf() -> None:
    """Insufficient, zero-variation, malformed, and non-finite inputs refuse cleanly."""
    lot = _lot_cohort()

    res_nan = attribute(part_value=float("nan"), lot_cohort=lot)
    assert res_nan.refusal_code == "INVALID_INPUT"
    assert res_nan.verdict == AttributionVerdict.INDETERMINATE
    _assert_evidence_finite(res_nan)

    res_small = attribute(part_value=18.0, lot_cohort=np.array([10.0, 11.0]))
    assert res_small.refusal_code == "INSUFFICIENT_COHORT"
    assert res_small.verdict == AttributionVerdict.INDETERMINATE
    _assert_evidence_finite(res_small)

    res_flat = attribute(part_value=10.0, lot_cohort=np.full(25, 10.0))
    assert res_flat.refusal_code == "NO_VARIATION"
    assert res_flat.verdict == AttributionVerdict.INDETERMINATE
    _assert_evidence_finite(res_flat)

    res_2d = attribute(part_value=18.0, lot_cohort=np.zeros((6, 2)))
    assert res_2d.refusal_code == "INVALID_INPUT"
    assert res_2d.verdict == AttributionVerdict.INDETERMINATE
    _assert_evidence_finite(res_2d)

    res_2d_group = attribute(
        part_value=18.0,
        lot_cohort=lot,
        socket_cohort=np.zeros((6, 2)),
    )
    assert res_2d_group.refusal_code == "INVALID_INPUT"
    _assert_evidence_finite(res_2d_group)

    # A too-small group cohort is unevaluated metadata, not a refusal.
    res_thin_group = attribute(
        part_value=18.0,
        lot_cohort=lot,
        socket_cohort=np.array([10.1, 10.2]),
        zone_cohort=np.random.default_rng(113).normal(loc=10.0, scale=1.0, size=25),
        tester_cohort=np.random.default_rng(114).normal(loc=10.0, scale=1.0, size=30),
    )
    assert res_thin_group.verdict == AttributionVerdict.PART
    assert res_thin_group.refusal_code is None
    assert res_thin_group.evidence.socket_n is None
    assert res_thin_group.warning is not None and "socket" in res_thin_group.warning
    _assert_evidence_finite(res_thin_group)


@pytest.mark.fast
def test_zero_variation_socket_group() -> None:
    """A constant socket cohort still yields exact typicality by equality."""
    lot = _lot_cohort()
    zone = np.random.default_rng(123).normal(loc=10.0, scale=1.0, size=25)
    tester = np.random.default_rng(124).normal(loc=10.0, scale=1.0, size=30)

    res_equal = attribute(
        part_value=10.4,
        lot_cohort=lot,
        socket_cohort=np.full(8, 10.4),
        zone_cohort=zone,
        tester_cohort=tester,
    )
    assert res_equal.verdict == AttributionVerdict.PART
    assert res_equal.evidence.z_socket == 0.0
    _assert_evidence_finite(res_equal)

    res_far = attribute(
        part_value=16.0,
        lot_cohort=lot,
        socket_cohort=np.full(8, 10.4),
        zone_cohort=zone,
        tester_cohort=tester,
    )
    assert res_far.verdict == AttributionVerdict.PART
    assert res_far.evidence.z_socket is None
    _assert_evidence_finite(res_far)


@pytest.mark.fast
def test_mismatched_tester_timestamps_omit_drift_evidence() -> None:
    """Unpairable timestamps warn and omit rho instead of failing the verdict."""
    lot = _lot_cohort()
    res = attribute(
        part_value=18.0,
        lot_cohort=lot,
        socket_cohort=np.random.default_rng(132).normal(loc=10.0, scale=0.5, size=12),
        zone_cohort=np.random.default_rng(133).normal(loc=10.0, scale=1.0, size=25),
        tester_cohort=np.random.default_rng(134).normal(loc=10.0, scale=1.0, size=30),
        tester_timestamps=np.arange(7, dtype=np.float64),
    )

    assert res.verdict == AttributionVerdict.PART
    assert res.evidence.tester_spearman_rho is None
    assert res.warning is not None and "timestamps" in res.warning
    _assert_evidence_finite(res)


@pytest.mark.fast
def test_extreme_finite_physical_values() -> None:
    """Scales far beyond picoamperes stay finite and decide identically."""
    for scale in (1e-30, 1e-12, 1e12, 1e30):
        rng = np.random.default_rng(142)
        lot = rng.normal(loc=10.0 * scale, scale=scale, size=40)
        sigma_guess = float(np.std(lot))
        part = float(np.median(lot) + 8.0 * sigma_guess)
        socket = rng.normal(loc=10.0 * scale, scale=0.5 * scale, size=12)
        zone = rng.normal(loc=10.0 * scale, scale=scale, size=25)
        tester = rng.normal(loc=10.0 * scale, scale=scale, size=30)

        res = attribute(
            part_value=part,
            lot_cohort=lot,
            socket_cohort=socket,
            zone_cohort=zone,
            tester_cohort=tester,
        )

        assert res.verdict == AttributionVerdict.PART, f"scale {scale}"
        assert res.refusal_code is None, f"scale {scale}"
        assert res.evidence.z_part is not None and math.isfinite(res.evidence.z_part)
        _assert_evidence_finite(res)
