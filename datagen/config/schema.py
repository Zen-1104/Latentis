"""Schema definitions for synthetic dataset generation (DATA_GENERATION_SPEC.md, DATASET_SPEC.md).

Owner: Data + ML Engineer
Charter: Pure numeric core, datagen/**, model artifacts.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from datagen.config.provenance import TaggedParameter

# =============================================================================
# 1. Domain Enums
# =============================================================================


class ComponentType(StrEnum):
    """Supported semiconductor component types (DATASET_SPEC.md § 2)."""

    CMOS_LOGIC = "CMOS_LOGIC"
    SRAM = "SRAM"
    LDO_REG = "LDO_REG"
    OPAMP = "OPAMP"
    POWER_MOSFET = "POWER_MOSFET"


class ParameterName(StrEnum):
    """Measured device parameters carrying distinct physics (DATASET_SPEC.md § 4)."""

    IDDQ_STANDBY = "iddq_standby"
    LEAKAGE_INPUT = "leakage_input"
    PROP_DELAY = "prop_delay"
    VTH_SHIFT = "vth_shift"
    ICC_ACTIVE = "icc_active"
    OUTPUT_RES = "output_res"


class DegradationClass(StrEnum):
    """Ground-truth degradation behaviour classes (DATASET_SPEC.md § 6)."""

    HEALTHY_STABLE = "healthy_stable"
    HEALTHY_NOISY = "healthy_noisy"
    GRADUAL_DRIFT = "gradual_drift"
    ACCELERATED_DRIFT = "accelerated_drift"
    EARLY_LATENT_DEFECT = "early_latent_defect"
    SUDDEN_FAILURE = "sudden_failure"
    INTERMITTENT = "intermittent"
    SENSOR_NOISE_ANOMALY = "sensor_noise_anomaly"
    LOT_SHIFT = "lot_shift"


class Stratum(StrEnum):
    """Difficulty strata and escape definitions (DATASET_SPEC.md § 7)."""

    S0_CLEAR_FAIL = "S0-clear-fail"
    S1_ESCAPE_ANOMALY = "S1-escape-anomaly"
    S2_ESCAPE_DRIFT = "S2-escape-drift"
    S3_DECOY_HEALTHY = "S3-decoy-healthy"
    S4_DECOY_SENSOR = "S4-decoy-sensor"
    S5_LOT_SHIFT = "S5-lot-shift"


class MeasurementStatus(StrEnum):
    """Status flags for individual measurement readings (DATASET_SPEC.md § 5.1)."""

    OK = "OK"
    BELOW_LOD = "BELOW_LOD"
    OVERRANGE = "OVERRANGE"
    NOT_MEASURED = "NOT_MEASURED"
    SUSPECT = "SUSPECT"


class FailureLabel(StrEnum):
    """Ground-truth failure labels (DATASET_SPEC.md § 5.3)."""

    HEALTHY = "HEALTHY"
    LATENT_DEFECT = "LATENT_DEFECT"
    FAILED = "FAILED"


# =============================================================================
# 2. Sub-configurations
# =============================================================================


class PartsPerLotConfig(BaseModel):
    """Distribution of part counts per lot (DATASET_SPEC.md § 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dist: str = "loguniform"
    low: int = 30
    high: int = 500


class ScaleConfig(BaseModel):
    """Default scale parameters for the synthetic burn-in corpus (DATASET_SPEC.md § 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n_lots: int = 40
    parts_per_lot: PartsPerLotConfig = Field(default_factory=PartsPerLotConfig)


class SpecialLotsConfig(BaseModel):
    """Injected stress and edge-case lot counts (DATA_GENERATION_SPEC.md § 7)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lot_shift: int = 2
    unit_inconsistent: int = 2
    single_part: int = 1
    zero_iqr: int = 1
    tiny_n: int = 1
    tester_drift: int = 1


class ClassMixtureConfig(BaseModel):
    """Per-lot class mixture proportions with provenance tags (DATA_GENERATION_SPEC.md § 7)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    healthy_stable: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(0.62, "dominant class in a mature process")
    )
    healthy_noisy: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(0.12, "FP pressure")
    )
    gradual_drift: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(0.15, "normal wear-in")
    )
    accelerated_drift: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(0.04, "part of the 3% defect budget")
    )
    early_latent_defect: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(0.04, "Module A target")
    )
    sudden_failure: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(0.01, "sanity stratum")
    )
    intermittent: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(0.01, "acknowledged hard case")
    )
    sensor_noise_anomaly: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(0.01, "attribution test")
    )

    @model_validator(mode="after")
    def validate_mixture_sum(self) -> ClassMixtureConfig:
        """Mixture proportions must sum to 1.0 within numerical tolerance."""
        total = (
            float(self.healthy_stable.value)
            + float(self.healthy_noisy.value)
            + float(self.gradual_drift.value)
            + float(self.accelerated_drift.value)
            + float(self.early_latent_defect.value)
            + float(self.sudden_failure.value)
            + float(self.intermittent.value)
            + float(self.sensor_noise_anomaly.value)
        )
        if abs(total - 1.0) > 1e-3:
            raise ValueError(f"Class mixture proportions must sum to 1.0, got {total:.4f}")
        return self


def default_ea_ev() -> dict[str, TaggedParameter[float]]:
    """Default activation energies per parameter (DATA_GENERATION_SPEC.md § 7, D-B-01)."""
    return {
        "iddq_standby": TaggedParameter.cited(
            0.7, source="D-B-01", rationale="common default; swept in sensitivity"
        ),
        "leakage_input": TaggedParameter.assumed(
            0.7, rationale="within cited 0.3-0.7 eV range per D-B-01"
        ),
        "prop_delay": TaggedParameter.assumed(
            0.5, rationale="NBTI-like; within cited 0.3-0.7 eV range per D-B-01"
        ),
        "vth_shift": TaggedParameter.assumed(
            0.5, rationale="NBTI-like; within cited 0.3-0.7 eV range per D-B-01"
        ),
        "icc_active": TaggedParameter.assumed(
            0.6, rationale="carrier mobility temperature dependence mechanism"
        ),
        "output_res": TaggedParameter.assumed(
            0.9, rationale="package/interconnect mechanism per D-B-01"
        ),
    }


class PhysicsConfig(BaseModel):
    """Arrhenius acceleration and thermal physics (DATA_GENERATION_SPEC.md § 2, D-B-01)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    k_boltzmann_ev_per_k: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.cited(
            8.617333262e-5, source="SI/CODATA", rationale="Boltzmann constant in eV/K"
        )
    )
    t_ref_c: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.cited(
            125.0, source="D-A-02", rationale="MIL-STD-883 reference burn-in temperature in Celsius"
        )
    )
    ea_ev: dict[str, TaggedParameter[float]] = Field(default_factory=default_ea_ev)

    @field_validator("ea_ev")
    @classmethod
    def validate_ea_entries(
        cls, v: dict[str, TaggedParameter[float]]
    ) -> dict[str, TaggedParameter[float]]:
        for param, tagged in v.items():
            val = float(tagged.value)
            if not (0.1 <= val <= 2.0):
                raise ValueError(f"Activation energy for '{param}'={val} eV outside [0.1, 2.0] eV.")
        return v


class ProcessVariationConfig(BaseModel):
    """Lot-to-lot and part-to-part baseline distributions (DATA_GENERATION_SPEC.md § 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sigma_lot_ratio: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.40, "ratio of sigma_lot to sigma_within per DQ-01; swept in sensitivity"
        )
    )
    iddq_nominal: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            11.0, "D-B-04 midpoint of 8-14 uA nominal range"
        )
    )
    leakage_nominal: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            3.0, "D-B-04 midpoint of 1-5 nA nominal range"
        )
    )
    prop_delay_nominal: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            10.0, "D-B-04 midpoint of 8-12 ns nominal range"
        )
    )
    vth_shift_nominal: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(0.0, "symmetric around 0.0 mV baseline")
    )
    icc_nominal: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(25.0, "midpoint of 20-30 mA nominal range")
    )
    output_res_nominal: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            50.0, "midpoint of 40-60 mOhm nominal range"
        )
    )


class DegradationModelConfig(BaseModel):
    """Parametric degradation trajectory parameters (DATA_GENERATION_SPEC.md § 2, § 3, § 7.1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    shape_exponent_mean: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.50, "sub-linear degradation exponent n < 1 per D-B-03"
        )
    )
    shape_exponent_spread: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.05, "narrow per-part shape variation per DATA_GENERATION_SPEC § 3"
        )
    )
    healthy_amplitude: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.01, "negligible degradation amplitude for healthy parts"
        )
    )
    gradual_drift_amplitude: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.15, "normal wear-in degradation amplitude"
        )
    )
    accelerated_drift_amplitude: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.85, "accelerated drift amplitude targeting limit crossing near 168h"
        )
    )
    early_latent_defect_amplitude: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.35, "elevated baseline outlier amplitude constrained inside limits"
        )
    )
    sudden_failure_step: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            2.50, "multiplicative step jump crossing absolute limit"
        )
    )
    max_rejection_attempts: int = 100


class FactorModelConfig(BaseModel):
    """Latent factor model loadings for correlation structure (DATA_GENERATION_SPEC.md § 5)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lambda_supply_iddq: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.70, "targets iddq-icc correlation rho ~ 0.65"
        )
    )
    lambda_supply_icc: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.75, "targets iddq-icc correlation rho ~ 0.65"
        )
    )
    lambda_supply_leakage: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.30, "targets iddq-leakage correlation rho ~ 0.25"
        )
    )
    lambda_leak_specific: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.60, "independent leakage path for joint-only anomaly detection"
        )
    )
    lambda_threshold_delay: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.65, "targets prop_delay-vth_shift correlation rho ~ 0.50"
        )
    )
    lambda_threshold_vth: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.60, "targets prop_delay-vth_shift correlation rho ~ 0.50"
        )
    )
    lambda_package_res: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.80, "independent package mechanism factor loading"
        )
    )
    joint_only_ratio: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.50, "proportion of early_latent_defect parts that are joint-only anomalies"
        )
    )


class TemperatureModelConfig(BaseModel):
    """Burn-in oven thermal zone model (DATA_GENERATION_SPEC.md § 6)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    setpoint_c: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.cited(
            125.0, source="D-A-02", rationale="MIL-STD-883 oven setpoint in Celsius"
        )
    )
    zone_offset_std_c: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            3.0, "thermal zone Gaussian offset standard deviation"
        )
    )
    zone_offset_clip_c: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            8.0, "maximum thermal zone deviation clip limit (+/- 8 C)"
        )
    )
    jitter_std_c: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.5, "per-read thermocouple measurement jitter standard deviation"
        )
    )


class SetupEffectsConfig(BaseModel):
    """Socket and tester setup effects and measurement noise (DATA_GENERATION_SPEC.md § 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    socket_offset_scale: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.05, "D-I-03/D-CD-04 socket contact resistance variation scale"
        )
    )
    tester_drift_slope: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.001, "linear measurement drift rate per hour"
        )
    )
    measurement_noise_scale: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.02, "base measurement error standard deviation"
        )
    )
    heteroscedasticity_exponent: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.derived(
            0.50, "shot-noise scaling exponent: sigma proportional to sqrt(value)"
        )
    )


class ImperfectionsConfig(BaseModel):
    """Injected realistic data imperfection rates (DATASET_SPEC.md § 8)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    missing_rate: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.015, "1.5% missing read-points per DATASET_SPEC § 8"
        )
    )
    below_lod_rate: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.005, "0.5% of leakage rows censored below LOD per DATASET_SPEC § 8"
        )
    )
    overrange_rate: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.002, "0.2% overrange readings per DATASET_SPEC § 8"
        )
    )
    duplicate_rate: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.003, "0.3% duplicate rows per DATASET_SPEC § 8"
        )
    )
    timestamp_jitter_rate: TaggedParameter[float] = Field(
        default_factory=lambda: TaggedParameter.assumed(
            0.010, "1% timestamp jitter per DATASET_SPEC § 8"
        )
    )


# =============================================================================
# 3. Parameter Limits & Profile
# =============================================================================


class ParameterLimitConfig(BaseModel):
    """Specifications and screening limits for a single parameter (DATASET_SPEC.md § 4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit: str
    nominal_min: float | None = None
    nominal_max: float | None = None
    absolute_min: float | None = None
    absolute_max: float | None = None
    degradation_direction: str = "increase"


def default_parameter_limits() -> dict[str, ParameterLimitConfig]:
    """Default screening limits from DATASET_SPEC.md § 4."""
    return {
        "iddq_standby": ParameterLimitConfig(
            unit="uA", nominal_min=8.0, nominal_max=14.0, absolute_max=50.0
        ),
        "leakage_input": ParameterLimitConfig(
            unit="nA", nominal_min=1.0, nominal_max=5.0, absolute_max=100.0
        ),
        "prop_delay": ParameterLimitConfig(
            unit="ns", nominal_min=8.0, nominal_max=12.0, absolute_max=20.0
        ),
        "vth_shift": ParameterLimitConfig(
            unit="mV",
            nominal_min=0.0,
            nominal_max=0.0,
            absolute_min=-50.0,
            absolute_max=50.0,
            degradation_direction="bidirectional",
        ),
        "icc_active": ParameterLimitConfig(
            unit="mA", nominal_min=20.0, nominal_max=30.0, absolute_max=45.0
        ),
        "output_res": ParameterLimitConfig(
            unit="mOhm", nominal_min=40.0, nominal_max=60.0, absolute_max=100.0
        ),
    }


class ProfileConfig(BaseModel):
    """Screening profile configuration (read-points and absolute limits)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = "mil_std_883_like"
    read_points: list[int] = Field(default_factory=lambda: [0, 24, 96, 168])
    limits: dict[str, ParameterLimitConfig] = Field(default_factory=default_parameter_limits)


# =============================================================================
# 4. Root DatagenConfig
# =============================================================================


class DatagenConfig(BaseModel):
    """Complete, validated synthetic dataset generator configuration.

    Owner: Data + ML Engineer
    Implements: DR-01, DR-03, DATA_GENERATION_SPEC.md, DATASET_SPEC.md
    """

    model_config = ConfigDict(extra="forbid")

    seed: int = 20260930
    profile: str = "mil_std_883_like"
    scale: ScaleConfig = Field(default_factory=ScaleConfig)
    special_lots: SpecialLotsConfig = Field(default_factory=SpecialLotsConfig)
    class_mixture: ClassMixtureConfig = Field(default_factory=ClassMixtureConfig)
    physics: PhysicsConfig = Field(default_factory=PhysicsConfig)
    process: ProcessVariationConfig = Field(default_factory=ProcessVariationConfig)
    degradation: DegradationModelConfig = Field(default_factory=DegradationModelConfig)
    factors: FactorModelConfig = Field(default_factory=FactorModelConfig)
    temperature: TemperatureModelConfig = Field(default_factory=TemperatureModelConfig)
    setup_effects: SetupEffectsConfig = Field(default_factory=SetupEffectsConfig)
    imperfections: ImperfectionsConfig = Field(default_factory=ImperfectionsConfig)
