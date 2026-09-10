"""Lot distribution and system posture views (Phase 5, T-504).

- Distribution: per-parameter histograms with cohort-level DPAT limits
  and per-member positions for the S2 Lot Explorer. Binning is display
  aggregation (fixed 30-bin partition of the observed range); every
  decision number (limits, median, sigma) comes from the authoritative
  ``dpat_limits`` call, and per-member z values evaluate the registry's
  own ``dpat.z_v1`` callable (D-017: one implementation, called — never
  re-implemented). ``cohort_mode`` names the non-LOO display basis
  (API_CONTRACT section 6, LK-5).
- Posture: the operator-facing risk posture (alpha, margin, k, PDA,
  weights) with model versions and ladder capacity. Reads profile and
  calibration stores; computes nothing.
"""

from __future__ import annotations

import math
from typing import Any, Final

import numpy as np

from backend.app.errors import ApiError, ErrorCode
from backend.core.dpat import dpat_limits
from backend.core.formulas import FORMULAS, get_formula
from backend.core.traced import trace
from backend.services.investigation import DISPLAY_UNIT, PARAMETERS

_N_BINS: Final[int] = 30
_PRECISION_BY_UNIT: Final[dict[str, int]] = {"uA": 2, "ns": 2}


def _dump_traced(
    value: float | None,
    unit: str,
    formula_id: str,
    inputs: dict[str, Any],
    parameters: dict[str, Any],
    dataset_hash: str,
) -> dict[str, Any] | None:
    clean_inputs: dict[str, float | str] = {}
    for key, item in inputs.items():
        if item is None or isinstance(item, bool):
            return None
        if isinstance(item, float) and not math.isfinite(item):
            return None
        clean_inputs[key] = item
    clean_params: dict[str, float | str] = {}
    for key, item in parameters.items():
        if item is None or isinstance(item, bool):
            return None
        if isinstance(item, float) and not math.isfinite(item):
            return None
        clean_params[key] = item
    if value is None or not math.isfinite(value):
        return None
    spec = get_formula(formula_id)
    traced = trace(
        value,
        unit,
        formula_id,
        clean_inputs,
        clean_params,
        dataset_hash,
        _PRECISION_BY_UNIT.get(unit, 2),
    )
    return {
        "value": traced.value,
        "unit": traced.unit,
        "formula_id": traced.formula_id,
        "expression": spec.expression,
        "inputs": dict(traced.inputs),
        "parameters": dict(traced.parameters),
        "model_version": traced.model_version,
        "dataset_hash": traced.dataset_hash,
        "display_precision": traced.display_precision,
    }


def lot_distribution(state: Any, lot_id: str) -> dict[str, Any]:
    """Build the S2 distribution payload for one lot."""
    dataset_hash = state.active_dataset_hash
    if dataset_hash is None:
        raise ApiError(
            ErrorCode.UNKNOWN_LOT,
            "No dataset ingested yet.",
            [{"remediation": "POST /api/v1/datasets with a screening CSV or Parquet file"}],
        )
    lot_row = state.store.fetchone(
        "SELECT component_type FROM lots WHERE lot_id = ? AND dataset_hash = ?",
        [lot_id, dataset_hash],
    )
    if lot_row is None:
        raise ApiError(
            ErrorCode.UNKNOWN_LOT,
            f"Unknown lot {lot_id!r} in this dataset.",
            [{"lot_id": lot_id}],
        )
    component_type = str(lot_row[0])
    profile = state.active_profile()
    z_fn = FORMULAS["dpat.z_v1"].fn
    parameters = []
    for parameter in PARAMETERS:
        limit = profile.limits[parameter]
        rows = state.store.fetchall(
            "SELECT component_id, value FROM measurements WHERE lot_id = ?"
            " AND component_type = ? AND parameter = ? AND elapsed_hours = 24"
            " AND status = 'OK' AND dataset_hash = ? ORDER BY component_id ASC",
            [lot_id, component_type, parameter, dataset_hash],
        )
        values = np.array([float(row[1]) for row in rows], dtype=np.float64)
        result = dpat_limits(values, None, profile.k)
        stats = result.stats
        median = result.median
        sigma = result.robust_sigma
        display = DISPLAY_UNIT.get(str(limit.unit))
        unit = display[0] if display else str(limit.unit)
        factor = display[1] if display else 1.0
        traced = display is not None
        dataset_key = str(dataset_hash)

        def conv(value: Any, _factor: float = factor) -> float | None:
            finite = (
                float(value)
                if isinstance(value, (int, float)) and math.isfinite(float(value))
                else None
            )
            return finite * _factor if finite is not None else None

        median_tv: dict[str, Any] | None = None
        sigma_tv: dict[str, Any] | None = None
        limit_low_tv: dict[str, Any] | None = None
        limit_high_tv: dict[str, Any] | None = None
        if traced:
            median_tv = _dump_traced(
                conv(median), unit, "robust.median_v1", {"n": len(values)}, {}, dataset_key
            )
            if stats is not None and str(result.estimator) == "mad":
                from backend.core.constants import MAD_SCALE_FACTOR

                sigma_tv = _dump_traced(
                    conv(sigma),
                    unit,
                    "robust.sigma_mad_v1",
                    {"mad": conv(stats.mad)},
                    {"mad_scale": MAD_SCALE_FACTOR, "c_n": float(stats.c_n)},
                    dataset_key,
                )
            elif stats is not None:
                from backend.core.constants import DPAT_IQR_DIVISOR

                sigma_tv = _dump_traced(
                    conv(sigma),
                    unit,
                    "robust.sigma_iqr_v1",
                    {"iqr": conv(stats.iqr)},
                    {"divisor": DPAT_IQR_DIVISOR},
                    dataset_key,
                )
            if conv(median) is not None and conv(sigma):
                limit_low_tv = _dump_traced(
                    conv(result.limit_low),
                    unit,
                    "dpat.limit_low_v1",
                    {"median": conv(median), "k": profile.k, "robust_sigma": conv(sigma)},
                    {},
                    dataset_key,
                )
                limit_high_tv = _dump_traced(
                    conv(result.limit_high),
                    unit,
                    "dpat.limit_high_v1",
                    {"median": conv(median), "k": profile.k, "robust_sigma": conv(sigma)},
                    {},
                    dataset_key,
                )
        members = []
        if median is not None and sigma:
            for component_id, value in rows:
                member_z = float(z_fn(x=float(value), median=median, robust_sigma=sigma))
                members.append(
                    {
                        "component_id": str(component_id),
                        "value": float(value),
                        "z": member_z,
                        "flagged": bool(
                            result.limit_high is not None and float(value) > result.limit_high
                        )
                        or bool(result.limit_low is not None and float(value) < result.limit_low),
                    }
                )
        bins: list[dict[str, float]] = []
        if len(values):
            lo, hi = float(values.min()), float(values.max())
            edges = np.linspace(lo, hi, _N_BINS + 1) if hi > lo else np.array([lo - 0.5, hi + 0.5])
            counts, edges = np.histogram(values, bins=edges)
            bins = [
                {
                    "lo": float(edges[index]),
                    "hi": float(edges[index + 1]),
                    "count": int(counts[index]),
                }
                for index in range(len(counts))
            ]
        parameters.append(
            {
                "parameter": parameter,
                "unit": unit,
                "native_unit": str(limit.unit),
                "fully_traced": traced,
                "n": len(values),
                "cohort_mode": "cohort",
                "median": median_tv if traced else median,
                "robust_sigma": sigma_tv if traced else sigma,
                "estimator": str(result.estimator),
                "limit_low": limit_low_tv if traced else result.limit_low,
                "limit_high": limit_high_tv if traced else result.limit_high,
                "absolute_limit_low": limit.low,
                "absolute_limit_high": limit.high,
                "bins": bins,
                "members": members,
                "refusal": (
                    str(result.verdict)
                    if result.verdict in ("INSUFFICIENT_COHORT", "NO_VARIATION")
                    else None
                ),
            }
        )
    from backend.services.provenance import appendix_block

    return {
        "lot_id": lot_id,
        "component_type": component_type,
        "parameters": parameters,
        "provenance": appendix_block(
            state, {"dpat.limit_high_v1", "dpat.limit_low_v1", "dpat.z_v1"}
        ),
    }


def system_posture(state: Any) -> dict[str, Any]:
    """Mission Risk Posture: the operator-facing risk configuration."""
    from backend.app.errors import ApiError
    from backend.services.calibration import ensure_calibration

    profile = state.active_profile()
    try:
        calibration = ensure_calibration(state)
    except ApiError:
        calibration = None
    groups = []
    if calibration is not None:
        for key in sorted(calibration.groups):
            group = calibration.groups[key]
            n_cal = len(group.residuals_l0)
            groups.append(
                {
                    "group": f"{key[0]}/{key[1]}",
                    "n_cal": n_cal,
                    "attainable_alpha": 1.0 / (n_cal + 1) if n_cal else None,
                }
            )
    return {
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "mission_risk_posture": {
            "alpha": profile.alpha,
            "alpha_note": "Mission Risk Posture: bounds the prioritised error rate;"
            " smaller alpha widens bounds and raises false positives.",
            "margin_fraction": profile.margin_fraction,
            "k": profile.k,
            "pda_limit_pct": profile.pda_limit_pct,
            "horizon_hours": profile.horizon_hours,
        },
        "risk_weights": {
            "w_anomaly": profile.risk_weights.w_anomaly,
            "w_drift": profile.risk_weights.w_drift,
            "w_margin": profile.risk_weights.w_margin,
            "w_quality": profile.risk_weights.w_quality,
            "w_credit": profile.risk_weights.w_credit,
            "note": "Policy inputs (assumed); weights cannot move a part across a band.",
        },
        "model_versions": dict(calibration.model_versions) if calibration else {},
        "calibration_groups": groups,
        "dataset_hash": state.active_dataset_hash,
        "data_provenance": "SYNTHETIC",
    }
