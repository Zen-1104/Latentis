"""Unit tests for datagen configuration schema and provenance models (T-201, DR-03).

Owner: Data + ML Engineer
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from datagen.config import (
    ClassMixtureConfig,
    ComponentType,
    DatagenConfig,
    DegradationClass,
    ParameterName,
    PhysicsConfig,
    Stratum,
    TaggedParameter,
    extract_parameter_manifest,
    get_default_config,
    load_config,
    save_config,
)


@pytest.mark.fast
def test_default_config_validity() -> None:
    """Verify default DatagenConfig instantiates cleanly with full provenance coverage."""
    cfg = get_default_config()
    assert cfg.seed == 20260930
    assert cfg.scale.n_lots == 40
    assert cfg.scale.parts_per_lot.low == 30
    assert cfg.scale.parts_per_lot.high == 500
    assert cfg.special_lots.lot_shift == 2
    assert cfg.special_lots.zero_iqr == 1

    # Extract all parameters and assert 100% are tagged
    params = extract_parameter_manifest(cfg)
    assert len(params) > 50
    for p in params:
        assert p["provenance"] in ("cited", "derived", "assumed")
        if p["provenance"] == "cited":
            assert p["source"], f"Parameter {p['path']} missing source"
        else:
            assert p["rationale"], f"Parameter {p['path']} missing rationale"


@pytest.mark.fast
def test_yaml_and_json_roundtrip(tmp_path: Path) -> None:
    """Verify configuration serializes and deserializes losslessly across YAML and JSON."""
    cfg = get_default_config()

    yaml_path = tmp_path / "test_config.yaml"
    json_path = tmp_path / "test_config.json"

    save_config(cfg, yaml_path)
    save_config(cfg, json_path)

    loaded_yaml = load_config(yaml_path)
    loaded_json = load_config(json_path)

    assert loaded_yaml.seed == cfg.seed
    assert loaded_json.seed == cfg.seed
    assert float(loaded_yaml.physics.k_boltzmann_ev_per_k.value) == float(
        cfg.physics.k_boltzmann_ev_per_k.value
    )
    assert float(loaded_json.physics.k_boltzmann_ev_per_k.value) == float(
        cfg.physics.k_boltzmann_ev_per_k.value
    )


@pytest.mark.fast
def test_class_mixture_sum_validation() -> None:
    """Verify class mixture enforces that proportions sum to 1.0."""
    with pytest.raises(ValueError, match=r"proportions must sum to 1\.0"):
        ClassMixtureConfig(
            healthy_stable=TaggedParameter.assumed(0.90, "dominant"),
            healthy_noisy=TaggedParameter.assumed(0.50, "too high sum"),
        )


@pytest.mark.fast
def test_extra_fields_forbidden() -> None:
    """Verify extra/unknown configuration fields are strictly rejected (anti-pollution)."""
    raw = get_default_config().model_dump(mode="json")
    raw["unexpected_knob"] = 123
    with pytest.raises(ValidationError):
        DatagenConfig.model_validate(raw)


@pytest.mark.fast
def test_domain_enums_presence() -> None:
    """Verify all domain enums align with DATASET_SPEC.md § 2, 4, 6, 7."""
    assert len(ComponentType) == 5
    assert "CMOS_LOGIC" in [c.value for c in ComponentType]
    assert "POWER_MOSFET" in [c.value for c in ComponentType]

    assert len(ParameterName) == 6
    assert "iddq_standby" in [p.value for p in ParameterName]
    assert "vth_shift" in [p.value for p in ParameterName]

    assert len(DegradationClass) == 9
    assert "early_latent_defect" in [d.value for d in DegradationClass]
    assert "accelerated_drift" in [d.value for d in DegradationClass]

    assert len(Stratum) == 6
    assert "S1-escape-anomaly" in [s.value for s in Stratum]
    assert "S2-escape-drift" in [s.value for s in Stratum]


@pytest.mark.fast
def test_physics_activation_energy_bounds() -> None:
    """Verify activation energies are bounded by physical limits [0.1, 2.0] eV."""
    with pytest.raises(ValidationError, match=r"outside \[0\.1, 2\.0\] eV"):
        PhysicsConfig(
            ea_ev={
                "iddq_standby": TaggedParameter.cited(
                    -0.5, source="invalid", rationale="negative Ea unphysical"
                )
            }
        )
