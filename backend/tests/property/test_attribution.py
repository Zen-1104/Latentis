"""Property and adversarial tests for part / socket / zone / tester attribution (T-305).

Asserts the non-negotiable invariants for ``backend.core.attribution.attribute``
(TEST-ATTR-007 and supporting property coverage):
  - Deterministic repeated execution (INV-8): bitwise-identical results.
  - Component-ID permutation invariance (INV-2 / RT-004) via leave-one-out cohorts.
  - Parameter (column) permutation consistency for the multivariate link.
  - Additive consistency with the T-304 joint decomposition across random systems.
  - No NaN or inf in any decision-bearing attribution output (ANOMALY_SPEC § 9).
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.core.attribution import (
    AttributionEvidence,
    AttributionVerdict,
    attribute,
)
from backend.core.constants import SUM_CHECK_TOLERANCE
from backend.core.dpat import leave_one_out
from backend.core.multivariate import mahalanobis


def _all_floats_finite_or_none(evidence: AttributionEvidence) -> bool:
    for field_info in dataclasses.fields(evidence):
        value = getattr(evidence, field_info.name)
        if isinstance(value, float) and not math.isfinite(value):
            return False
    return True


def _standard_setup(seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {
        "lot": rng.normal(loc=10.0, scale=1.0, size=60),
        "socket": rng.normal(loc=10.0, scale=0.5, size=12),
        "zone": rng.normal(loc=10.0, scale=1.0, size=25),
        "tester": rng.normal(loc=10.0, scale=1.0, size=30),
    }


@pytest.mark.property
def test_attribute_deterministic_repeated_execution() -> None:
    """TEST-ATTR-007 anchor: repeated execution is bitwise identical (INV-8)."""
    setup = _standard_setup(2001)
    joint = mahalanobis(
        np.random.default_rng(2002).normal(size=(30, 2)),
        part_value=[3.0, -3.0],
        parameter_names=["x", "y"],
    )

    first = attribute(
        part_value=18.0,
        lot_cohort=setup["lot"],
        socket_cohort=setup["socket"],
        zone_cohort=setup["zone"],
        tester_cohort=setup["tester"],
        mahalanobis_result=joint,
        parameter="x",
    )
    for _ in range(5):
        repeat = attribute(
            part_value=18.0,
            lot_cohort=setup["lot"],
            socket_cohort=setup["socket"],
            zone_cohort=setup["zone"],
            tester_cohort=setup["tester"],
            mahalanobis_result=joint,
            parameter="x",
        )
        assert repeat == first


@pytest.mark.property
def test_attribute_component_id_permutation_invariance() -> None:
    """Bijectively permuting component IDs leaves the verdict unchanged (INV-2)."""
    rng = np.random.default_rng(3003)
    n_parts = 40
    lot_values = rng.normal(loc=10.0, scale=1.0, size=n_parts)
    socket_values = rng.normal(loc=10.0, scale=0.5, size=12)

    base_ids = [f"PART_{i:04d}" for i in range(n_parts)]
    target_id = base_ids[0]
    target_value = float(lot_values[0]) + 8.0

    lot_records = [
        {"component_id": pid, "value": float(val), "status": "OK"}
        for pid, val in zip(base_ids, lot_values, strict=True)
    ]
    socket_records = [
        {"component_id": f"SOCK_{i:04d}", "value": float(val), "status": "OK"}
        for i, val in enumerate(socket_values)
    ]

    base_lot = leave_one_out(excluded_component_id=target_id, records=lot_records)
    base_res = attribute(
        part_value=target_value,
        lot_cohort=base_lot,
        socket_cohort=leave_one_out(excluded_component_id="SOCK_XXXX", records=socket_records),
    )

    perm_ids = rng.permutation(base_ids).tolist()
    perm_target = perm_ids[0]
    perm_records = [
        {"component_id": perm_ids[i], "value": float(lot_values[i]), "status": "OK"}
        for i in range(n_parts)
    ]
    perm_lot = leave_one_out(excluded_component_id=perm_target, records=perm_records)
    perm_res = attribute(
        part_value=target_value,
        lot_cohort=perm_lot,
        socket_cohort=leave_one_out(excluded_component_id="SOCK_XXXX", records=socket_records),
    )

    assert perm_res.verdict == base_res.verdict
    assert base_res.evidence.z_part is not None and perm_res.evidence.z_part is not None
    assert abs(perm_res.evidence.z_part - base_res.evidence.z_part) < 1e-12
    assert _all_floats_finite_or_none(base_res.evidence)
    assert _all_floats_finite_or_none(perm_res.evidence)


@pytest.mark.property
def test_attribute_parameter_permutation_consistency() -> None:
    """Permuting multivariate columns+names preserves verdict and top parameter."""
    rng = np.random.default_rng(4004)
    cohort = rng.normal(loc=[10.0, 20.0, 30.0], scale=[1.0, 2.0, 3.0], size=(50, 3))
    candidate = np.array([12.0, 25.0, 28.0])
    names = ["param_0", "param_1", "param_2"]

    joint_orig = mahalanobis(cohort, part_value=candidate, parameter_names=names)
    perm_order = [2, 0, 1]
    joint_perm = mahalanobis(
        cohort[:, perm_order],
        part_value=candidate[perm_order],
        parameter_names=[names[i] for i in perm_order],
    )
    assert joint_orig.refusal_code is None and joint_perm.refusal_code is None

    setup = _standard_setup(4005)
    res_orig = attribute(
        part_value=18.0,
        lot_cohort=setup["lot"],
        socket_cohort=setup["socket"],
        zone_cohort=setup["zone"],
        tester_cohort=setup["tester"],
        mahalanobis_result=joint_orig,
    )
    res_perm = attribute(
        part_value=18.0,
        lot_cohort=setup["lot"],
        socket_cohort=setup["socket"],
        zone_cohort=setup["zone"],
        tester_cohort=setup["tester"],
        mahalanobis_result=joint_perm,
    )

    assert res_perm.verdict == res_orig.verdict
    assert res_perm.evidence.top_parameter == res_orig.evidence.top_parameter
    for res, joint in ((res_orig, joint_orig), (res_perm, joint_perm)):
        assert joint.contributions is not None and joint.d2 is not None
        assert res.evidence.d2 == joint.d2
        assert abs(sum(c.contribution for c in joint.contributions) - joint.d2) <= (
            SUM_CHECK_TOLERANCE
        )
    assert _all_floats_finite_or_none(res_orig.evidence)
    assert _all_floats_finite_or_none(res_perm.evidence)


@settings(max_examples=50, deadline=1000)
@given(
    st.integers(min_value=2, max_value=3),
    st.integers(min_value=25, max_value=40),
    st.integers(min_value=1, max_value=10000),
)
def test_attribute_additive_consistency_hypothesis(p: int, n: int, seed: int) -> None:
    """Random joint systems: evidence D² equals the verified additive sum."""
    rng = np.random.default_rng(seed)
    mean = rng.uniform(-10.0, 10.0, size=p)
    mat = rng.normal(size=(p, p))
    cov = mat @ mat.T + np.eye(p) * 1.5
    cohort = rng.multivariate_normal(mean, cov, size=n)
    candidate = rng.uniform(-15.0, 15.0, size=p)
    names = [f"hyp_{q}" for q in range(p)]

    joint = mahalanobis(cohort, part_value=candidate, parameter_names=names)
    if joint.refusal_code is not None or joint.d2 is None or joint.contributions is None:
        return

    setup_rng = np.random.default_rng(seed + 1)
    res = attribute(
        part_value=float(candidate[0]) + 8.0,
        lot_cohort=setup_rng.normal(loc=10.0, scale=1.0, size=40),
        socket_cohort=setup_rng.normal(loc=10.0, scale=0.5, size=12),
        zone_cohort=setup_rng.normal(loc=10.0, scale=1.0, size=25),
        tester_cohort=setup_rng.normal(loc=10.0, scale=1.0, size=30),
        mahalanobis_result=joint,
        parameter=names[0],
    )

    assert res.refusal_code is None
    assert res.evidence.d2 == joint.d2
    assert res.verdict in (
        AttributionVerdict.PART,
        AttributionVerdict.SOCKET,
        AttributionVerdict.ZONE,
        AttributionVerdict.TESTER,
        AttributionVerdict.INDETERMINATE,
    )
    assert _all_floats_finite_or_none(res.evidence)


@settings(max_examples=50, deadline=1000)
@given(
    st.integers(min_value=1, max_value=10000),
)
def test_attribute_never_emits_nonfinite_hypothesis(seed: int) -> None:
    """Random univariate setups: verdict always in-enum, evidence always finite-or-None."""
    rng = np.random.default_rng(seed)
    shift = float(rng.uniform(-8.0, 8.0))
    lot = rng.normal(loc=0.0, scale=1.0, size=40)
    socket = rng.normal(loc=shift, scale=0.5, size=12)
    zone = rng.normal(loc=-shift, scale=1.0, size=25)
    tester = rng.normal(loc=shift / 2.0, scale=1.0, size=30)
    part = float(rng.normal(loc=shift, scale=1.0))

    res = attribute(
        part_value=part,
        lot_cohort=lot,
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
    )

    assert res.verdict in (
        AttributionVerdict.PART,
        AttributionVerdict.SOCKET,
        AttributionVerdict.ZONE,
        AttributionVerdict.TESTER,
        AttributionVerdict.INDETERMINATE,
    )
    assert _all_floats_finite_or_none(res.evidence)
