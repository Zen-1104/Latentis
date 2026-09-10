"""Configuration models and provenance tag validators for datagen (DR-03, TEST-GEN-001).

Owner: Data + ML Engineer
Charter: Pure numeric core, datagen/**, model artifacts.
"""

from __future__ import annotations

from datagen.config.loader import (
    get_default_config,
    load_config,
    save_config,
)
from datagen.config.provenance import (
    InvalidProvenanceError,
    MissingProvenanceError,
    ProvenanceTag,
    ProvenanceTagError,
    TaggedParameter,
    UntaggedParameterError,
    enforce_provenance_tags,
    extract_parameter_manifest,
)
from datagen.config.schema import (
    ClassMixtureConfig,
    ComponentType,
    DatagenConfig,
    DegradationClass,
    DegradationModelConfig,
    FactorModelConfig,
    FailureLabel,
    ImperfectionsConfig,
    MeasurementStatus,
    ParameterLimitConfig,
    ParameterName,
    PartsPerLotConfig,
    PhysicsConfig,
    ProcessVariationConfig,
    ProfileConfig,
    ScaleConfig,
    SetupEffectsConfig,
    SpecialLotsConfig,
    Stratum,
    TemperatureModelConfig,
)

__all__ = [
    "ClassMixtureConfig",
    "ComponentType",
    "DatagenConfig",
    "DegradationClass",
    "DegradationModelConfig",
    "FactorModelConfig",
    "FailureLabel",
    "ImperfectionsConfig",
    "InvalidProvenanceError",
    "MeasurementStatus",
    "MissingProvenanceError",
    "ParameterLimitConfig",
    "ParameterName",
    "PartsPerLotConfig",
    "PhysicsConfig",
    "ProcessVariationConfig",
    "ProfileConfig",
    "ProvenanceTag",
    "ProvenanceTagError",
    "ScaleConfig",
    "SetupEffectsConfig",
    "SpecialLotsConfig",
    "Stratum",
    "TaggedParameter",
    "TemperatureModelConfig",
    "UntaggedParameterError",
    "enforce_provenance_tags",
    "extract_parameter_manifest",
    "get_default_config",
    "load_config",
    "save_config",
]
