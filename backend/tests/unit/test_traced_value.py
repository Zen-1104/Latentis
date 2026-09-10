"""Unit tests for TracedValue provenance (T-314, FR-403).

Implements TEST-PROV-001 (closed unit enum, never blank), TEST-PROV-002
(inputs/parameters match the registry declaration both directions), and
TEST-PROV-006 (property naming ``trace``, ``trace_raw``, and
``resolve_unit``: validation matrix plus determinism) against
PROVENANCE_SPEC § 3.
"""

from __future__ import annotations

import pytest

from backend.core.traced import UNIT_ENUM, TracedValue, resolve_unit, trace, trace_raw

HASH = "fixture-hash"


@pytest.mark.fast
def test_unit_never_blank() -> None:
    """TEST-PROV-001: every TracedValue carries a closed-enum unit."""
    assert "" not in UNIT_ENUM
    for unit in ("uA", "ns", "sigma", "ratio", "hours", "index"):
        assert unit in UNIT_ENUM
    tv = trace(
        22.4,
        "uA",
        "dpat.limit_high_v1",
        {"median": 10.4, "k": 6.0, "robust_sigma": 2.0},
        {},
        HASH,
        1,
    )
    assert tv.unit == "uA"
    assert isinstance(tv, TracedValue)
    with pytest.raises(ValueError):
        trace(
            22.4,
            "",
            "dpat.limit_high_v1",
            {"median": 10.4, "k": 6.0, "robust_sigma": 2.0},
            {},
            HASH,
            1,
        )
    with pytest.raises(ValueError):
        trace(
            22.4,
            "furlongs",
            "dpat.limit_high_v1",
            {"median": 10.4, "k": 6.0, "robust_sigma": 2.0},
            {},
            HASH,
            1,
        )


@pytest.mark.fast
def test_inputs_match_registry_operands() -> None:
    """TEST-PROV-002: inputs/parameters equal the declaration, both ways."""
    good = trace(
        17.4, "sigma", "dpat.z_v1", {"x": 45.2, "median": 10.4, "robust_sigma": 2.0}, {}, HASH, 1
    )
    assert set(good.inputs) == {"x", "median", "robust_sigma"}
    assert set(good.parameters) == set()
    # Missing operand fails.
    with pytest.raises(ValueError):
        trace(17.4, "sigma", "dpat.z_v1", {"x": 45.2, "median": 10.4}, {}, HASH, 1)
    # Extra operand fails.
    with pytest.raises(ValueError):
        trace(
            17.4,
            "sigma",
            "dpat.z_v1",
            {"x": 45.2, "median": 10.4, "robust_sigma": 2.0, "mood": "grim"},
            {},
            HASH,
            1,
        )
    # Missing parameter fails.
    with pytest.raises(ValueError):
        trace(2.0, "uA", "robust.sigma_iqr_v1", {"iqr": 2.7}, {}, HASH, 1)
    # Unknown formula fails (a hard-coded number has no formula, INV-1).
    with pytest.raises(ValueError):
        trace(2.0, "uA", "vibes.adjusted", {"iqr": 2.7}, {"divisor": 1.35}, HASH, 1)
    # Non-finite values never enter the ledger.
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            trace(
                bad,
                "uA",
                "raw.measurement",
                {"measured_value": 1.0, "source_row": "s:1"},
                {},
                HASH,
                1,
            )
    # Raw observations trace to their file source.
    raw = trace_raw(12.1, "uA", "ingest-7:42", HASH, 2)
    assert raw.formula_id == "raw.measurement"
    assert raw.inputs["source_row"] == "ingest-7:42"
    with pytest.raises(ValueError):
        trace_raw(12.1, "uA", "", HASH, 2)


@pytest.mark.fast
def test_trace_validation_matrix_and_determinism() -> None:
    """TEST-PROV-006: trace/trace_raw/resolve_unit validate and repeat."""
    first = trace(
        22.4,
        "uA",
        "dpat.limit_high_v1",
        {"median": 10.4, "k": 6.0, "robust_sigma": 2.0},
        {},
        HASH,
        1,
        model_version="anomaly-1.0.0",
    )
    second = trace(
        22.4,
        "uA",
        "dpat.limit_high_v1",
        {"median": 10.4, "k": 6.0, "robust_sigma": 2.0},
        {},
        HASH,
        1,
        model_version="anomaly-1.0.0",
    )
    assert first == second
    assert first.model_version == "anomaly-1.0.0"

    assert resolve_unit("same_as:median", {"median": "uA"}) == "uA"
    assert resolve_unit("index", {}) == "index"
    with pytest.raises(ValueError):
        resolve_unit("same_as:median", {})
    with pytest.raises(ValueError):
        resolve_unit("furlongs", {})

    raw_first = trace_raw(12.1, "uA", "ingest-7:42", HASH, 2)
    raw_second = trace_raw(12.1, "uA", "ingest-7:42", HASH, 2)
    assert raw_first == raw_second

    with pytest.raises(ValueError):
        trace(1.0, "uA", "raw.measurement", {"measured_value": 1.0}, {}, "", 1)
    with pytest.raises(ValueError):
        trace(
            1.0, "uA", "raw.measurement", {"measured_value": 1.0, "source_row": "s:1"}, {}, HASH, -1
        )
    with pytest.raises(ValueError):
        trace(
            True,
            "uA",
            "raw.measurement",
            {"measured_value": 1.0, "source_row": "s:1"},
            {},
            HASH,
            1,
        )
