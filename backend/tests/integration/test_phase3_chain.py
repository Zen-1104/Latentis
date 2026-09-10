"""Phase 3 chain integration (T-316, FR-401..FR-403).

Exercises the full provenance spine on one deterministic synthetic part:
robust → DPAT → Mahalanobis → attribution → shape → forecast → conformal →
guard → safety → risk → recommendation, wrapping every stage output in a
verified TracedValue immediately after its computation, rendering the
narrative from those values, and measuring the re-derivation rate.

The chain reuses authoritative upstream values throughout (no stage
recomputes another's science), preserves refusals, bands, sum_check, and
registry linkage end to end, and replays byte-identically (INV-8).
"""

from __future__ import annotations

import math
from typing import TypedDict

import numpy as np
import pytest

from backend.core.attribution import attribute
from backend.core.conformal import ConformalResult, conformal_upper
from backend.core.dpat import dpat_limits
from backend.core.explain import ExplanationResult, explain
from backend.core.forecast import forecast_v168
from backend.core.formulas import FORMULAS, RederivationReport, rederivation_rate
from backend.core.guard import GuardResult, check_exchangeability
from backend.core.multivariate import mahalanobis
from backend.core.recommend import Recommendation, RecommendationResult, recommend
from backend.core.risk import LotRollup, RiskResult, compute_risk, roll_up_lot
from backend.core.robust import robust_stats
from backend.core.safety import SafetyBand, SafetyResult, evaluate_safety
from backend.core.shape import estimate_phi
from backend.core.traced import TracedValue, _wrap_verified

HASH = "synthetic-test-chain"
PREC = 4
LOT_SEED = 5011
CAL_SEED = 6011


class ChainResult(TypedDict):
    """One built chain: records, values, narrative, and measurement."""

    wall: list[TracedValue]
    report: RederivationReport
    narration: ExplanationResult
    safety: SafetyResult
    risk: RiskResult
    rec: RecommendationResult
    guard: GuardResult
    bound: ConformalResult
    rollup: LotRollup
    band: SafetyBand


def _build_chain() -> ChainResult:
    """Run the full T-301→T-312 chain once, returning records and values."""
    lot = np.random.default_rng(LOT_SEED).normal(loc=10.0, scale=1.0, size=60)
    part_value = 18.0

    stats = robust_stats(lot)
    dpat = dpat_limits(lot, part_value=part_value, k=6.0)
    assert dpat.median is not None and dpat.robust_sigma is not None and dpat.z is not None
    assert dpat.limit_high is not None and dpat.limit_low is not None
    z_val = float(dpat.z)

    pair_cohort = np.column_stack(
        [lot, np.random.default_rng(LOT_SEED + 1).normal(loc=5.0, scale=0.5, size=60)]
    )
    joint = mahalanobis(pair_cohort, np.array([part_value, 5.1]))
    assert joint.d2 is not None

    socket = np.random.default_rng(LOT_SEED + 2).normal(loc=10.1, scale=0.5, size=12)
    zone = np.random.default_rng(LOT_SEED + 3).normal(loc=9.9, scale=1.0, size=25)
    tester = np.random.default_rng(LOT_SEED + 4).normal(loc=10.0, scale=1.0, size=30)
    attr = attribute(
        part_value=part_value,
        lot_cohort=lot,
        socket_cohort=socket,
        zone_cohort=zone,
        tester_cohort=tester,
        mahalanobis_result=joint,
    )

    train_v0 = np.full(8, 10.0)
    train_amp = np.array([2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])
    shape = estimate_phi(train_v0, train_v0 + train_amp, train_v0 + train_amp * 3.0)
    assert shape.phi_168 is not None
    phi_val = float(shape.phi_168)

    forecast = forecast_v168(12.1, 18.7, phi_val)
    assert forecast.point is not None and forecast.baseline_linear is not None
    assert forecast.shape_point is not None and forecast.amplitude is not None
    point_val = float(forecast.point)

    calib_residuals = np.random.default_rng(CAL_SEED).normal(loc=0.0, scale=2.0, size=150)
    bound = conformal_upper(point_val, [calib_residuals], alpha=0.10)
    assert bound.upper is not None and bound.q_hat is not None and bound.k is not None
    upper_val = float(bound.upper)

    rng_cal = np.random.default_rng(CAL_SEED + 1)
    guard = check_exchangeability(
        lot_v0=lot,
        lot_delta24=np.random.default_rng(LOT_SEED + 5).normal(loc=2.0, scale=0.5, size=60),
        calib_v0=rng_cal.normal(loc=10.0, scale=1.0, size=1500),
        calib_delta24=rng_cal.normal(loc=2.0, scale=0.5, size=1500),
        calib_lot_medians=rng_cal.normal(loc=10.0, scale=0.2, size=30),
        lot_temperatures=np.full(60, 125.0),
        calib_temperatures=np.full(1500, 125.0),
        tester_id="T-01",
        calib_tester_ids=["T-01"],
        group_key="CMOS/iddq",
        calib_group_keys=["CMOS/iddq"],
    )

    safety = evaluate_safety(12.1, upper_val, point_val, 18.7, 50.0)
    assert safety.band is not None and safety.slope_ratio is not None
    assert safety.predicted_margin_pct is not None and safety.predicted_margin is not None
    assert safety.usable_margin is not None and safety.safety_slope is not None
    assert safety.predicted_long_slope is not None and safety.observed_early_slope is not None
    band = safety.band

    risk = compute_risk(z_val, safety, attr.verdict, 0.95)
    assert risk.refusal_code is None

    rec = recommend(band, False, z_val, attr.verdict, safety.predicted_margin_pct)
    rollup = roll_up_lot([band] + ["SAFE"] * 39, [False] * 40)

    wall: list[TracedValue] = []
    unit = "uA"
    wall.append(
        _wrap_verified(
            float(stats.median), "robust.median_v1", {"n": 60.0}, {}, unit, None, HASH, PREC
        )
    )
    wall.append(
        _wrap_verified(float(stats.q1), "robust.q1_v1", {"n": 60.0}, {}, unit, None, HASH, PREC)
    )
    wall.append(
        _wrap_verified(float(stats.q3), "robust.q3_v1", {"n": 60.0}, {}, unit, None, HASH, PREC)
    )
    wall.append(
        _wrap_verified(
            float(stats.iqr),
            "robust.iqr_v1",
            {"q3": float(stats.q3), "q1": float(stats.q1)},
            {},
            unit,
            unit,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(stats.robust_sigma),
            "robust.sigma_iqr_v1",
            {"iqr": float(stats.iqr)},
            {"divisor": 1.35},
            unit,
            unit,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(dpat.limit_high),
            "dpat.limit_high_v1",
            {"median": float(dpat.median), "k": 6.0, "robust_sigma": float(dpat.robust_sigma)},
            {},
            unit,
            unit,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(dpat.limit_low),
            "dpat.limit_low_v1",
            {"median": float(dpat.median), "k": 6.0, "robust_sigma": float(dpat.robust_sigma)},
            {},
            unit,
            unit,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            z_val,
            "dpat.z_v1",
            {
                "x": part_value,
                "median": float(dpat.median),
                "robust_sigma": float(dpat.robust_sigma),
            },
            {},
            "sigma",
            None,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(joint.d2),
            "mahalanobis.d2_v1",
            {"n": 60.0, "p": 2.0},
            {},
            "ratio",
            None,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(phi_val, "shape.phi_168_v1", {"n_used": 8.0}, {}, "ratio", None, HASH, PREC)
    )
    wall.append(
        _wrap_verified(
            float(forecast.shape_point),
            "forecast.shape_point_v1",
            {"v0": 12.1, "amplitude": float(forecast.amplitude), "phi_168": phi_val},
            {},
            unit,
            unit,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(forecast.baseline_linear),
            "forecast.baseline_linear_v1",
            {"v0": 12.1, "amplitude": float(forecast.amplitude)},
            {"linear_phi": 7.0},
            unit,
            unit,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            point_val,
            "forecast.point_v1",
            {"shape_point": float(forecast.shape_point), "residual_correction": 0.0},
            {},
            unit,
            unit,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(bound.q_hat),
            "conformal.q_hat_v1",
            {"n_cal": 150.0, "k": float(bound.k), "alpha": 0.10},
            {},
            unit,
            None,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            upper_val,
            "conformal.upper_v1",
            {"point": point_val, "q_hat": float(bound.q_hat)},
            {},
            unit,
            unit,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(safety.predicted_long_slope),
            "slope.long_v1",
            {"point": point_val, "v0": 12.1},
            {"horizon": 168.0},
            "uA/h",
            None,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(safety.observed_early_slope),
            "slope.early_v1",
            {"v24": 18.7, "v0": 12.1},
            {"t_early": 24.0},
            "uA/h",
            None,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(safety.usable_margin),
            "safety.usable_margin_v1",
            {"limit_high": 50.0, "v0": 12.1},
            {"margin_fraction": 0.20},
            unit,
            unit,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(safety.safety_slope),
            "safety.safety_slope_v1",
            {"usable_margin": float(safety.usable_margin)},
            {"horizon": 168.0},
            "uA/h",
            None,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(safety.predicted_margin),
            "safety.predicted_margin_v1",
            {"limit_high": 50.0, "upper": upper_val},
            {},
            unit,
            unit,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(safety.predicted_margin_pct),
            "safety.predicted_margin_pct_v1",
            {"predicted_margin": float(safety.predicted_margin), "headroom": 37.9},
            {},
            "ratio",
            None,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(safety.slope_ratio),
            "safety.slope_ratio_v1",
            {
                "long_slope": float(safety.predicted_long_slope),
                "safety_slope": float(safety.safety_slope),
            },
            {},
            "ratio",
            None,
            HASH,
            PREC,
        )
    )
    for comp in risk.components:
        if comp.name == "anomaly":
            wall.append(
                _wrap_verified(
                    comp.raw,
                    comp.formula_id,
                    {"abs_z": abs(z_val)},
                    {"z_low": 3.0, "z_high": 6.0},
                    "index",
                    None,
                    HASH,
                    PREC,
                )
            )
        elif comp.name == "drift":
            wall.append(
                _wrap_verified(
                    comp.raw,
                    comp.formula_id,
                    {"slope_ratio": float(safety.slope_ratio)},
                    {"slope_ref": 2.0},
                    "index",
                    None,
                    HASH,
                    PREC,
                )
            )
        elif comp.name == "margin":
            wall.append(
                _wrap_verified(
                    comp.raw,
                    comp.formula_id,
                    {"margin_pct": float(safety.predicted_margin_pct)},
                    {},
                    "index",
                    None,
                    HASH,
                    PREC,
                )
            )
        elif comp.name == "quality":
            wall.append(
                _wrap_verified(
                    comp.raw,
                    comp.formula_id,
                    {"data_quality_score": 0.95},
                    {},
                    "index",
                    None,
                    HASH,
                    PREC,
                )
            )
        else:
            wall.append(
                _wrap_verified(
                    comp.raw,
                    comp.formula_id,
                    {"attribution": attr.verdict.value},
                    {"zone_consistent": "no"},
                    "index",
                    None,
                    HASH,
                    PREC,
                )
            )
    wall.append(
        _wrap_verified(
            risk.risk_index,
            "risk.total_v1",
            {
                c.name if c.name != "attribution_credit" else "credit": c.raw
                for c in risk.components
            },
            {"w_a": 0.30, "w_b": 0.30, "w_m": 0.20, "w_q": 0.10, "w_c": 0.10},
            "index",
            None,
            HASH,
            PREC,
        )
    )
    assert rollup.pda_pct is not None and rollup.pda_pct_including_early_warning is not None
    wall.append(
        _wrap_verified(
            float(rollup.pda_pct),
            "lot.pda_pct_v1",
            {"n_reject": float(rollup.n_reject), "n_tested": float(rollup.n_tested)},
            {"percent_scale": 100.0},
            "percent",
            None,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            float(rollup.pda_pct_including_early_warning),
            "lot.pda_pct_ew_v1",
            {
                "n_reject_ew": float(rollup.n_reject + rollup.n_early_warning),
                "n_tested": float(rollup.n_tested),
            },
            {"percent_scale": 100.0},
            "percent",
            None,
            HASH,
            PREC,
        )
    )
    wall.append(
        _wrap_verified(
            18.7,
            "raw.measurement",
            {"measured_value": 18.7, "source_row": "chain:v24"},
            {},
            unit,
            None,
            HASH,
            PREC,
        )
    )

    by_id = {tv.formula_id: tv for tv in wall}
    narration = explain(
        "drift",
        {
            "forecast_point": by_id["forecast.shape_point_v1"],
            "bound_upper": by_id["conformal.upper_v1"],
            "baseline": by_id["forecast.baseline_linear_v1"],
            "long_slope": by_id["slope.long_v1"],
            "safety_slope": by_id["safety.safety_slope_v1"],
            "slope_ratio": by_id["safety.slope_ratio_v1"],
        },
        {
            "horizon_h": "168",
            "unit": unit,
            "alpha": "0.10",
            "slope_unit": "uA/h",
            "band": str(band),
        },
        mondrian_level=bound.mondrian_level,
        guarantee_status=guard.guarantee_status,
        censored=forecast.censored,
    )
    report = rederivation_rate(wall)
    return ChainResult(
        wall=wall,
        report=report,
        narration=narration,
        safety=safety,
        risk=risk,
        rec=rec,
        guard=guard,
        bound=bound,
        rollup=rollup,
        band=band,
    )


def _assert_chain_invariants(chain: ChainResult) -> None:
    """Every spine invariant, asserted on one built chain."""
    assert chain["risk"].band == chain["band"] == chain["safety"].band
    assert chain["risk"].sum_check.abs_diff <= 1e-9
    assert chain["risk"].refusal_code is None
    assert chain["rec"].action == Recommendation.INVESTIGATE
    assert "disagree" in chain["rec"].trigger
    assert chain["guard"].verdict in ("PASS", "WARN")
    assert chain["guard"].guarantee_status in ("VALID", "DEGRADED")
    report = chain["report"]
    assert report.failures == ()
    assert report.rate == 1.0
    assert report.n_procedural >= 1
    assert {tv.formula_id for tv in chain["wall"]} <= set(FORMULAS)
    assert chain["narration"].text is not None
    assert str(chain["band"]) in chain["narration"].text
    if chain["guard"].guarantee_status != "VALID":
        assert "guarantee" in chain["narration"].text
    for tv in chain["wall"]:
        assert math.isfinite(tv.value)
        assert tv.unit != ""


@pytest.mark.integration
def test_phase3_provenance_spine_end_to_end() -> None:
    """T-316: the full chain preserves values, provenance, and decisions."""
    _assert_chain_invariants(_build_chain())


@pytest.mark.integration
def test_phase3_chain_replays_byte_identically() -> None:
    """T-316/INV-8: rebuilding the chain gives identical records and prose."""
    first = _build_chain()
    second = _build_chain()
    assert first["wall"] == second["wall"]
    assert first["narration"] == second["narration"]
    assert first["report"] == second["report"]
    _assert_chain_invariants(second)
