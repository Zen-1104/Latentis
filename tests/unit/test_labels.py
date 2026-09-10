"""Unit and behavioral tests for ground-truth label derivation (T-205, TEST-GEN-005).

Validates:
  1. TEST-GEN-005: Recompute every label from emitted values with an independent function;
     intent flags must not appear in the derivation.
  2. Ground-truth rule applied to 168 h column (DECISIONS.md D-014).
  3. D-014 Invariant: Parts intended to be defective whose rendered values stay inside
     safe limits derive as HEALTHY (intent does NOT override rendered reality).
  4. D-014 Invariant: Parts intended to be healthy whose rendered values breach limits
     derive as FAILED / S0-clear-fail.
  5. Escape Set (S1 union S2) inside-limits invariant (DR-04, TEST-GEN-004).
  6. Decoy strata (S3, S4, S5) derive as HEALTHY and must_flag=False (D-015).
  7. Catastrophic step jumps derive as FAILED / sudden_failure.
  8. Ingested MeasurementRecord compatibility: derivation from raw measurement rows.
  9. Hypothesis property fuzzing on arbitrary rendered trajectories.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from datagen.config.schema import (
    DatagenConfig,
    FailureLabel,
    ParameterLimitConfig,
    Stratum,
    default_parameter_limits,
)
from datagen.imperfections import convert_lot_to_records
from datagen.labels import (
    PartLabelResult,
    derive_part_labels,
    recompute_ground_truth_labels,
)
from datagen.physics import PhysicalModel
from datagen.strata import StrataGenerator, StratifiedLot


@pytest.fixture
def config() -> DatagenConfig:
    """Fixture providing default configuration."""
    return DatagenConfig()


@pytest.fixture
def limits() -> dict[str, ParameterLimitConfig]:
    """Fixture providing default screening limits."""
    return default_parameter_limits()


@pytest.fixture
def strata_gen(config: DatagenConfig) -> StrataGenerator:
    """Fixture providing StrataGenerator."""
    physics = PhysicalModel(config)
    return StrataGenerator(config, physics=physics, rng=physics.rng)


# =============================================================================
# 1. TEST-GEN-005: Labels Derived from Rendered Values, Not Intent
# =============================================================================


@pytest.mark.fast
def test_labels_derived_from_rendered_values(
    strata_gen: StrataGenerator,
    limits: dict[str, ParameterLimitConfig],
) -> None:
    """TEST-GEN-005: Recompute every label from emitted values with an independent function.

    Requirements: DR-05, D-014.
    Oracle:
      Recompute every label from the emitted values with an independent function;
      intent flags must not appear in the derivation.
    """
    # 1. Generate a full stratified lot of parts with diverse strata S0..S5
    lot: StratifiedLot = strata_gen.generate_stratified_lot("L-2026-VAL", n_parts=40)

    # 2. Extract ONLY emitted/rendered values and component IDs (Zero intent flags passed)
    raw_values_payload: dict[str, dict[str, dict[int, float]]] = {
        p.component_id: {param: dict(p.values[param]) for param in p.values} for p in lot.parts
    }

    # 3. Call the independent derivation oracle without ANY generator intent
    rederived: dict[str, PartLabelResult] = recompute_ground_truth_labels(
        raw_values_payload,
        limits=limits,
    )

    assert len(rederived) == len(lot.parts)

    for part in lot.parts:
        cid = part.component_id
        res = rederived[cid]

        # Invariant A: Stratum S0 must breach absolute limits
        if res.stratum == Stratum.S0_CLEAR_FAIL:
            assert not res.is_inside_limits
            assert len(res.limit_violations) > 0
            assert res.must_flag is True

        # Invariant B: Escape Set (S1, S2) must be strictly inside all limits and defective
        if res.stratum in (Stratum.S1_ESCAPE_ANOMALY, Stratum.S2_ESCAPE_DRIFT):
            assert res.is_inside_limits is True
            assert res.failure_label == FailureLabel.LATENT_DEFECT
            assert res.is_escape is True
            assert res.must_flag is True

        # Invariant C: Decoy strata (S3, S4, S5) must be healthy and must NOT be flagged
        if res.stratum in (Stratum.S3_DECOY_HEALTHY, Stratum.S4_DECOY_SENSOR, Stratum.S5_LOT_SHIFT):
            assert res.is_inside_limits is True
            assert res.failure_label == FailureLabel.HEALTHY
            assert res.is_escape is False
            assert res.must_flag is False


# =============================================================================
# 2. D-014 Invariant: Intent vs. Rendered Reality Divergence Tests
# =============================================================================


@pytest.mark.fast
def test_rendered_derived_when_noise_cleans_intended_defect(
    limits: dict[str, ParameterLimitConfig],
) -> None:
    """D-014: If noise or small amplitude leaves an intended defect clean, it derives as HEALTHY.

    "Some parts intended to be defective will be labelled clean because the noise realisation
     put them inside the limit. That is correct: they are clean in this corpus."
    """
    # Create rendered values representing a completely clean, stable part:
    # All values are at nominal centre, with tiny drift (0.2 uA on IDDQ, negligible on others)
    clean_rendered: dict[str, dict[int, float]] = {
        "iddq_standby": {0: 10.0, 24: 10.05, 96: 10.12, 168: 10.20},  # margin=40, drift=0.20 (0.5%)
        "leakage_input": {0: 2.0, 24: 2.02, 96: 2.05, 168: 2.10},
        "prop_delay": {0: 10.0, 24: 10.01, 96: 10.03, 168: 10.05},
        "vth_shift": {0: 0.0, 24: 0.2, 96: 0.4, 168: 0.6},
        "icc_active": {0: 25.0, 24: 25.05, 96: 25.10, 168: 25.15},
        "output_res": {0: 50.0, 24: 50.1, 96: 50.2, 168: 50.3},
    }

    # Derive strictly from rendered values
    res = derive_part_labels(clean_rendered, limits=limits, component_id="C-INTENT-CLEAN")

    # MUST derive as HEALTHY because the physical numbers are clean
    assert res.failure_label == FailureLabel.HEALTHY
    assert res.stratum == Stratum.S3_DECOY_HEALTHY
    assert res.is_escape is False
    assert res.must_flag is False


@pytest.mark.fast
def test_rendered_derived_when_noise_fails_intended_healthy(
    limits: dict[str, ParameterLimitConfig],
) -> None:
    """D-014: If noise pushes an intended healthy part over the limit, it derives as S0 / FAILED.

    "If noise pushes a part outside limits, it becomes S0 regardless of intent."
    """
    # Create rendered values where IDDQ is pushed to 55.0 uA at 168h (absolute limit is 50.0 uA)
    breached_rendered: dict[str, dict[int, float]] = {
        "iddq_standby": {0: 12.0, 24: 14.0, 96: 28.0, 168: 55.0},  # Breaches 50.0 limit
        "leakage_input": {0: 2.0, 24: 2.5, 96: 3.0, 168: 4.0},
        "prop_delay": {0: 10.0, 24: 10.5, 96: 11.0, 168: 11.5},
        "vth_shift": {0: 0.0, 24: 1.0, 96: 2.0, 168: 3.0},
        "icc_active": {0: 25.0, 24: 25.5, 96: 26.0, 168: 26.5},
        "output_res": {0: 50.0, 24: 51.0, 96: 52.0, 168: 53.0},
    }

    res = derive_part_labels(breached_rendered, limits=limits, component_id="C-INTENT-FAIL")

    assert res.is_inside_limits is False
    assert res.stratum == Stratum.S0_CLEAR_FAIL
    assert res.must_flag is True
    assert "iddq_standby" in res.limit_violations


# =============================================================================
# 3. Escape Set and Decoy Invariant Verification (DR-04, D-015)
# =============================================================================


@pytest.mark.fast
def test_escape_set_inside_limits_invariant(
    limits: dict[str, ParameterLimitConfig],
) -> None:
    """DR-04: S1 and S2 Escape Set parts are strictly inside all absolute limits."""
    # S1 Escape Anomaly: elevated baseline (24 uA, inside limit 50), lot-relative outlier at 24h
    s1_values: dict[str, dict[int, float]] = {
        "iddq_standby": {0: 24.0, 24: 25.5, 96: 27.0, 168: 28.5},
        "leakage_input": {0: 15.0, 24: 16.0, 96: 17.5, 168: 19.0},
        "prop_delay": {0: 10.0, 24: 10.2, 96: 10.4, 168: 10.6},
        "vth_shift": {0: 0.0, 24: 1.0, 96: 2.0, 168: 3.0},
        "icc_active": {0: 25.0, 24: 25.5, 96: 26.0, 168: 26.5},
        "output_res": {0: 50.0, 24: 50.5, 96: 51.0, 168: 51.5},
    }

    res_s1 = derive_part_labels(s1_values, limits=limits, is_24h_outlier=True)
    assert res_s1.stratum == Stratum.S1_ESCAPE_ANOMALY
    assert res_s1.failure_label == FailureLabel.LATENT_DEFECT
    assert res_s1.is_escape is True
    assert res_s1.is_inside_limits is True
    assert res_s1.must_flag is True

    # S2 Escape Drift: normal at 24h, large drift at 168h (10 -> 42 uA, inside 50 uA limit)
    s2_values: dict[str, dict[int, float]] = {
        "iddq_standby": {0: 10.0, 24: 12.0, 96: 28.0, 168: 42.0},  # margin=40, drift=32 (80%)
        "leakage_input": {0: 2.0, 24: 2.5, 96: 4.0, 168: 8.0},
        "prop_delay": {0: 10.0, 24: 10.2, 96: 10.6, 168: 11.2},
        "vth_shift": {0: 0.0, 24: 1.0, 96: 3.0, 168: 6.0},
        "icc_active": {0: 25.0, 24: 25.5, 96: 26.5, 168: 28.0},
        "output_res": {0: 50.0, 24: 50.5, 96: 51.5, 168: 53.0},
    }

    res_s2 = derive_part_labels(s2_values, limits=limits, is_24h_outlier=False)
    assert res_s2.stratum == Stratum.S2_ESCAPE_DRIFT
    assert res_s2.failure_label == FailureLabel.LATENT_DEFECT
    assert res_s2.is_escape is True
    assert res_s2.is_inside_limits is True
    assert res_s2.must_flag is True


@pytest.mark.fast
def test_decoy_strata_never_flagged(
    limits: dict[str, ParameterLimitConfig],
) -> None:
    """D-015: Decoy strata (S3, S4, S5) must NOT be flagged as defective."""
    normal_values: dict[str, dict[int, float]] = {
        "iddq_standby": {0: 11.0, 24: 11.5, 96: 12.0, 168: 12.5},
        "leakage_input": {0: 2.5, 24: 2.7, 96: 3.0, 168: 3.2},
        "prop_delay": {0: 10.0, 24: 10.1, 96: 10.2, 168: 10.3},
        "vth_shift": {0: 0.0, 24: 0.5, 96: 1.0, 168: 1.5},
        "icc_active": {0: 25.0, 24: 25.2, 96: 25.4, 168: 25.6},
        "output_res": {0: 50.0, 24: 50.2, 96: 50.4, 168: 50.6},
    }

    # S3 Decoy Healthy
    res_s3 = derive_part_labels(normal_values, limits=limits)
    assert res_s3.stratum == Stratum.S3_DECOY_HEALTHY
    assert res_s3.failure_label == FailureLabel.HEALTHY
    assert res_s3.must_flag is False

    # S4 Decoy Sensor Artefact
    res_s4 = derive_part_labels(normal_values, limits=limits, has_sensor_artefact=True)
    assert res_s4.stratum == Stratum.S4_DECOY_SENSOR
    assert res_s4.failure_label == FailureLabel.HEALTHY
    assert res_s4.must_flag is False

    # S5 Decoy Lot Shift
    res_s5 = derive_part_labels(normal_values, limits=limits, is_lot_shifted=True)
    assert res_s5.stratum == Stratum.S5_LOT_SHIFT
    assert res_s5.failure_label == FailureLabel.HEALTHY
    assert res_s5.must_flag is False


# =============================================================================
# 4. Catastrophic Step Jumps & Measurement Record Compatibility
# =============================================================================


@pytest.mark.fast
def test_catastrophic_step_jump_derives_failed(
    limits: dict[str, ParameterLimitConfig],
) -> None:
    """Sudden failure step jump between readpoints derives as FAILED."""
    step_values: dict[str, dict[int, float]] = {
        "iddq_standby": {
            0: 10.0,
            24: 10.5,
            96: 55.0,
            168: 56.0,
        },  # Sudden step jump exceeding 50.0 limit
        "leakage_input": {0: 2.0, 24: 2.1, 96: 2.2, 168: 2.3},
        "prop_delay": {0: 10.0, 24: 10.1, 96: 10.2, 168: 10.3},
        "vth_shift": {0: 0.0, 24: 0.5, 96: 1.0, 168: 1.5},
        "icc_active": {0: 25.0, 24: 25.2, 96: 25.4, 168: 25.6},
        "output_res": {0: 50.0, 24: 50.2, 96: 50.4, 168: 50.6},
    }

    res = derive_part_labels(step_values, limits=limits)
    assert res.step_failure_detected is True
    assert res.failure_label == FailureLabel.FAILED
    assert res.must_flag is True


@pytest.mark.fast
def test_recompute_ground_truth_from_measurement_records(
    strata_gen: StrataGenerator,
    limits: dict[str, ParameterLimitConfig],
) -> None:
    """Recompute ground truth labels directly from MeasurementRecord sequence."""
    lot = strata_gen.generate_stratified_lot("L-2026-REC", n_parts=20)
    records = convert_lot_to_records(lot, limits=limits)

    recomputed = recompute_ground_truth_labels(records, limits=limits)
    assert len(recomputed) == 20
    for part in lot.parts:
        assert part.component_id in recomputed


# =============================================================================
# 5. Hypothesis Property Testing
# =============================================================================


@settings(max_examples=10, deadline=None)
@given(
    v0=st.floats(min_value=5.0, max_value=25.0),
    drift_factor=st.floats(min_value=0.0, max_value=2.0),
)
def test_hypothesis_label_derivation_invariants(
    v0: float,
    drift_factor: float,
) -> None:
    """Hypothesis property fuzzing: Stratum and escape definitions are self-consistent."""
    limits = default_parameter_limits()
    v168 = v0 + drift_factor * 15.0

    test_vals: dict[str, dict[int, float]] = {
        "iddq_standby": {0: v0, 24: v0 + 0.2, 96: v0 + 0.5, 168: v168},
        "leakage_input": {0: 2.0, 24: 2.1, 96: 2.2, 168: 2.5},
        "prop_delay": {0: 10.0, 24: 10.1, 96: 10.2, 168: 10.3},
        "vth_shift": {0: 0.0, 24: 0.1, 96: 0.2, 168: 0.3},
        "icc_active": {0: 25.0, 24: 25.1, 96: 25.2, 168: 25.3},
        "output_res": {0: 50.0, 24: 50.1, 96: 50.2, 168: 50.3},
    }

    res = derive_part_labels(test_vals, limits=limits)

    # Invariant: If outside limits, MUST be S0_CLEAR_FAIL
    if not res.is_inside_limits:
        assert res.stratum == Stratum.S0_CLEAR_FAIL
        assert res.must_flag is True

    # Invariant: If is_escape, MUST be inside limits AND defective
    if res.is_escape:
        assert res.is_inside_limits is True
        assert res.failure_label in (FailureLabel.LATENT_DEFECT, FailureLabel.FAILED)
        assert res.must_flag is True

    # Invariant: If healthy, CANNOT be escape
    if res.failure_label == FailureLabel.HEALTHY:
        assert res.is_escape is False
