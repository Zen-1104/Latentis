"""Unit and property tests for difficulty strata S0-S5 and decoy generation (T-203).

Validates:
  1. Stratum definitions, predicates, and decoy/escape partition (D-015, DATASET_SPEC § 7).
  2. Stratum S0 clear-fail generation: exceeds absolute limits; FAILED/LATENT_DEFECT label.
  3. Stratum S1 escape-anomaly: inside limits at ALL read-points, 24h outlier, LATENT_DEFECT.
  4. Stratum S2 escape-drift: inside limits at ALL read-points, 24h normal, unsafe drift at 168h.
  5. Stratum S3 decoy-healthy generation: healthy, inside limits, must NOT be flagged (FP pressure).
  6. Stratum S4 decoy-sensor: healthy part, sensor artefact magnitude > 0, must NOT be rejected.
  7. Stratum S5 decoy-lot-shift: healthy, shifted lot mean, DPAT absorbs shift, must NOT fail lot.
  8. Label and stratum derivation from rendered values, not intent (DR-05, D-014).
  9. Stratified lot generation and mixture properties.
  10. Hypothesis property testing across randomized parameters.
  11. Seed reproducibility (INV-08).
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from datagen import (
    DECOY_STRATA,
    ESCAPE_STRATA,
    FLAGGED_TARGET_STRATA,
    DatagenConfig,
    FailureLabel,
    StrataGenerator,
    Stratum,
    check_values_inside_limits,
    classify_rendered_stratum,
    find_limit_violations,
    get_default_config,
    is_decoy,
    is_escape,
    must_flag,
)
from datagen.config.schema import (
    ComponentType,
    ParameterName,
    default_parameter_limits,
)


@pytest.fixture
def default_config() -> DatagenConfig:
    """Fixture providing validated default generator configuration."""
    return get_default_config()


@pytest.fixture
def strata_gen(default_config: DatagenConfig) -> StrataGenerator:
    """Fixture providing seeded StrataGenerator instance."""
    return StrataGenerator(default_config)


# =============================================================================
# 1. Stratum Group and Predicate Tests
# =============================================================================


@pytest.mark.fast
def test_strata_definitions_and_predicates() -> None:
    """Verify strata partitions, predicates, and decoy/escape invariants."""
    # 1. Exact member partitions
    assert DECOY_STRATA == {
        Stratum.S3_DECOY_HEALTHY,
        Stratum.S4_DECOY_SENSOR,
        Stratum.S5_LOT_SHIFT,
    }
    assert ESCAPE_STRATA == {
        Stratum.S1_ESCAPE_ANOMALY,
        Stratum.S2_ESCAPE_DRIFT,
    }
    assert FLAGGED_TARGET_STRATA == {
        Stratum.S0_CLEAR_FAIL,
        Stratum.S1_ESCAPE_ANOMALY,
        Stratum.S2_ESCAPE_DRIFT,
    }

    # 2. Decoys and Escape Set are strictly disjoint
    assert len(DECOY_STRATA.intersection(ESCAPE_STRATA)) == 0

    # 3. Predicate checks
    for s in DECOY_STRATA:
        assert is_decoy(s) is True
        assert is_escape(s) is False
        assert must_flag(s) is False, f"Decoy stratum {s} must not be marked must_flag"

    for s in ESCAPE_STRATA:
        assert is_escape(s) is True
        assert is_decoy(s) is False
        assert must_flag(s) is True

    assert must_flag(Stratum.S0_CLEAR_FAIL) is True
    assert is_escape(Stratum.S0_CLEAR_FAIL) is False
    assert is_decoy(Stratum.S0_CLEAR_FAIL) is False


# =============================================================================
# 2. Stratum S0 Clear-Fail Tests
# =============================================================================


@pytest.mark.fast
def test_s0_clear_fail_generation_and_invariants(strata_gen: StrataGenerator) -> None:
    """Verify S0 parts exceed absolute limits and carry failure labels."""
    limits = default_parameter_limits()

    # Sudden failure mechanism
    part_step = strata_gen.generate_s0_clear_fail(
        component_id="C-TEST-S0-01",
        lot_id="L-2026-001",
        mechanism="sudden_failure",
    )
    assert part_step.stratum == Stratum.S0_CLEAR_FAIL
    assert part_step.failure_label in (FailureLabel.FAILED, FailureLabel.LATENT_DEFECT)
    assert part_step.is_escape is False
    assert part_step.is_decoy is False
    assert check_values_inside_limits(part_step.values, limits) is False

    violations = find_limit_violations(part_step.values, limits)
    assert len(violations) > 0, "S0 part must have at least one recorded limit violation"

    # Accelerated drift uncontained mechanism
    part_drift = strata_gen.generate_s0_clear_fail(
        component_id="C-TEST-S0-02",
        lot_id="L-2026-001",
        mechanism="accelerated_drift",
    )
    assert part_drift.stratum == Stratum.S0_CLEAR_FAIL
    assert check_values_inside_limits(part_drift.values, limits) is False


# =============================================================================
# 3. Stratum S1 Escape-Anomaly Tests (Module A Target)
# =============================================================================


@pytest.mark.fast
def test_s1_escape_anomaly_generation_and_invariants(strata_gen: StrataGenerator) -> None:
    """TEST-GEN-004 / DR-04: S1 parts are strictly inside limits and lot-relative outliers."""
    limits = default_parameter_limits()

    # Standard elevated baseline S1
    part_standard = strata_gen.generate_s1_escape_anomaly(
        component_id="C-TEST-S1-01",
        lot_id="L-2026-001",
        is_joint_only=False,
    )
    assert part_standard.stratum == Stratum.S1_ESCAPE_ANOMALY
    assert part_standard.failure_label == FailureLabel.LATENT_DEFECT
    assert part_standard.is_escape is True
    assert part_standard.is_decoy is False

    # STRICT INVARIANT (DR-04): Zero limit breaches across all read-points
    assert check_values_inside_limits(part_standard.values, limits) is True
    violations = find_limit_violations(part_standard.values, limits)
    assert len(violations) == 0

    # 24 h reading is elevated: IDDQ standby is > 3 sigma above nominal baseline
    iddq_24h = part_standard.value_24h[ParameterName.IDDQ_STANDBY.value]
    assert iddq_24h > 13.0, f"Expected elevated IDDQ at 24 h, got {iddq_24h:.2f} uA"
    assert iddq_24h < 50.0, f"Must remain strictly inside absolute max 50.0 uA, got {iddq_24h:.2f}"

    # Joint-only S1 anomaly
    part_joint = strata_gen.generate_s1_escape_anomaly(
        component_id="C-TEST-S1-02",
        lot_id="L-2026-001",
        is_joint_only=True,
    )
    assert part_joint.stratum == Stratum.S1_ESCAPE_ANOMALY
    assert part_joint.is_joint_only is True
    assert check_values_inside_limits(part_joint.values, limits) is True


# =============================================================================
# 4. Stratum S2 Escape-Drift Tests (Module B Target)
# =============================================================================


@pytest.mark.fast
def test_s2_escape_drift_generation_and_invariants(strata_gen: StrataGenerator) -> None:
    """TEST-GEN-004 / DR-04: S2 parts are lot-normal at 24h, unsafe at 168h, inside limits."""
    limits = default_parameter_limits()

    part = strata_gen.generate_s2_escape_drift(
        component_id="C-TEST-S2-01",
        lot_id="L-2026-001",
    )

    assert part.stratum == Stratum.S2_ESCAPE_DRIFT
    assert part.failure_label == FailureLabel.LATENT_DEFECT
    assert part.is_escape is True
    assert part.is_decoy is False

    # STRICT INVARIANT (DR-04): Inside absolute limits at ALL read points {0, 24, 96, 168}
    assert check_values_inside_limits(part.values, limits) is True

    # 1. 24 h reading is lot-normal (within typical nominal baseline range)
    iddq_0h = part.value_0h[ParameterName.IDDQ_STANDBY.value]
    iddq_24h = part.value_24h[ParameterName.IDDQ_STANDBY.value]
    iddq_168h = part.value_168h[ParameterName.IDDQ_STANDBY.value]

    # Baseline is normal healthy: between 8 and 14 uA
    assert 7.0 <= iddq_0h <= 16.0, f"Expected normal baseline for S2, got {iddq_0h:.2f} uA"

    # Degradation between 24h and 168h is substantial (sub-linear accelerated drift)
    drift_24_to_168 = iddq_168h - iddq_24h
    assert drift_24_to_168 > 0.5, f"Expected drift towards 168h, got {drift_24_to_168:.2f}"

    # Must not cross absolute max 50.0 uA
    assert iddq_168h < 50.0, f"Must remain inside absolute limit 50 uA, got {iddq_168h:.2f}"


# =============================================================================
# 5. Stratum S3 Decoy-Healthy Tests (False-Positive Pressure)
# =============================================================================


@pytest.mark.fast
def test_s3_decoy_healthy_generation_and_invariants(strata_gen: StrataGenerator) -> None:
    """D-015: S3 decoys are healthy and must NOT be flagged."""
    limits = default_parameter_limits()

    # Variant: noisy (3x measurement noise)
    p_noisy = strata_gen.generate_s3_decoy_healthy(
        component_id="C-TEST-S3-01",
        lot_id="L-2026-001",
        variant="noisy",
    )
    assert p_noisy.stratum == Stratum.S3_DECOY_HEALTHY
    assert p_noisy.failure_label == FailureLabel.HEALTHY
    assert p_noisy.is_escape is False
    assert p_noisy.is_decoy is True
    assert must_flag(p_noisy.stratum) is False
    assert check_values_inside_limits(p_noisy.values, limits) is True

    # Variant: gradual drift (normal wear-in)
    p_grad = strata_gen.generate_s3_decoy_healthy(
        component_id="C-TEST-S3-02",
        lot_id="L-2026-001",
        variant="gradual_drift",
    )
    assert p_grad.stratum == Stratum.S3_DECOY_HEALTHY
    assert p_grad.failure_label == FailureLabel.HEALTHY
    assert p_grad.is_decoy is True

    # Variant: upper tail
    p_tail = strata_gen.generate_s3_decoy_healthy(
        component_id="C-TEST-S3-03",
        lot_id="L-2026-001",
        variant="upper_tail",
    )
    assert p_tail.stratum == Stratum.S3_DECOY_HEALTHY
    assert p_tail.failure_label == FailureLabel.HEALTHY
    assert p_tail.is_decoy is True


# =============================================================================
# 6. Stratum S4 Decoy-Sensor Tests (Socket Attribution Target)
# =============================================================================


@pytest.mark.fast
def test_s4_decoy_sensor_generation_and_invariants(strata_gen: StrataGenerator) -> None:
    """D-015 / DATASET_SPEC § 5.3: S4 decoys have sensor artefact > 0 and healthy label."""
    limits = default_parameter_limits()

    part = strata_gen.generate_s4_decoy_sensor(
        component_id="C-TEST-S4-01",
        lot_id="L-2026-001",
        artefact_magnitude=4.2,
        socket_id="SOCK-BAD-09",
    )

    assert part.stratum == Stratum.S4_DECOY_SENSOR
    assert part.failure_label == FailureLabel.HEALTHY
    assert part.is_escape is False
    assert part.is_decoy is True
    assert must_flag(part.stratum) is False
    assert part.socket_id == "SOCK-BAD-09"

    # Crucial property: sensor_artefact_magnitude > 0 (non-zero ONLY for S4 per DATASET_SPEC § 5.3)
    assert part.sensor_artefact_magnitude == 4.2
    assert check_values_inside_limits(part.values, limits) is True


# =============================================================================
# 7. Stratum S5 Decoy-Lot-Shift Tests (DPAT Absorbs Shift)
# =============================================================================


@pytest.mark.fast
def test_s5_lot_shift_generation_and_invariants(strata_gen: StrataGenerator) -> None:
    """D-015 / D-CD-02: S5 shifted lot is healthy, internally consistent, inside limits."""
    limits = default_parameter_limits()

    part = strata_gen.generate_s5_lot_shift(
        component_id="C-TEST-S5-01",
        lot_id="L-SHIFT-01",
        shift_sigma_multiplier=3.0,
    )

    assert part.stratum == Stratum.S5_LOT_SHIFT
    assert part.failure_label == FailureLabel.HEALTHY
    assert part.is_escape is False
    assert part.is_decoy is True
    assert part.lot_shift_applied is True
    assert must_flag(part.stratum) is False
    assert check_values_inside_limits(part.values, limits) is True


# =============================================================================
# 8. Rendered Value Stratum Classification Tests (DR-05, D-014)
# =============================================================================


@pytest.mark.fast
def test_classify_rendered_stratum_derivation(strata_gen: StrataGenerator) -> None:
    """Verify stratum is derived strictly from rendered values, not generator intent."""
    limits = default_parameter_limits()

    # 1. Any reading breaching limits -> S0-clear-fail regardless of intent
    mock_values_breach = {
        ParameterName.IDDQ_STANDBY.value: {0: 10.0, 24: 12.0, 96: 25.0, 168: 55.0},  # > 50
    }
    derived_s0 = classify_rendered_stratum(
        values=mock_values_breach,
        failure_label=FailureLabel.LATENT_DEFECT,  # was intended as escape
        limits=limits,
    )
    assert derived_s0 == Stratum.S0_CLEAR_FAIL

    # 2. Inside limits + healthy label -> decoys
    mock_values_clean = {
        ParameterName.IDDQ_STANDBY.value: {0: 10.0, 24: 11.0, 96: 12.0, 168: 13.0},
    }
    # Decoy S3
    derived_s3 = classify_rendered_stratum(
        values=mock_values_clean,
        failure_label=FailureLabel.HEALTHY,
        limits=limits,
    )
    assert derived_s3 == Stratum.S3_DECOY_HEALTHY

    # Decoy S4 (sensor artefact present)
    derived_s4 = classify_rendered_stratum(
        values=mock_values_clean,
        failure_label=FailureLabel.HEALTHY,
        limits=limits,
        sensor_artefact_magnitude=3.5,
    )
    assert derived_s4 == Stratum.S4_DECOY_SENSOR

    # Decoy S5 (lot shift)
    derived_s5 = classify_rendered_stratum(
        values=mock_values_clean,
        failure_label=FailureLabel.HEALTHY,
        limits=limits,
        is_lot_shifted=True,
    )
    assert derived_s5 == Stratum.S5_LOT_SHIFT

    # 3. Inside limits + latent defect -> Escape Set S1 or S2
    derived_s1 = classify_rendered_stratum(
        values=mock_values_clean,
        failure_label=FailureLabel.LATENT_DEFECT,
        limits=limits,
        is_24h_outlier=True,
    )
    assert derived_s1 == Stratum.S1_ESCAPE_ANOMALY

    derived_s2 = classify_rendered_stratum(
        values=mock_values_clean,
        failure_label=FailureLabel.LATENT_DEFECT,
        limits=limits,
        is_24h_outlier=False,
    )
    assert derived_s2 == Stratum.S2_ESCAPE_DRIFT


# =============================================================================
# 9. Stratified Lot Generation and Mixture Tests
# =============================================================================


@pytest.mark.fast
def test_stratified_lot_generation_and_composition(strata_gen: StrataGenerator) -> None:
    """Verify full lot generation with class mixtures and counts."""
    limits = default_parameter_limits()

    # 1. Standard lot with 60 parts
    lot = strata_gen.generate_stratified_lot(
        lot_id="L-2026-042",
        n_parts=60,
        component_type=ComponentType.CMOS_LOGIC,
    )
    assert lot.count == 60
    assert lot.escape_count >= 1, "Lot must contain at least one escape part"
    assert lot.decoy_count >= 1, "Lot must contain decoy parts"

    # Every Escape Set member must strictly satisfy inside limits (DR-04)
    for p in lot.parts:
        if p.is_escape:
            assert p.stratum in ESCAPE_STRATA
            assert check_values_inside_limits(p.values, limits) is True
        if p.is_decoy:
            assert p.stratum in DECOY_STRATA
            assert p.failure_label == FailureLabel.HEALTHY

    # 2. Shifted lot (S5)
    shifted_lot = strata_gen.generate_stratified_lot(
        lot_id="L-2026-SHIFT",
        n_parts=30,
        component_type=ComponentType.CMOS_LOGIC,
        is_shifted_lot=True,
    )
    assert shifted_lot.is_shifted_lot is True
    assert shifted_lot.count == 30
    assert all(p.stratum == Stratum.S5_LOT_SHIFT for p in shifted_lot.parts)
    assert all(p.is_decoy is True for p in shifted_lot.parts)
    assert all(p.failure_label == FailureLabel.HEALTHY for p in shifted_lot.parts)
    assert all(check_values_inside_limits(p.values, limits) for p in shifted_lot.parts)


# =============================================================================
# 10. General Dispatcher and Reproducibility Tests
# =============================================================================


@pytest.mark.fast
def test_generate_part_for_stratum_dispatcher(strata_gen: StrataGenerator) -> None:
    """Verify generate_part_for_stratum dispatches correctly for all strata S0-S5."""
    for s in Stratum:
        part = strata_gen.generate_part_for_stratum(
            stratum=s,
            component_id=f"C-DISP-{s.value}",
            lot_id="L-2026-DISP",
        )
        assert part.stratum == s
        if s in ESCAPE_STRATA:
            assert part.is_escape is True
            assert part.is_decoy is False
        elif s in DECOY_STRATA:
            assert part.is_escape is False
            assert part.is_decoy is True
            assert part.failure_label == FailureLabel.HEALTHY


@pytest.mark.fast
def test_strata_generator_reproducibility(default_config: DatagenConfig) -> None:
    """INV-08: Identical seed produces byte-identical strata parts."""
    gen1 = StrataGenerator(default_config)
    gen2 = StrataGenerator(default_config)

    part1_s1 = gen1.generate_s1_escape_anomaly("C-001", "L-001")
    part2_s1 = gen2.generate_s1_escape_anomaly("C-001", "L-001")

    assert part1_s1.values == part2_s1.values
    assert part1_s1.stratum == part2_s1.stratum
    assert part1_s1.failure_label == part2_s1.failure_label

    part1_s2 = gen1.generate_s2_escape_drift("C-002", "L-001")
    part2_s2 = gen2.generate_s2_escape_drift("C-002", "L-001")

    assert part1_s2.values == part2_s2.values


# =============================================================================
# 11. Property-Based Fuzzing with Hypothesis
# =============================================================================


@settings(max_examples=15, deadline=None)
@given(
    seed=st.integers(min_value=1, max_value=2**31 - 1),
    component_type=st.sampled_from(list(ComponentType)),
    stratum=st.sampled_from(list(Stratum)),
)
def test_hypothesis_strata_invariants(
    seed: int, component_type: ComponentType, stratum: Stratum
) -> None:
    """Property test verifying structural invariants across random seeds and device types."""
    cfg = get_default_config()
    rng = np.random.default_rng(seed)
    gen = StrataGenerator(cfg, rng=rng)
    limits = default_parameter_limits()

    part = gen.generate_part_for_stratum(
        stratum=stratum,
        component_id="C-HYPO-001",
        lot_id="L-HYPO-001",
        component_type=component_type,
    )

    assert part.stratum == stratum

    if stratum in ESCAPE_STRATA:
        # Strict DR-04 invariant: ALL Escape Set members inside ALL limits at ALL read-points
        assert part.is_escape is True
        assert part.is_decoy is False
        assert part.failure_label == FailureLabel.LATENT_DEFECT
        assert check_values_inside_limits(part.values, limits) is True

    elif stratum in DECOY_STRATA:
        # Strict D-015 invariant: ALL decoys are healthy and must NOT be flagged
        assert part.is_escape is False
        assert part.is_decoy is True
        assert part.failure_label == FailureLabel.HEALTHY
        assert must_flag(part.stratum) is False
        assert check_values_inside_limits(part.values, limits) is True

        if stratum == Stratum.S4_DECOY_SENSOR:
            assert part.sensor_artefact_magnitude > 0.0
        elif stratum == Stratum.S5_LOT_SHIFT:
            assert part.lot_shift_applied is True

    elif stratum == Stratum.S0_CLEAR_FAIL:
        # S0 must fail at least one absolute limit
        assert part.is_escape is False
        assert part.is_decoy is False
        assert check_values_inside_limits(part.values, limits) is False
