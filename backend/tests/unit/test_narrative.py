"""Unit tests for narrative explanations (T-312, FR-402/FR-405).

Implements TEST-EXPL-001 (no numeric literal in any template), TEST-EXPL-004
(every slot resolves to a payload TracedValue), TEST-EXPL-005 (property naming
``explain``: determinism from the same values), and TEST-EXPL-006
(known-answer naming ``render_arithmetic``) against EXPLAINABILITY_SPEC § 6.
"""

from __future__ import annotations

import re

import pytest

from backend.core.explain import (
    NARRATIVE_TEMPLATES,
    ExplanationResult,
    explain,
    render_arithmetic,
)
from backend.core.traced import TracedValue, trace

HASH = "fixture-hash"
LABELS = {
    "component_id": "C-0001",
    "unit": "uA",
    "parameter": "iddq_standby",
    "read_point_h": "24",
    "cohort_n": "187",
    "dpat_k": "6",
    "absolute_verdict": "PASS",
    "horizon_h": "168",
    "alpha": "0.10",
    "slope_unit": "uA/h",
    "band": "WATCH",
    "attribution_verdict": "PART",
    "socket_coherent": "0",
    "top_parameter": "iddq_standby",
}


def _slots() -> dict[str, TracedValue]:
    """Payload TracedValues behind the anomaly template (hand values)."""
    return {
        "observed": trace(
            45.2,
            "uA",
            "raw.measurement",
            {"measured_value": 45.2, "source_row": "ing:7"},
            {},
            HASH,
            1,
        ),
        "median": trace(10.4, "uA", "robust.median_v1", {"n": 187}, {}, HASH, 1),
        "robust_sigma": trace(
            2.0, "uA", "robust.sigma_iqr_v1", {"iqr": 2.7}, {"divisor": 1.35}, HASH, 1
        ),
        "dpat_limit_high": trace(
            22.4,
            "uA",
            "dpat.limit_high_v1",
            {"median": 10.4, "k": 6.0, "robust_sigma": 2.0},
            {},
            HASH,
            1,
        ),
        "z": trace(
            17.4,
            "sigma",
            "dpat.z_v1",
            {"x": 45.2, "median": 10.4, "robust_sigma": 2.0},
            {},
            HASH,
            1,
        ),
        "absolute_limit": trace(
            50.0,
            "uA",
            "raw.measurement",
            {"measured_value": 50.0, "source_row": "profile:1"},
            {},
            HASH,
            1,
        ),
    }


def _strip_variables(template: str) -> str:
    """Remove every {slot} and [[label]] span, leaving bare prose."""
    text = re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*\}", "", template)
    return re.sub(r"\[\[[A-Za-z_][A-Za-z0-9_]*\]\]", "", text)


@pytest.mark.fast
def test_no_numeric_literal_in_any_template() -> None:
    """TEST-EXPL-001: a digit outside a slot/label name fails the scan."""
    assert len(NARRATIVE_TEMPLATES) > 0
    for name, template in NARRATIVE_TEMPLATES.items():
        bare = _strip_variables(template)
        assert re.search(r"\d", bare) is None, f"Template {name!r} carries a literal number"


@pytest.mark.fast
def test_narrative_slots_resolve_to_payload_traced_values() -> None:
    """TEST-EXPL-004: every slot is a payload TracedValue; gaps refuse."""
    slots = _slots()
    ok = explain("anomaly", slots, LABELS)
    assert ok.text is not None
    assert "45.2" in ok.text and "PART" not in ok.text
    assert ok.unresolved_slots == () and ok.unresolved_labels == ()

    thin_slots = dict(slots)
    del thin_slots["z"]
    refused = explain("anomaly", thin_slots, LABELS)
    assert refused.text is None
    assert refused.unresolved_slots == ("z",)
    assert refused.warning is not None and "z" in refused.warning

    thin_labels = dict(LABELS)
    del thin_labels["band"]
    drift_slots: dict[str, TracedValue] = {
        "forecast_point": trace(
            32.3,
            "uA",
            "forecast.shape_point_v1",
            {"v0": 12.1, "amplitude": 6.6, "phi_168": 3.06},
            {},
            HASH,
            1,
        ),
        "bound_upper": trace(
            39.8, "uA", "conformal.upper_v1", {"point": 32.3, "q_hat": 7.5}, {}, HASH, 1
        ),
        "baseline": trace(
            58.3,
            "uA",
            "forecast.baseline_linear_v1",
            {"v0": 12.1, "amplitude": 6.6},
            {"linear_phi": 7.0},
            HASH,
            1,
        ),
        "long_slope": trace(
            0.1202,
            "uA/h",
            "slope.long_v1",
            {"point": 32.3, "v0": 12.1},
            {"horizon": 168.0},
            HASH,
            1,
        ),
        "safety_slope": trace(
            0.1805,
            "uA/h",
            "safety.safety_slope_v1",
            {"usable_margin": 30.32},
            {"horizon": 168.0},
            HASH,
            1,
        ),
        "slope_ratio": trace(
            0.666,
            "ratio",
            "safety.slope_ratio_v1",
            {"long_slope": 0.1202, "safety_slope": 0.1805},
            {},
            HASH,
            1,
        ),
    }
    refused_drift = explain("drift", drift_slots, thin_labels)
    assert refused_drift.text is None
    assert "band" in refused_drift.unresolved_labels


@pytest.mark.fast
def test_mandatory_guard_clauses_cannot_be_suppressed() -> None:
    """Uncertainty flags inject clauses that configuration cannot remove."""
    slots = _slots()
    flagged = explain(
        "anomaly",
        slots,
        LABELS,
        reduced_power=True,
        mondrian_level=2,
        guarantee_status="VOID",
        censored=True,
    )
    assert flagged.text is not None
    assert "power is reduced" in flagged.text
    assert "fallback grouping level 2" in flagged.text
    assert "VOID" in flagged.text
    assert "interval-censored" in flagged.text
    clean = explain("anomaly", slots, LABELS)
    assert clean.text is not None
    assert "power is reduced" not in clean.text


@pytest.mark.fast
def test_explain_deterministic_from_same_traced_values() -> None:
    """TEST-EXPL-005: identical payload values give byte-identical prose."""
    slots = _slots()
    first = explain("anomaly", slots, LABELS, reduced_power=True)
    second = explain("anomaly", slots, LABELS, reduced_power=True)
    assert isinstance(first, ExplanationResult)
    assert first == second
    assert first.text is not None and second.text is not None


@pytest.mark.fast
def test_render_arithmetic_known_answer() -> None:
    """TEST-EXPL-006: render_arithmetic substitutes and equates by hand."""
    limit = trace(
        22.4,
        "uA",
        "dpat.limit_high_v1",
        {"median": 10.4, "k": 6.0, "robust_sigma": 2.0},
        {},
        HASH,
        1,
    )
    assert render_arithmetic(limit) == "10.4 + 6.0 * 2.0 = 22.4"
    orphan = TracedValue(
        value=1.0,
        unit="uA",
        formula_id="no.such_formula",
        inputs={},
        parameters={},
        dataset_hash=HASH,
        display_precision=1,
    )
    with pytest.raises(ValueError):
        render_arithmetic(orphan)


@pytest.mark.fast
def test_unknown_template_raises() -> None:
    """An unregistered template name is a programmer error, raised loudly."""
    with pytest.raises(ValueError):
        explain("sonnet", _slots(), LABELS)
