"""Unit and property tests for Physical Model forward simulation (T-202).

Validates:
  1. Arrhenius acceleration factor (hand-computed known answer per D-B-01).
  2. Degradation shape function Phi_g (Phi(0) = 0, Phi(24) = 1, sub-linearity at 168 h).
  3. Thermal zone variations and thermal confound.
  4. Baseline v0 draws with latent factor correlations and right-skewed leakage.
  5. Per-part degradation amplitudes across degradation classes.
  6. Escape Set inside-limits constraint enforcement and analytical clipping (DATASET_SPEC § 7.1).
  7. Joint-only anomaly generation (DATA_GENERATION_SPEC § 5.1).
  8. Numerical stability, non-negativity, and reproducibility under fixed seed (INV-08).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from datagen import (
    ArrheniusModel,
    DatagenConfig,
    DegradationShapeModel,
    PhysicalModel,
    ShapeFamily,
    SyntheticDataGenerator,
    get_default_config,
)
from datagen.config.schema import (
    ComponentType,
    DegradationClass,
    ParameterName,
    default_parameter_limits,
)


@pytest.fixture
def default_config() -> DatagenConfig:
    """Fixture providing validated default generator configuration."""
    return get_default_config()


@pytest.fixture
def physical_model(default_config: DatagenConfig) -> PhysicalModel:
    """Fixture providing seeded PhysicalModel instance."""
    return PhysicalModel(default_config)


# =============================================================================
# 1. Arrhenius Acceleration Model Tests
# =============================================================================


@pytest.mark.fast
def test_arrhenius_hand_computed_reference_and_known_answer() -> None:
    """TEST-PHYS-001 / D-B-01 known-answer validation:

    AF = exp((Ea / k_B) * (1 / T_ref - 1 / T_stress))
    Evaluated on paper for Ea = 0.7 eV, T_stress = 150 °C, T_use = 90 °C => AF ≈ 23.85.
    At reference temperature 125 °C => AF == 1.0 exactly.
    """
    k_b = 8.617333262e-5  # eV/K
    arrhenius = ArrheniusModel(k_boltzmann_ev_per_k=k_b, t_ref_c=125.0)

    # 1. At reference temperature (125 °C), AF must be exactly 1.0
    af_ref = arrhenius.compute_af(temp_c=125.0, ea_ev=0.7)
    assert isinstance(af_ref, float)
    assert math.isclose(af_ref, 1.0, rel_tol=1e-9)

    # 2. Worked example from DOMAIN_RESEARCH.md § D-B-01:
    # Ea = 0.7 eV, T_stress = 150 °C (423.15 K), T_use = 90 °C (363.15 K) => AF ≈ 23.85
    equiv_hours = arrhenius.equivalent_field_hours(
        burn_in_hours=1.0,
        stress_temp_c=150.0,
        field_temp_c=90.0,
        ea_ev=0.7,
    )
    assert math.isclose(equiv_hours, 23.848, rel_tol=1e-3)

    # 3. Monotonicity with temperature: higher temperature => higher AF
    temps = [115.0, 120.0, 125.0, 130.0, 135.0]
    afs = [float(arrhenius.compute_af(t, ea_ev=0.7)) for t in temps]
    assert all(afs[i] < afs[i + 1] for i in range(len(afs) - 1))

    # 4. Monotonicity with activation energy when temp > t_ref
    af_low_ea = float(arrhenius.compute_af(133.0, ea_ev=0.3))
    af_high_ea = float(arrhenius.compute_af(133.0, ea_ev=0.9))
    assert (
        af_low_ea < af_high_ea
    ), "Higher activation energy must yield higher acceleration at elevated T"


@pytest.mark.fast
def test_arrhenius_invalid_inputs_aborts() -> None:
    """Verify ArrheniusModel rejects unphysical temperatures or negative activation energy."""
    arrhenius = ArrheniusModel(k_boltzmann_ev_per_k=8.617333262e-5, t_ref_c=125.0)

    # Below absolute zero
    with pytest.raises(ValueError, match="above absolute zero"):
        arrhenius.compute_af(temp_c=-280.0, ea_ev=0.7)

    # Negative activation energy
    with pytest.raises(ValueError, match="Activation energy must be positive"):
        arrhenius.compute_af(temp_c=125.0, ea_ev=-0.5)

    # Negative burn-in hours
    with pytest.raises(ValueError, match="Burn-in hours cannot be negative"):
        arrhenius.equivalent_field_hours(-10.0, 125.0, 55.0, 0.7)


# =============================================================================
# 2. Degradation Shape Model Tests
# =============================================================================


@pytest.mark.fast
def test_shape_model_normalization_and_sublinearity() -> None:
    """Verify shape model satisfies critical invariants:

    1. Phi(0) == 0.0 (no degradation at t=0).
    2. Phi(24) == 1.0 (normalization constraint).
    3. Sub-linear: for n = 0.5, Phi(168) = sqrt(7) ≈ 2.646 < 7.0 (linear baseline).
    """
    shape_power = DegradationShapeModel(ShapeFamily.POWER_LAW, default_exponent=0.50)

    # Invariant 1: Phi(0) == 0
    assert shape_power.evaluate(0.0) == 0.0

    # Invariant 2: Phi(24) == 1.0
    assert math.isclose(float(shape_power.evaluate(24.0)), 1.0, rel_tol=1e-9)

    # Invariant 3: Sub-linear at 96 h and 168 h
    phi_96 = float(shape_power.evaluate(96.0))
    phi_168 = float(shape_power.evaluate(168.0))
    expected_96 = (96.0 / 24.0) ** 0.5  # 4^0.5 = 2.0
    expected_168 = (168.0 / 24.0) ** 0.5  # 7^0.5 ≈ 2.64575

    assert math.isclose(phi_96, expected_96, rel_tol=1e-5)
    assert math.isclose(phi_168, expected_168, rel_tol=1e-5)
    assert phi_168 < 7.0, "Sub-linear shape must evaluate strictly below linear extrapolation (7.0)"

    # Test all other supported shape families satisfy Phi(0) = 0 and Phi(24) = 1
    for family in (ShapeFamily.LOG_TIME, ShapeFamily.SATURATING, ShapeFamily.LINEAR):
        model = DegradationShapeModel(family, time_constant_tau=24.0)
        assert model.evaluate(0.0) == 0.0
        assert math.isclose(float(model.evaluate(24.0)), 1.0, rel_tol=1e-6)


@pytest.mark.fast
def test_shape_model_vectorized_evaluation() -> None:
    """Verify shape model evaluates NumPy arrays correctly and monotonically."""
    shape_model = DegradationShapeModel(ShapeFamily.POWER_LAW, default_exponent=0.50)
    grid = np.array([0, 12, 24, 48, 96, 168], dtype=np.float64)
    res = shape_model.evaluate(grid)

    assert isinstance(res, np.ndarray)
    assert res[0] == 0.0
    assert math.isclose(res[2], 1.0, rel_tol=1e-7)
    # Strictly increasing
    assert np.all(np.diff(res) > 0)


# =============================================================================
# 3. Thermal Zone & Confound Tests
# =============================================================================


@pytest.mark.fast
def test_thermal_zone_confound_acceleration(physical_model: PhysicalModel) -> None:
    """Verify that oven thermal zones introduce a genuine physical degradation confound.

    A part in a hotter zone (e.g. +8 °C offset) must experience a strictly higher
    Arrhenius acceleration factor than a part in a cooler zone (-8 °C offset).
    """
    zones = physical_model.thermal_zones
    assert len(zones) >= 4, "Expected at least 4 chamber thermal zones"

    # Verify stable offsets are bounded within +/- zone_offset_clip_c (+/- 8 °C)
    clip_c = float(physical_model.config.temperature.zone_offset_clip_c.value)
    for zone in zones.values():
        assert -clip_c <= zone.offset_c <= clip_c
        assert math.isclose(zone.mean_temp_c, 125.0 + zone.offset_c, rel_tol=1e-7)

    # Test degradation confound: higher zone temp => higher AF
    af_hot = float(physical_model.arrhenius.compute_af(125.0 + 5.0, ea_ev=0.7))
    af_cool = float(physical_model.arrhenius.compute_af(125.0 - 5.0, ea_ev=0.7))

    assert af_hot > 1.0, "Hotter thermal zone must accelerate degradation (AF > 1.0)"
    assert af_cool < 1.0, "Cooler thermal zone must decelerate degradation (AF < 1.0)"
    assert af_hot > af_cool


# =============================================================================
# 4. Baseline Draw (v0) & Correlation Structure Tests
# =============================================================================


@pytest.mark.fast
def test_baseline_v0_draw_and_factor_correlation(physical_model: PhysicalModel) -> None:
    """Verify v0 draws:

    1. All values are finite and physically non-negative for unipolar parameters.
    2. Shared factor model induces target positive correlation between iddq and icc (rho ~ 0.65).
    3. Moderate correlation between prop_delay and vth_shift (rho ~ 0.50).
    4. Near-zero correlation between output_res and iddq_standby.
    5. Leakage parameters display positive right-skewness (LogNormal property per D-B-04).
    """
    n_samples = 2000
    iddq_vals = []
    icc_vals = []
    leak_vals = []
    delay_vals = []
    vth_vals = []
    res_vals = []

    lot_centres = physical_model.draw_lot_centres("L-2026-001", ComponentType.CMOS_LOGIC)

    for i in range(n_samples):
        draw = physical_model.draw_v0(
            component_id=f"C-TEST-{i:04d}",
            lot_id="L-2026-001",
            component_type=ComponentType.CMOS_LOGIC,
            lot_centre=lot_centres,
            degradation_class=DegradationClass.HEALTHY_STABLE,
        )
        v0 = draw.v0
        iddq_vals.append(v0[ParameterName.IDDQ_STANDBY.value])
        icc_vals.append(v0[ParameterName.ICC_ACTIVE.value])
        leak_vals.append(v0[ParameterName.LEAKAGE_INPUT.value])
        delay_vals.append(v0[ParameterName.PROP_DELAY.value])
        vth_vals.append(v0[ParameterName.VTH_SHIFT.value])
        res_vals.append(v0[ParameterName.OUTPUT_RES.value])

        # Physical floor: unipolar parameters must be positive
        assert v0[ParameterName.IDDQ_STANDBY.value] > 0
        assert v0[ParameterName.LEAKAGE_INPUT.value] > 0
        assert v0[ParameterName.PROP_DELAY.value] > 0
        assert v0[ParameterName.ICC_ACTIVE.value] > 0
        assert v0[ParameterName.OUTPUT_RES.value] > 0

    iddq_arr = np.array(iddq_vals)
    icc_arr = np.array(icc_vals)
    delay_arr = np.array(delay_vals)
    vth_arr = np.array(vth_vals)
    res_arr = np.array(res_vals)

    # 2. iddq <-> icc correlation: target ~ 0.65
    rho_iddq_icc = float(np.corrcoef(iddq_arr, icc_arr)[0, 1])
    assert 0.45 <= rho_iddq_icc <= 0.85, f"Expected rho(iddq, icc) ~ 0.65, got {rho_iddq_icc:.3f}"

    # 3. prop_delay <-> vth_shift correlation: target ~ 0.50
    rho_delay_vth = float(np.corrcoef(delay_arr, vth_arr)[0, 1])
    assert (
        0.30 <= rho_delay_vth <= 0.75
    ), f"Expected rho(delay, vth) ~ 0.50, got {rho_delay_vth:.3f}"

    # 4. output_res independence with iddq: target rho ~ 0
    rho_res_iddq = float(np.corrcoef(res_arr, iddq_arr)[0, 1])
    assert (
        abs(rho_res_iddq) < 0.20
    ), f"Expected near-zero correlation for output_res, got {rho_res_iddq:.3f}"

    # 5. Right-skewness of iddq: sample skewness must be positive
    mean_iddq = np.mean(iddq_arr)
    std_iddq = np.std(iddq_arr)
    skew_iddq = np.mean(((iddq_arr - mean_iddq) / std_iddq) ** 3)
    assert skew_iddq > 0.1, f"Expected positive skewness for iddq leakage, got {skew_iddq:.3f}"


# =============================================================================
# 5. Degradation Amplitudes & Trajectory Simulation Tests
# =============================================================================


@pytest.mark.fast
def test_per_part_amplitudes_across_classes(physical_model: PhysicalModel) -> None:
    """Verify that per-part amplitudes reflect their specified degradation class (T-202).

    Accelerated drift amplitude must significantly exceed gradual drift amplitude,
    which in turn must exceed healthy amplitude.
    """
    draw = physical_model.draw_v0(
        component_id="C-001",
        lot_id="L-001",
        component_type=ComponentType.CMOS_LOGIC,
    )
    v0 = draw.v0

    amp_healthy = physical_model.draw_amplitudes(v0, DegradationClass.HEALTHY_STABLE)
    amp_gradual = physical_model.draw_amplitudes(v0, DegradationClass.GRADUAL_DRIFT)
    amp_accel = physical_model.draw_amplitudes(v0, DegradationClass.ACCELERATED_DRIFT)

    param = ParameterName.IDDQ_STANDBY.value
    assert amp_healthy[param] < amp_gradual[param] < amp_accel[param]
    assert amp_accel[param] > 3.0 * amp_gradual[param]


@pytest.mark.fast
def test_trajectory_simulation_endpoints(physical_model: PhysicalModel) -> None:
    """Verify multi-point trajectory simulation across read-points {0, 24, 96, 168} h."""
    draw = physical_model.draw_v0(
        component_id="C-002",
        lot_id="L-001",
        component_type=ComponentType.CMOS_LOGIC,
    )
    traj = physical_model.simulate_trajectory(
        v0=draw,
        degradation_class=DegradationClass.GRADUAL_DRIFT,
        read_points=[0, 24, 96, 168],
    )

    param = ParameterName.IDDQ_STANDBY.value
    # At t=0, value equals v0
    assert traj.values[param][0] == draw.v0[param]

    # Monotonic degradation: values increase over burn-in
    assert (
        traj.values[param][0]
        <= traj.values[param][24]
        <= traj.values[param][96]
        <= traj.values[param][168]
    )


# =============================================================================
# 6. Escape Set Inside-Limits Enforcement & Clipping Tests (DATASET_SPEC § 7.1)
# =============================================================================


@pytest.mark.fast
def test_escape_set_inside_limits_enforcement(physical_model: PhysicalModel) -> None:
    """Verify that when enforce_inside_limits=True (for Escape Set S1/S2):

    All readings across all read-points {0, 24, 96, 168} are strictly inside limits:
        limit_low < value(part, p, t) < limit_high.
    """
    draw = physical_model.draw_v0(
        component_id="C-ESC-001",
        lot_id="L-001",
        component_type=ComponentType.CMOS_LOGIC,
        degradation_class=DegradationClass.EARLY_LATENT_DEFECT,
    )

    traj = physical_model.simulate_trajectory(
        v0=draw,
        degradation_class=DegradationClass.ACCELERATED_DRIFT,
        read_points=[0, 24, 96, 168],
        enforce_inside_limits=True,
    )

    limits = default_parameter_limits()

    for param, readings in traj.values.items():
        limit_cfg = limits[param]
        for t, val in readings.items():
            if limit_cfg.absolute_max is not None:
                assert val < limit_cfg.absolute_max, (
                    f"Parameter {param} violated absolute_max={limit_cfg.absolute_max} "
                    f"at {t}h: {val}"
                )
            if limit_cfg.absolute_min is not None:
                assert val > limit_cfg.absolute_min, (
                    f"Parameter {param} violated absolute_min={limit_cfg.absolute_min} "
                    f"at {t}h: {val}"
                )


# =============================================================================
# 7. Joint-Only Anomaly Generation Tests
# =============================================================================


@pytest.mark.fast
def test_joint_only_anomaly_generation(physical_model: PhysicalModel) -> None:
    """Verify joint-only anomaly parts:

    Marginal values remain inside standard lot limits (~2.5 sigma),
    but the independent leakage factor is perturbed off-manifold.
    """
    draw = physical_model.draw_v0(
        component_id="C-JOINT-001",
        lot_id="L-001",
        component_type=ComponentType.CMOS_LOGIC,
        is_joint_only=True,
    )

    assert draw.is_joint_only is True
    assert draw.factors["f_leak_specific"] > 2.0
    # Values remain within reasonable physical bounds
    assert draw.v0[ParameterName.LEAKAGE_INPUT.value] < 15.0


# =============================================================================
# 8. Reproducibility & Generator Integration Tests (INV-08)
# =============================================================================


@pytest.mark.fast
def test_physical_model_reproducibility(default_config: DatagenConfig) -> None:
    """INV-08: Same seed + same config => bit-identical trajectory simulation."""
    model_a = PhysicalModel(default_config)
    model_b = PhysicalModel(default_config)

    draw_a = model_a.draw_v0("C-REPRO-1", "L-001")
    draw_b = model_b.draw_v0("C-REPRO-1", "L-001")

    traj_a = model_a.simulate_trajectory(draw_a, DegradationClass.ACCELERATED_DRIFT)
    traj_b = model_b.simulate_trajectory(draw_b, DegradationClass.ACCELERATED_DRIFT)

    for p in traj_a.values:
        for t in traj_a.values[p]:
            assert traj_a.values[p][t] == traj_b.values[p][t]


@pytest.mark.fast
def test_synthetic_data_generator_holds_physics() -> None:
    """Verify SyntheticDataGenerator exposes the physical model seamlessly."""
    gen = SyntheticDataGenerator()
    assert hasattr(gen, "physics")
    assert isinstance(gen.physics, PhysicalModel)

    draw = gen.physics.draw_v0("C-GEN-01", "L-001")
    assert len(draw.v0) == 6


# =============================================================================
# 9. Hypothesis Property-Based Tests
# =============================================================================


@settings(max_examples=50)
@given(
    temp_c=st.floats(min_value=25.0, max_value=200.0),
    ea_ev=st.floats(min_value=0.2, max_value=1.5),
)
def test_hypothesis_arrhenius_properties(temp_c: float, ea_ev: float) -> None:
    """Property test: Arrhenius acceleration is strictly positive, non-NaN, and monotonic."""
    arrhenius = ArrheniusModel(k_boltzmann_ev_per_k=8.617333262e-5, t_ref_c=125.0)
    af = arrhenius.compute_af(temp_c=temp_c, ea_ev=ea_ev)

    assert isinstance(af, float)
    assert not math.isnan(af)
    assert not math.isinf(af)
    assert af > 0.0

    if temp_c > 125.0:
        assert af > 1.0
    elif temp_c < 125.0:
        assert af < 1.0
    else:
        assert math.isclose(af, 1.0, rel_tol=1e-7)
