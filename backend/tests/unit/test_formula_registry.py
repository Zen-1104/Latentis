"""Unit tests for the formula registry (T-313, FR-408).

Implements TEST-EXPL-002 (coverage both directions: every formula_id core
emits is registered, every registered id is wrappable) and TEST-EXPL-007
(differential naming ``get_formula``, ``evaluate_expression``, and
``rederivation_rate``: fn and expression agree on random operands, and a
fully traced fixture payload re-derives at 1.0).
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.core.formulas import (
    FORMULAS,
    FormulaNotFoundError,
    evaluate_expression,
    get_formula,
    rederivation_rate,
)
from backend.core.traced import TracedValue, _wrap_verified

HASH = "fixture-hash"


def _fixture_operands(formula_id: str) -> tuple[dict[str, float | str], dict[str, float | str]]:
    """Valid scalar operands/parameters per registry entry for tests."""
    table: dict[str, tuple[dict[str, float | str], dict[str, float | str]]] = {
        "raw.measurement": ({"measured_value": 12.1, "source_row": "x"}, {}),
        "robust.median_v1": ({"n": 60.0}, {}),
        "robust.q1_v1": ({"n": 60.0}, {}),
        "robust.q3_v1": ({"n": 60.0}, {}),
        "robust.iqr_v1": ({"q3": 11.8, "q1": 9.1}, {}),
        "robust.sigma_iqr_v1": ({"iqr": 2.7}, {"divisor": 1.35}),
        "robust.sigma_mad_v1": ({"mad": 1.0}, {"mad_scale": 1.4826, "c_n": 1.05}),
        "dpat.limit_low_v1": ({"median": 10.4, "k": 6.0, "robust_sigma": 2.0}, {}),
        "dpat.limit_high_v1": ({"median": 10.4, "k": 6.0, "robust_sigma": 2.0}, {}),
        "dpat.z_v1": ({"x": 45.2, "median": 10.4, "robust_sigma": 2.0}, {}),
        "shape.phi_168_v1": ({"n_used": 26.0}, {}),
        "forecast.shape_point_v1": ({"v0": 12.1, "amplitude": 6.6, "phi_168": 3.06}, {}),
        "forecast.point_v1": ({"shape_point": 32.3, "residual_correction": 1.1}, {}),
        "forecast.baseline_linear_v1": ({"v0": 12.1, "amplitude": 6.6}, {"linear_phi": 7.0}),
        "conformal.q_hat_v1": ({"n_cal": 412.0, "k": 372.0, "alpha": 0.10}, {}),
        "conformal.upper_v1": ({"point": 32.3, "q_hat": 7.5}, {}),
        "slope.early_v1": ({"v24": 18.7, "v0": 12.1}, {"t_early": 24.0}),
        "slope.long_v1": ({"point": 32.3, "v0": 12.1}, {"horizon": 168.0}),
        "safety.usable_margin_v1": ({"limit_high": 50.0, "v0": 12.1}, {"margin_fraction": 0.20}),
        "safety.safety_slope_v1": ({"usable_margin": 30.32}, {"horizon": 168.0}),
        "safety.safety_slope_delta_v1": ({"delta_max": 5.0}, {"horizon": 168.0}),
        "safety.predicted_margin_v1": ({"limit_high": 50.0, "upper": 39.8}, {}),
        "safety.predicted_margin_pct_v1": ({"predicted_margin": 10.2, "headroom": 37.9}, {}),
        "safety.slope_ratio_v1": ({"long_slope": 0.1202, "safety_slope": 0.1805}, {}),
        "mahalanobis.d2_v1": ({"n": 60.0, "p": 2.0}, {}),
        "risk.anomaly_v1": ({"abs_z": 7.5}, {"z_low": 3.0, "z_high": 6.0}),
        "risk.drift_v1": ({"slope_ratio": 0.666}, {"slope_ref": 2.0}),
        "risk.margin_v1": ({"margin_pct": 0.269}, {}),
        "risk.quality_v1": ({"data_quality_score": 0.9}, {}),
        "risk.credit_v1": ({"attribution": "SOCKET"}, {"zone_consistent": "no"}),
        "risk.total_v1": (
            {"anomaly": 1.0, "drift": 0.333, "margin": 0.731, "quality": 0.1, "credit": 0.0},
            {"w_a": 0.30, "w_b": 0.30, "w_m": 0.20, "w_q": 0.10, "w_c": 0.10},
        ),
        "lot.pda_pct_v1": ({"n_reject": 2.0, "n_tested": 40.0}, {"percent_scale": 100.0}),
        "lot.pda_pct_ew_v1": ({"n_reject_ew": 4.0, "n_tested": 40.0}, {"percent_scale": 100.0}),
    }
    return table[formula_id]


def _fixture_unit(formula_id: str) -> tuple[str, str | None]:
    """(unit, source_unit) per entry for the wrap test."""
    if formula_id in (
        "slope.early_v1",
        "slope.long_v1",
        "safety.safety_slope_v1",
        "safety.safety_slope_delta_v1",
    ):
        return "uA/h", None
    if formula_id in (
        "mahalanobis.d2_v1",
        "safety.slope_ratio_v1",
        "safety.predicted_margin_pct_v1",
        "shape.phi_168_v1",
    ):
        return "ratio", None
    if formula_id == "dpat.z_v1":
        return "sigma", None
    if formula_id in (
        "risk.anomaly_v1",
        "risk.drift_v1",
        "risk.margin_v1",
        "risk.quality_v1",
        "risk.credit_v1",
        "risk.total_v1",
    ):
        return "index", None
    if formula_id in ("lot.pda_pct_v1", "lot.pda_pct_ew_v1"):
        return "percent", None
    if formula_id in (
        "raw.measurement",
        "robust.median_v1",
        "robust.q1_v1",
        "robust.q3_v1",
        "conformal.q_hat_v1",
    ):
        return "uA", None
    return "uA", "uA"


@pytest.mark.fast
def test_registry_coverage_both_directions() -> None:
    """TEST-EXPL-002: emitted ids registered; registered ids wrappable."""
    from backend.core.attribution import AttributionVerdict
    from backend.core.risk import compute_risk
    from backend.core.safety import evaluate_safety

    # Direction 1: every formula_id a core result carries is registered.
    safety = evaluate_safety(12.1, 39.8, 32.3, 18.7, 50.0)
    res = compute_risk(7.5, safety, AttributionVerdict.PART, 0.9)
    for comp in res.components:
        assert comp.formula_id in FORMULAS

    # Direction 2: every registered id wraps through the verified builder.
    wrapped_ids: list[str] = []
    for formula_id, spec in FORMULAS.items():
        inputs, params = _fixture_operands(formula_id)
        if spec.derivation == "expression":
            merged = {**inputs, **params}
            numeric = {k: v for k, v in merged.items() if isinstance(v, (int, float))}
            value = float(spec.fn(**numeric))
        else:
            value = 1.0
            if formula_id == "risk.credit_v1":
                value = 1.0
        unit, source = _fixture_unit(formula_id)
        traced = _wrap_verified(value, formula_id, inputs, params, unit, source, HASH, 3)
        assert traced.formula_id == formula_id
        wrapped_ids.append(formula_id)
    assert set(wrapped_ids) == set(FORMULAS)


@pytest.mark.fast
def test_registered_fn_matches_expression_and_rederives() -> None:
    """TEST-EXPL-007: get_formula resolves; fn == expression; rate measured."""
    spec = get_formula("dpat.limit_high_v1")
    assert spec.formula_id == "dpat.limit_high_v1"
    with pytest.raises(FormulaNotFoundError):
        get_formula("no.such_formula")

    # Differential: fn and the restricted evaluator agree on every entry.
    for formula_id, entry in FORMULAS.items():
        if entry.derivation != "expression":
            continue
        inputs, params = _fixture_operands(formula_id)
        merged = {**inputs, **params}
        assert set(merged) == set(entry.operands) | set(entry.parameters)
        assert float(entry.fn(**merged)) == pytest.approx(
            evaluate_expression(entry.expression, merged), abs=1e-9
        )

    # Procedural roots execute their authoritative callables (never stubs).
    assert get_formula("robust.median_v1").fn([1.0, 2.0, 3.0]) == pytest.approx(2.0)
    assert get_formula("robust.q1_v1").fn([1.0, 2.0, 3.0, 4.0]) is not None
    assert get_formula("shape.phi_168_v1").fn(
        [10.0, 10.0, 10.0], [12.0, 14.0, 16.0], [14.0, 20.0, 28.0]
    ) == pytest.approx(2.5)
    assert get_formula("conformal.q_hat_v1").fn([1.0, 2.0, 3.0, 4.0], 0.5) == pytest.approx(3.0)
    spread_cohort = np.random.default_rng(313).normal(size=(12, 2))
    assert get_formula("mahalanobis.d2_v1").fn(spread_cohort, [3.0, 3.0]) is not None
    assert get_formula("risk.credit_v1").fn("SOCKET", "no") == pytest.approx(1.0)
    assert get_formula("risk.credit_v1").fn("PART", "no") == pytest.approx(0.0)
    with pytest.raises(ValueError):
        get_formula("risk.credit_v1").fn("NOZZLE", "no")

    # Measured: a fully traced fixture payload re-derives at 1.0, honestly.
    payload = []
    for formula_id, entry in FORMULAS.items():
        if entry.derivation != "expression":
            continue
        inputs, params = _fixture_operands(formula_id)
        merged = {**inputs, **params}
        value = float(entry.fn(**merged))
        unit, source = _fixture_unit(formula_id)
        payload.append(_wrap_verified(value, formula_id, inputs, params, unit, source, HASH, 3))
    report = rederivation_rate(payload)
    assert report.failures == ()
    assert report.rate == pytest.approx(1.0)
    assert report.n_procedural == 0

    # Fabrication is never papered over: a hand-built value with the right
    # formula but the wrong number fails rederivation loudly.
    honest = payload[0]
    forged = TracedValue(
        value=honest.value + 1.0,
        unit=honest.unit,
        formula_id=honest.formula_id,
        inputs=dict(honest.inputs),
        parameters=dict(honest.parameters),
        dataset_hash=honest.dataset_hash,
        display_precision=honest.display_precision,
        model_version=honest.model_version,
    )
    forged_report = rederivation_rate([forged])
    assert forged_report.rate == pytest.approx(0.0)
    assert len(forged_report.failures) == 1


@pytest.mark.fast
def test_evaluator_rejects_non_arithmetic() -> None:
    """The restricted evaluator refuses code, unknown names, and bad values."""
    assert evaluate_expression(
        "median + k * robust_sigma", {"median": 10.0, "k": 6.0, "robust_sigma": 2.0}
    ) == pytest.approx(22.0)
    with pytest.raises(ValueError):
        evaluate_expression("__import__('os').system('x')", {})
    with pytest.raises(ValueError):
        evaluate_expression("median + unknown", {"median": 1.0})
    with pytest.raises(ValueError):
        evaluate_expression("median / 0", {"median": 1.0})
    with pytest.raises(ValueError):
        evaluate_expression("", {"median": 1.0})
    with pytest.raises(ValueError):
        evaluate_expression("median + k", {"median": 1.0, "k": float("nan")})
