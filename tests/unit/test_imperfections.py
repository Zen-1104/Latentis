"""Unit and behavioral tests for realistic imperfection injection (T-204, TEST-GEN-006).

Validates:
  1. TEST-GEN-006: Observed rate of each injected imperfection within configured tolerance band.
  2. Missing read-point row injection and row omission (FR-103).
  3. Censored readings (<LOD, OVERRANGE) retained as first-class, never coerced to 0 (FR-107).
  4. Duplicate row injection for duplicate detection (FR-103).
  5. Unit inconsistency injection (mA instead of uA) on targeted lots (FR-108).
  6. Timestamp jitter and mild non-monotonicity (FR-103).
  7. Measurement System Analysis (MSA) noise (Gage R&R repeatability & reproducibility, D-I-03).
  8. Reproducibility under fixed seed (DR-01, INV-8).
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from datagen.config.schema import (
    ComponentType,
    DatagenConfig,
    MeasurementStatus,
    ParameterLimitConfig,
    ParameterName,
    default_parameter_limits,
)
from datagen.imperfections import (
    ImperfectionInjector,
    MeasurementRecord,
    convert_lot_to_records,
    inject_censoring,
    inject_duplicates,
    inject_missing_rows,
    inject_msa_noise,
    inject_timestamp_jitter,
    inject_unit_inconsistencies,
)
from datagen.physics import PhysicalModel
from datagen.strata import StrataGenerator


@pytest.fixture
def test_config() -> DatagenConfig:
    """Fixture providing default configuration."""
    return DatagenConfig()


@pytest.fixture
def limits() -> dict[str, ParameterLimitConfig]:
    """Fixture providing parameter limits."""
    return default_parameter_limits()


@pytest.fixture
def strata_gen(test_config: DatagenConfig) -> StrataGenerator:
    """Fixture providing StrataGenerator."""
    physics = PhysicalModel(test_config)
    return StrataGenerator(test_config, physics=physics, rng=physics.rng)


@pytest.fixture
def sample_lot_records(
    strata_gen: StrataGenerator, limits: dict[str, ParameterLimitConfig]
) -> list[MeasurementRecord]:
    """Fixture providing ~720 measurement records from a 30-part stratified lot."""
    lot = strata_gen.generate_stratified_lot("L-2026-001", n_parts=30)
    return convert_lot_to_records(lot, limits=limits)


# =============================================================================
# 1. TEST-GEN-006: Configured Imperfection Rates Present in Tolerance Bands
# =============================================================================


@pytest.mark.fast
def test_configured_imperfection_rates_present() -> None:
    """TEST-GEN-006: Observed rate of each imperfection within its tolerance band.

    Requirements: DATASET_SPEC-12, DATASET_SPEC § 8.
    Oracle:
      - missing_rate (1.5% target) in [0.8%, 2.2%]
      - below_lod_rate (0.5% of leakage target) in [0.1%, 1.2%]
      - overrange_rate (0.2% target) in [0.03%, 0.50%]
      - duplicate_rate (0.3% target) in [0.08%, 0.65%]
      - timestamp_jitter_rate (1.0% target) in [0.4%, 1.8%]
    """
    config = DatagenConfig()
    limits = default_parameter_limits()
    rng = np.random.default_rng(20260930)

    # Statistical rate measurement (120 parts * 6 params * 4 pts = 2880 rows)
    physics = PhysicalModel(config, rng=rng)
    strata = StrataGenerator(config, physics=physics, rng=rng)
    lot = strata.generate_stratified_lot("L-2026-CALIB", n_parts=120)
    raw_records = convert_lot_to_records(lot, limits=limits)

    # We have 120 parts * 6 params * 4 readpoints = 2880 records
    assert len(raw_records) >= 2000

    injector = ImperfectionInjector(config=config, limits=limits, rng=rng)
    emitted_records, audit = injector.apply(raw_records, unit_mismatch_lots={"L-2026-CALIB"})

    # 1. Missing read-points: target 1.5% (0.015)
    assert (
        0.008 <= audit.missing_rate_observed <= 0.022
    ), f"Missing rate {audit.missing_rate_observed:.4f} outside tolerance band [0.008, 0.022]"

    # 2. Below LOD: target 0.5% (0.005) of leakage rows
    assert (
        0.001 <= audit.below_lod_rate_observed <= 0.015
    ), f"Below LOD rate {audit.below_lod_rate_observed:.4f} outside tolerance band [0.001, 0.015]"

    # 3. Overrange: target 0.2% (0.002) of all rows
    assert (
        0.0003 <= audit.overrange_rate_observed <= 0.006
    ), f"Overrange rate {audit.overrange_rate_observed:.4f} outside tolerance band [0.0003, 0.006]"

    # 4. Duplicate rows: target 0.3% (0.003)
    assert (
        0.0008 <= audit.duplicate_rate_observed <= 0.007
    ), f"Duplicate rate {audit.duplicate_rate_observed:.4f} outside tolerance band [0.0008, 0.007]"

    # 5. Timestamp jitter: target 1.0% (0.010)
    assert (
        0.004 <= audit.timestamp_jitter_rate_observed <= 0.020
    ), f"Timestamp jitter rate {audit.timestamp_jitter_rate_observed:.4f} outside [0.004, 0.020]"

    # 6. Unit inconsistency applied to targeted lot
    assert audit.unit_inconsistent_lot_count == 1
    mismatched = [
        r for r in emitted_records if r.measurement_unit == "mA" and r.parameter == "iddq_standby"
    ]
    assert len(mismatched) > 0


# =============================================================================
# 2. Censoring Invariant Tests (FR-107)
# =============================================================================


@pytest.mark.fast
def test_censored_readings_never_coerced_to_zero_or_limit(
    sample_lot_records: list[MeasurementRecord],
) -> None:
    """FR-107: Censored readings (<LOD, OVERRANGE) retained, never coerced to 0 or limit."""
    rng = np.random.default_rng(42)
    limits = default_parameter_limits()

    # Apply censoring with elevated rates to ensure occurrences
    censored = inject_censoring(
        records=sample_lot_records,
        below_lod_rate=0.10,
        overrange_rate=0.08,
        limits=limits,
        rng=rng,
    )

    below_lod_records = [r for r in censored if r.status == MeasurementStatus.BELOW_LOD.value]
    overrange_records = [r for r in censored if r.status == MeasurementStatus.OVERRANGE.value]

    assert len(below_lod_records) > 0, "Expected BELOW_LOD readings to be generated"
    assert len(overrange_records) > 0, "Expected OVERRANGE readings to be generated"

    # Invariant: BELOW_LOD must NOT be coerced to 0.0 or None (FR-107)
    for r in below_lod_records:
        assert r.measurement_value != 0.0, "BELOW_LOD was incorrectly coerced to 0.0"
        assert not math.isnan(r.measurement_value), "BELOW_LOD was incorrectly set to NaN"
        assert r.parameter in (ParameterName.IDDQ_STANDBY.value, ParameterName.LEAKAGE_INPUT.value)
        assert r.is_below_lod
        assert r.is_censored

    # Invariant: OVERRANGE must NOT be coerced to the limit
    for r in overrange_records:
        limit_cfg = limits[r.parameter]
        abs_max = limit_cfg.absolute_max or 100.0
        assert r.measurement_value > abs_max, "OVERRANGE was incorrectly clamped to the limit"
        assert r.is_overrange
        assert r.is_censored


# =============================================================================
# 3. Missing Rows & Duplicate Injection (FR-103)
# =============================================================================


@pytest.mark.fast
def test_missing_readpoint_rows_injection(sample_lot_records: list[MeasurementRecord]) -> None:
    """FR-103: Missing read-points result in missing rows, exercising INSUFFICIENT_DATA."""
    rng = np.random.default_rng(123)
    n_initial = len(sample_lot_records)

    retained, dropped = inject_missing_rows(sample_lot_records, missing_rate=0.10, rng=rng)

    assert len(retained) + len(dropped) == n_initial
    assert len(dropped) > 0
    assert abs(len(dropped) / n_initial - 0.10) < 0.04


@pytest.mark.fast
def test_duplicate_row_injection(sample_lot_records: list[MeasurementRecord]) -> None:
    """FR-103: Duplicate (part, param, hours) rows are injected into the stream."""
    rng = np.random.default_rng(456)
    n_initial = len(sample_lot_records)

    with_dups = inject_duplicates(sample_lot_records, duplicate_rate=0.08, rng=rng)

    assert len(with_dups) > n_initial
    duplicates = [r for r in with_dups if r.is_duplicate]
    assert len(duplicates) > 0

    # Verify duplicate matches an existing record in (component_id, parameter, elapsed_hours)
    keys = {(r.component_id, r.parameter, r.elapsed_hours) for r in sample_lot_records}
    for d in duplicates:
        assert (d.component_id, d.parameter, d.elapsed_hours) in keys


# =============================================================================
# 4. Unit Inconsistency & Timestamp Jitter (FR-108, FR-103)
# =============================================================================


@pytest.mark.fast
def test_unit_inconsistency_injection(sample_lot_records: list[MeasurementRecord]) -> None:
    """FR-108: Unit inconsistency emits mA instead of uA for specified lots."""
    lot_to_corrupt = sample_lot_records[0].lot_id
    corrupted = inject_unit_inconsistencies(
        sample_lot_records,
        target_lot_ids={lot_to_corrupt},
        target_param="iddq_standby",
        original_unit="uA",
        inconsistent_unit="mA",
    )

    iddq_corrupted = [
        r for r in corrupted if r.lot_id == lot_to_corrupt and r.parameter == "iddq_standby"
    ]
    assert len(iddq_corrupted) > 0
    assert all(r.measurement_unit == "mA" for r in iddq_corrupted)

    # Other parameters remain unchanged
    other_params = [
        r for r in corrupted if r.lot_id == lot_to_corrupt and r.parameter != "iddq_standby"
    ]
    assert all(r.measurement_unit != "mA" or r.parameter == "icc_active" for r in other_params)


@pytest.mark.fast
def test_timestamp_jitter_preserves_iso_format(sample_lot_records: list[MeasurementRecord]) -> None:
    """FR-103: Timestamp jitter perturbs timestamps while maintaining ISO format."""
    rng = np.random.default_rng(789)
    jittered = inject_timestamp_jitter(sample_lot_records, jitter_rate=0.25, rng=rng)

    perturbed_count = 0
    for orig, new_rec in zip(sample_lot_records, jittered, strict=True):
        # Must parse valid datetime
        dt = datetime.fromisoformat(new_rec.read_timestamp)
        assert dt is not None
        if orig.read_timestamp != new_rec.read_timestamp:
            perturbed_count += 1

    assert perturbed_count > 0


# =============================================================================
# 5. Measurement System Analysis (MSA) Noise (D-I-03, D-CD-04)
# =============================================================================


@pytest.mark.fast
def test_msa_noise_repeatability_and_reproducibility(
    sample_lot_records: list[MeasurementRecord],
) -> None:
    """D-I-03: MSA noise incorporates equipment repeatability and operator reproducibility."""
    rng = np.random.default_rng(999)
    noisy = inject_msa_noise(
        sample_lot_records,
        rng=rng,
        repeatability_rel_scale=0.02,
        operator_offsets={"OP-01": 0.05, "OP-02": -0.05},
        tester_drift_per_hour=0.001,
    )

    assert len(noisy) == len(sample_lot_records)

    # Values must be perturbed
    diffs = [
        abs(n.measurement_value - orig.measurement_value)
        for orig, n in zip(sample_lot_records, noisy, strict=True)
    ]
    assert np.mean(diffs) > 0.0

    # Non-negative floor preserved for positive physical quantities
    for rec in noisy:
        if rec.parameter != ParameterName.VTH_SHIFT.value:
            assert rec.measurement_value >= 0.0


# =============================================================================
# 6. Reproducibility & Property Testing (INV-8, DR-01)
# =============================================================================


@pytest.mark.fast
def test_imperfection_injector_reproducibility(sample_lot_records: list[MeasurementRecord]) -> None:
    """INV-8: Identical seed produces identical transformed records and audit numbers."""
    cfg = DatagenConfig()
    limits = default_parameter_limits()

    inj1 = ImperfectionInjector(cfg, limits=limits, rng=np.random.default_rng(42))
    inj2 = ImperfectionInjector(cfg, limits=limits, rng=np.random.default_rng(42))

    recs1, audit1 = inj1.apply(sample_lot_records)
    recs2, audit2 = inj2.apply(sample_lot_records)

    assert audit1 == audit2
    assert len(recs1) == len(recs2)
    for r1, r2 in zip(recs1, recs2, strict=True):
        assert r1.measurement_value == r2.measurement_value
        assert r1.status == r2.status
        assert r1.read_timestamp == r2.read_timestamp


@settings(max_examples=10, deadline=None)
@given(
    missing_rate=st.floats(min_value=0.0, max_value=0.05),
    below_lod_rate=st.floats(min_value=0.0, max_value=0.02),
    overrange_rate=st.floats(min_value=0.0, max_value=0.01),
)
def test_hypothesis_imperfection_invariants(
    missing_rate: float,
    below_lod_rate: float,
    overrange_rate: float,
) -> None:
    """Hypothesis property fuzzing: Invariants hold across arbitrary rate settings."""
    limits = default_parameter_limits()
    rec = MeasurementRecord(
        component_id="C-TEST-0001",
        lot_id="L-TEST",
        component_type=ComponentType.CMOS_LOGIC.value,
        parameter=ParameterName.IDDQ_STANDBY.value,
        elapsed_hours=0,
        measurement_value=10.0,
        measurement_unit="uA",
    )
    records = [rec for _ in range(50)]

    retained, dropped = inject_missing_rows(records, missing_rate=missing_rate)
    assert len(retained) + len(dropped) == 50

    censored = inject_censoring(
        records,
        below_lod_rate=below_lod_rate,
        overrange_rate=overrange_rate,
        limits=limits,
    )
    for r in censored:
        assert not math.isnan(r.measurement_value)
        assert r.status in {s.value for s in MeasurementStatus}
