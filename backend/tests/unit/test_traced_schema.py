"""Unit tests for the API TracedValue mirror (T-501, T-314 handoff).

Oracle: differential + behavioural contract. Values travel core →
``TracedValueSchema.from_core`` → JSON, and the shipped ``expression`` must
re-derive the value via the restricted evaluator with no access to
``backend.core`` (the RT-007 mechanism at the boundary). Rejections use
genuinely malformed payloads, not snapshots of current behaviour.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from pydantic import ValidationError

from backend.app.schemas import DataProvenance, TracedValueSchema
from backend.core.formulas import evaluate_expression, get_formula
from backend.core.traced import trace

HASH = "sha256:test-fixture"


def _core_value(
    formula_id: str,
    inputs: Mapping[str, float | str],
    parameters: Mapping[str, float | str],
    unit: str,
) -> TracedValueSchema:
    """Compute through the single implementation (registry fn), trace, carry."""
    spec = get_formula(formula_id)
    numeric = {k: v for k, v in {**inputs, **parameters}.items() if isinstance(v, (int, float))}
    value = float(spec.fn(**numeric))
    traced = trace(value, unit, formula_id, inputs, parameters, HASH, 2)
    return TracedValueSchema.from_core(traced)


@pytest.mark.fast
def test_provenance_survives_the_api_boundary() -> None:
    """Core → schema → JSON → independent rederivation reproduces the value."""
    cases = [
        ("dpat.limit_high_v1", {"median": 10.4, "k": 6.0, "robust_sigma": 2.0}, {}, "uA"),
        ("dpat.z_v1", {"x": 45.2, "median": 10.4, "robust_sigma": 2.0}, {}, "sigma"),
        (
            "risk.total_v1",
            {"anomaly": 0.8, "drift": 0.5, "margin": 0.2, "quality": 0.0, "credit": 0.0},
            {"w_a": 0.35, "w_b": 0.30, "w_m": 0.20, "w_q": 0.10, "w_c": 0.05},
            "index",
        ),
    ]
    for formula_id, inputs, parameters, unit in cases:
        carried = _core_value(formula_id, inputs, parameters, unit)
        payload = carried.model_dump(mode="json")
        assert payload["expression"] == get_formula(formula_id).expression
        assert payload["unit"] == unit
        assert payload["dataset_hash"] == HASH
        rederived = evaluate_expression(
            payload["expression"], {**payload["inputs"], **payload["parameters"]}
        )
        assert abs(rederived - payload["value"]) < 1e-9, formula_id
        round_tripped = TracedValueSchema.model_validate_json(carried.model_dump_json())
        assert round_tripped == carried


@pytest.mark.fast
def test_malformed_traced_payloads_are_rejected() -> None:
    """Fail-loud boundary: unknown formulas, bad units, non-finite, bools."""
    good_inputs = {"median": 10.4, "k": 6.0, "robust_sigma": 2.0}
    base = {
        "value": 22.4,
        "unit": "uA",
        "formula_id": "dpat.limit_high_v1",
        "expression": "median + k * robust_sigma",
        "inputs": good_inputs,
        "parameters": {},
        "dataset_hash": HASH,
        "display_precision": 1,
    }
    TracedValueSchema.model_validate(base)
    bad_variants = [
        {**base, "formula_id": "vibes.adjusted"},
        {**base, "unit": ""},
        {**base, "unit": "furlongs"},
        {**base, "value": float("inf")},
        {**base, "expression": "median - k * robust_sigma"},
        {**base, "inputs": {"median": 10.4, "k": 6.0}},
        {**base, "inputs": {**good_inputs, "mood": "grim"}},
        {**base, "inputs": {**good_inputs, "k": True}},
        {**base, "parameters": {"divisor": 1.35}},
        {**base, "dataset_hash": ""},
        {**base, "display_precision": -1},
    ]
    for variant in bad_variants:
        with pytest.raises(ValidationError):
            TracedValueSchema.model_validate(variant)


@pytest.mark.fast
def test_data_provenance_is_single_member_synthetic() -> None:
    """Supports TEST-PROV-004 at the API layer: no code path emits anything else."""
    assert [member.value for member in DataProvenance] == ["SYNTHETIC"]
    assert DataProvenance("SYNTHETIC") is DataProvenance.SYNTHETIC
    with pytest.raises(ValueError):
        DataProvenance("REAL")
