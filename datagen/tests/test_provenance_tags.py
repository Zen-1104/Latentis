"""Adversarial and boundary tests for generator parameter provenance tags (TEST-GEN-001, DR-03).

Oracle: Every generator parameter must carry cited|derived|assumed;
an untagged parameter must abort generation, not warn.
"""

from __future__ import annotations

import copy
import warnings

import pytest
from pydantic import ValidationError

from datagen.config import (
    InvalidProvenanceError,
    MissingProvenanceError,
    ProvenanceTag,
    TaggedParameter,
    UntaggedParameterError,
    get_default_config,
    load_config,
)
from datagen.generator import SyntheticDataGenerator


@pytest.mark.fast
@pytest.mark.adversarial
def test_generator_refuses_untagged_parameter() -> None:
    """TEST-GEN-001 (P0, Adversarial, DR-03):

    Every generator parameter must carry cited|derived|assumed;
    an untagged parameter must abort generation, not warn.
    """
    base_cfg = get_default_config().model_dump(mode="json")

    # 1. Bare numeric parameter at root level of physics: abort, do not warn
    untagged_physics = copy.deepcopy(base_cfg)
    untagged_physics["physics"]["k_boltzmann_ev_per_k"] = 8.617333262e-5  # bare float!

    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        with pytest.raises((UntaggedParameterError, ValidationError)) as exc_info:
            SyntheticDataGenerator(untagged_physics)

        # Assert no warnings were issued as a weak substitute for aborting
        warning_messages = [str(w.message).lower() for w in recorded_warnings]
        assert not any(
            "untagged" in m or "provenance" in m for m in warning_messages
        ), "Generator issued warning instead of strictly aborting on untagged parameter."

    assert "untagged" in str(exc_info.value).lower() or "provenance" in str(exc_info.value).lower()

    # 2. Bare numeric parameter in nested activation energy map
    untagged_ea = copy.deepcopy(base_cfg)
    untagged_ea["physics"]["ea_ev"]["iddq_standby"] = 0.7  # bare float!

    with pytest.raises((UntaggedParameterError, ValidationError)):
        SyntheticDataGenerator(untagged_ea)

    # 3. Parameter dict missing 'provenance' key entirely
    missing_prov = copy.deepcopy(base_cfg)
    missing_prov["class_mixture"]["healthy_stable"] = {
        "value": 0.62,
        "rationale": "dominant class in a mature process",
    }

    with pytest.raises((MissingProvenanceError, UntaggedParameterError, ValidationError)):
        SyntheticDataGenerator(missing_prov)

    # 4. Invalid/unrecognized provenance tag (e.g. 'guessed', 'tuned', 'arbitrary')
    invalid_tag = copy.deepcopy(base_cfg)
    invalid_tag["class_mixture"]["healthy_stable"] = {
        "value": 0.62,
        "provenance": "guessed",  # Banned provenance
        "rationale": "guessed for convenience",
    }

    with pytest.raises((InvalidProvenanceError, ValidationError)):
        SyntheticDataGenerator(invalid_tag)

    # 5. Cited parameter missing mandatory literature/standard source
    missing_source = copy.deepcopy(base_cfg)
    missing_source["physics"]["k_boltzmann_ev_per_k"] = {
        "value": 8.617333262e-5,
        "provenance": "cited",
        "source": "",  # Empty source reference!
    }

    with pytest.raises((InvalidProvenanceError, ValidationError)):
        SyntheticDataGenerator(missing_source)

    # 6. Assumed/derived parameter missing mandatory rationale
    missing_rationale = copy.deepcopy(base_cfg)
    missing_rationale["class_mixture"]["gradual_drift"] = {
        "value": 0.15,
        "provenance": "assumed",
        "rationale": "   ",  # Whitespace-only rationale!
    }

    with pytest.raises((InvalidProvenanceError, ValidationError)):
        SyntheticDataGenerator(missing_rationale)


@pytest.mark.fast
@pytest.mark.adversarial
def test_generator_accepts_valid_tagged_configuration() -> None:
    """Verify that a compliant configuration initializes cleanly with all tags validated."""
    cfg = get_default_config()
    generator = SyntheticDataGenerator(cfg)

    manifest = generator.manifest()
    total = manifest["total_parameters"]
    breakdown = manifest["provenance_breakdown"]

    assert total > 0, "No parameters discovered in default configuration."
    assert sum(breakdown.values()) == total, "Provenance breakdown sum does not match total."
    assert (
        breakdown["cited"] > 0
    ), "Expected at least one cited parameter (e.g. Boltzmann constant)."
    assert breakdown["derived"] > 0, "Expected derived parameters."
    assert breakdown["assumed"] > 0, "Expected assumed parameters for sensitivity analysis."

    # Validate every parameter in the manifest
    for param in manifest["parameters"]:
        prov = param["provenance"]
        assert prov in (ProvenanceTag.CITED, ProvenanceTag.DERIVED, ProvenanceTag.ASSUMED)
        if prov == ProvenanceTag.CITED:
            assert param.get("source"), f"Cited parameter {param['path']} lacks source."
        else:
            assert param.get("rationale"), f"{prov} parameter {param['path']} lacks rationale."


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_tampering_deeply_nested_parameters() -> None:
    """Verify provenance enforcement on factor loadings, imperfections, and degradation models."""
    base_cfg = get_default_config().model_dump(mode="json")

    # Corrupt factor loadings
    tampered_factors = copy.deepcopy(base_cfg)
    tampered_factors["factors"]["lambda_supply_iddq"] = 0.70  # bare float
    with pytest.raises((UntaggedParameterError, ValidationError)):
        load_config(tampered_factors)

    # Corrupt imperfections
    tampered_imperfections = copy.deepcopy(base_cfg)
    tampered_imperfections["imperfections"]["missing_rate"] = 0.015  # bare float
    with pytest.raises((UntaggedParameterError, ValidationError)):
        load_config(tampered_imperfections)

    # Corrupt temperature model
    tampered_temp = copy.deepcopy(base_cfg)
    tampered_temp["temperature"]["zone_offset_std_c"] = {
        "value": 3.0,
        "provenance": "tuned",  # Illegal provenance tag
        "rationale": "tuned to pass tests",
    }
    with pytest.raises((InvalidProvenanceError, ValidationError)):
        load_config(tampered_temp)


@pytest.mark.fast
def test_tagged_parameter_numeric_semantics() -> None:
    """Verify TaggedParameter behaves cleanly as a numeric wrapper."""
    p = TaggedParameter.cited(value=0.7, source="D-B-01", rationale="swept default")
    assert float(p) == 0.7
    assert f"{p:.2f}" == "0.70"
    assert p.value == 0.7
    assert p.provenance == ProvenanceTag.CITED
    assert p.source == "D-B-01"

    # Frozen immutability
    with pytest.raises(ValidationError):
        p.value = 0.9  # type: ignore[misc]
