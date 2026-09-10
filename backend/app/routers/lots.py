"""Lot routes: directory, statistics, analysis runs, disposition (T-503).

Implements API_CONTRACT.md section 6. Lot statistics honour the
cohort-mode distinction (API_CONTRACT section 6, LK-5): cohort-level by
default, leave-one-out per part under ``?for_component=``, and the
response names which one it is. Lot disposition rolls up through the
PDA rule (RISK_SCORING_SPEC section 5) — never an average of scores.
"""

from __future__ import annotations

import json as _json
import math
import uuid
from typing import Any

from fastapi import APIRouter, Request

from backend.app.errors import ApiError, ErrorCode
from backend.app.runtime import build_meta, utc_now_z
from backend.app.schemas import Envelope
from backend.app.schemas_phase5 import LotSummary
from backend.core.constants import DPAT_IQR_DIVISOR, MAD_SCALE_FACTOR, PERCENT_SCALE
from backend.core.dpat import dpat_limits
from backend.core.formulas import get_formula
from backend.core.risk import roll_up_lot
from backend.core.traced import trace
from backend.services.investigation import DISPLAY_UNIT, PARAMETERS, build_investigator

_PRECISION_BY_UNIT = {"uA": 2, "ns": 2, "sigma": 2, "ratio": 3, "index": 3, "percent": 2}


def _display_of(native_unit: str) -> tuple[str, float] | None:
    mapping = DISPLAY_UNIT.get(native_unit)
    return (mapping[0], mapping[1]) if mapping else None


def _stat_tv(
    value: float | None,
    unit: str,
    formula_id: str,
    inputs: dict[str, Any],
    parameters: dict[str, Any],
    dataset_hash: str,
) -> dict[str, Any] | None:
    """Wrap a cohort statistic iff every operand is real (else None)."""
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


router = APIRouter(tags=["lots"])


def _context(request: Request) -> tuple[str, int, Any]:
    return (
        getattr(request.state, "request_id", "unknown"),
        getattr(request.state, "start_ns", 0),
        request.app.state.app_state,
    )


def _meta(request_id: str, start_ns: int, state: Any) -> Any:
    calibration = state.calibration
    model_versions = dict(calibration.model_versions) if calibration else {}
    profile = state.active_profile()
    return build_meta(
        request_id,
        start_ns,
        dataset_hash=state.active_dataset_hash,
        profile_id=profile.profile_id,
        profile_version=profile.version,
        model_versions=model_versions,
    )


def _require_dataset(state: Any) -> str:
    dataset_hash = state.active_dataset_hash
    if dataset_hash is None:
        raise ApiError(
            ErrorCode.UNKNOWN_LOT,
            "No dataset ingested yet; ingest one before listing lots.",
            [{"remediation": "POST /api/v1/datasets with a screening CSV or Parquet file"}],
        )
    return str(dataset_hash)


@router.get("/lots")
def list_lots(request: Request) -> Envelope[list[LotSummary]]:
    """Every lot with part counts and provenance."""
    request_id, start_ns, state = _context(request)
    dataset_hash = _require_dataset(state)
    rows = state.store.fetchall(
        "SELECT lot_id, component_type, n_parts, data_provenance FROM lots"
        " WHERE dataset_hash = ? ORDER BY lot_id ASC",
        [dataset_hash],
    )
    summaries = [
        LotSummary(
            lot_id=str(row[0]),
            component_type=str(row[1]),
            n_parts=int(row[2]),
            data_provenance=str(row[3]),
        )
        for row in rows
    ]
    return Envelope[list[LotSummary]](data=summaries, meta=_meta(request_id, start_ns, state))


@router.get("/lots/{lot_id}/statistics")
def lot_statistics(
    request: Request, lot_id: str, for_component: str | None = None
) -> Envelope[dict[str, Any]]:
    """Per-parameter DPAT limits + robust statistics with the guard state."""
    request_id, start_ns, state = _context(request)
    dataset_hash = _require_dataset(state)
    profile = state.active_profile()
    lot_row = state.store.fetchone(
        "SELECT lot_id FROM lots WHERE lot_id = ? AND dataset_hash = ?",
        [lot_id, dataset_hash],
    )
    if lot_row is None:
        raise ApiError(
            ErrorCode.UNKNOWN_LOT,
            f"Unknown lot {lot_id!r} in this dataset.",
            [{"lot_id": lot_id}],
        )
    if for_component is not None:
        comp_row = state.store.fetchone(
            "SELECT component_id, lot_id, component_type FROM components"
            " WHERE component_id = ? AND dataset_hash = ?",
            [for_component, dataset_hash],
        )
        if comp_row is None or str(comp_row[1]) != lot_id:
            raise ApiError(
                ErrorCode.UNKNOWN_COMPONENT,
                f"Component {for_component!r} is not in lot {lot_id!r}.",
                [{"component_id": for_component, "lot_id": lot_id}],
            )
        component_type = str(comp_row[2])
        cohort_mode = "leave-one-out"
    else:
        type_row = state.store.fetchone(
            "SELECT component_type FROM lots WHERE lot_id = ? AND dataset_hash = ?",
            [lot_id, dataset_hash],
        )
        component_type = str(type_row[0]) if type_row else ""
        cohort_mode = "cohort"
    entries = []
    for parameter in PARAMETERS:
        limit = profile.limits[parameter]
        rows = state.store.fetchall(
            "SELECT value, component_id FROM measurements WHERE lot_id = ?"
            " AND component_type = ? AND parameter = ? AND elapsed_hours = 24"
            " AND status = 'OK' AND dataset_hash = ?",
            [lot_id, component_type, parameter, dataset_hash],
        )
        values = [float(row[0]) for row in rows]
        if for_component is not None:
            values = [float(row[0]) for row in rows if str(row[1]) != for_component]
        result = dpat_limits(values, None, profile.k)
        stats = result.stats
        native_unit = str(limit.unit)
        display = _display_of(native_unit)
        unit = display[0] if display else native_unit
        factor = display[1] if display else 1.0

        def conv(value: Any, _factor: float = factor) -> float | None:
            finite = _finite_or_none(value)
            if finite is None:
                return None
            return finite * _factor

        traced = display is not None
        entry: dict[str, Any] = {
            "parameter": parameter,
            "unit": unit,
            "native_unit": native_unit,
            "fully_traced": traced,
            "n": len(values),
            "cohort_mode": cohort_mode,
            "median": (
                _stat_tv(
                    conv(result.median),
                    unit,
                    "robust.median_v1",
                    {"n": len(values)},
                    {},
                    dataset_hash,
                )
                if traced
                else None
            ),
            "q1": (
                _stat_tv(
                    conv(stats.q1) if stats else None,
                    unit,
                    "robust.q1_v1",
                    {"n": len(values)},
                    {},
                    dataset_hash,
                )
                if traced
                else None
            ),
            "q3": (
                _stat_tv(
                    conv(stats.q3) if stats else None,
                    unit,
                    "robust.q3_v1",
                    {"n": len(values)},
                    {},
                    dataset_hash,
                )
                if traced
                else None
            ),
            "iqr": None,
            "mad": _finite_or_none(stats.mad) if stats else None,
            "robust_sigma": None,
            "estimator": str(result.estimator),
            "limit_low": None,
            "limit_high": None,
            "reduced_power": bool(result.reduced_power),
            "zero_iqr": bool(result.zero_iqr),
            "refusal": (
                str(result.verdict)
                if result.verdict in ("INSUFFICIENT_COHORT", "NO_VARIATION")
                else None
            ),
            "warning": result.warning,
            "absolute_limit_low": limit.low,
            "absolute_limit_high": limit.high,
        }
        if stats is not None and _finite_or_none(stats.q3) is not None:
            entry["iqr"] = (
                _stat_tv(
                    conv(stats.iqr),
                    unit,
                    "robust.iqr_v1",
                    {"q3": conv(stats.q3), "q1": conv(stats.q1)},
                    {},
                    dataset_hash,
                )
                if traced
                else None
            )
        if _finite_or_none(result.robust_sigma):
            if str(result.estimator) == "mad" and stats is not None:
                entry["robust_sigma"] = (
                    _stat_tv(
                        conv(result.robust_sigma),
                        unit,
                        "robust.sigma_mad_v1",
                        {"mad": conv(stats.mad)},
                        {"mad_scale": MAD_SCALE_FACTOR, "c_n": _finite_or_none(stats.c_n)},
                        dataset_hash,
                    )
                    if traced
                    else None
                )
            elif stats is not None:
                entry["robust_sigma"] = (
                    _stat_tv(
                        conv(result.robust_sigma),
                        unit,
                        "robust.sigma_iqr_v1",
                        {"iqr": conv(stats.iqr)},
                        {"divisor": DPAT_IQR_DIVISOR},
                        dataset_hash,
                    )
                    if traced
                    else None
                )
        if (
            _finite_or_none(result.limit_low) is not None
            and _finite_or_none(result.median) is not None
        ):
            entry["limit_low"] = (
                _stat_tv(
                    conv(result.limit_low),
                    unit,
                    "dpat.limit_low_v1",
                    {
                        "median": conv(result.median),
                        "k": profile.k,
                        "robust_sigma": conv(result.robust_sigma),
                    },
                    {},
                    dataset_hash,
                )
                if traced
                else None
            )
        if (
            _finite_or_none(result.limit_high) is not None
            and _finite_or_none(result.median) is not None
        ):
            entry["limit_high"] = (
                _stat_tv(
                    conv(result.limit_high),
                    unit,
                    "dpat.limit_high_v1",
                    {
                        "median": conv(result.median),
                        "k": profile.k,
                        "robust_sigma": conv(result.robust_sigma),
                    },
                    {},
                    dataset_hash,
                )
                if traced
                else None
            )
        if not traced:
            # mV/mOhm display basis (D-044): plain values, same numbers.
            entry.update(
                {
                    "median": result.median,
                    "q1": _finite_or_none(stats.q1) if stats else None,
                    "q3": _finite_or_none(stats.q3) if stats else None,
                    "iqr": _finite_or_none(stats.iqr) if stats else None,
                    "robust_sigma": _finite_or_none(result.robust_sigma),
                    "limit_low": _finite_or_none(result.limit_low),
                    "limit_high": _finite_or_none(result.limit_high),
                }
            )
        entries.append(entry)
    return Envelope[dict[str, Any]](
        data={"lot_id": lot_id, "cohort_mode": cohort_mode, "parameters": entries},
        meta=_meta(request_id, start_ns, state),
    )


def _finite_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


@router.post("/lots/{lot_id}/anomaly")
def run_lot_anomaly(request: Request, lot_id: str) -> Envelope[dict[str, Any]]:
    """Run Module A across a lot; persists the run and per-part summaries."""
    request_id, start_ns, state = _context(request)
    investigator = build_investigator(state)
    dataset_hash = _require_dataset(state)
    profile = state.active_profile()
    parts = _lot_parts(state, dataset_hash, lot_id)
    if len(parts) < 3:
        # No lot-relative statistic exists below n = 3 (ANOMALY_SPEC section 9):
        # per-part 200s would all be refusals, so the run itself is a 422.
        raise ApiError(
            ErrorCode.INSUFFICIENT_COHORT,
            f"Lot {lot_id!r} holds {len(parts)} parts; minimum is 3.",
            [{"lot_id": lot_id, "n": len(parts), "n_min": 3}],
        )
    run_id = uuid.uuid4().hex
    created_at = utc_now_z()
    summaries = []
    with state.store.transaction():
        state.store.execute(
            "INSERT INTO analysis_runs (run_id, dataset_hash, lot_id, profile_id,"
            " profile_version, kind, model_versions_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                dataset_hash,
                lot_id,
                profile.profile_id,
                profile.version,
                "anomaly",
                _versions_json(state),
                created_at,
            ],
        )
        for component_id in parts:
            payload = investigator.assemble(component_id)
            for block in payload["parameters"]:
                state.store.execute(
                    "INSERT INTO part_results (run_id, component_id, parameter, result_json)"
                    " VALUES (?, ?, ?, ?)",
                    [run_id, component_id, block["parameter"], _dump(block)],
                )
            worst = payload["worst"]
            summaries.append(
                {
                    "component_id": component_id,
                    "severity": worst["severity"],
                    "band": worst["band"],
                    "recommendation": worst["recommendation"],
                    "worst_parameter": worst["parameter"],
                }
            )
    order = {"ABSOLUTE_FAIL": 4, "SEVERE": 3, "ANOMALOUS": 2, "ELEVATED": 1, "NOMINAL": 0}
    summaries.sort(
        key=lambda item: (-order.get(str(item["severity"]), -1), str(item["component_id"]))
    )
    return Envelope[dict[str, Any]](
        data={"run_id": run_id, "lot_id": lot_id, "n_parts": len(parts), "queue": summaries},
        meta=_meta(request_id, start_ns, state),
    )


@router.post("/lots/{lot_id}/drift")
def run_lot_drift(request: Request, lot_id: str) -> Envelope[dict[str, Any]]:
    """Run Module B across a lot; persists the run and per-part forecasts."""
    request_id, start_ns, state = _context(request)
    investigator = build_investigator(state)
    dataset_hash = _require_dataset(state)
    profile = state.active_profile()
    parts = _lot_parts(state, dataset_hash, lot_id)
    if len(parts) < 3:
        raise ApiError(
            ErrorCode.INSUFFICIENT_COHORT,
            f"Lot {lot_id!r} holds {len(parts)} parts; minimum is 3.",
            [{"lot_id": lot_id, "n": len(parts), "n_min": 3}],
        )
    run_id = uuid.uuid4().hex
    created_at = utc_now_z()
    summaries = []
    with state.store.transaction():
        state.store.execute(
            "INSERT INTO analysis_runs (run_id, dataset_hash, lot_id, profile_id,"
            " profile_version, kind, model_versions_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                dataset_hash,
                lot_id,
                profile.profile_id,
                profile.version,
                "drift",
                _versions_json(state),
                created_at,
            ],
        )
        for component_id in parts:
            payload = investigator.assemble(component_id)
            for block in payload["parameters"]:
                state.store.execute(
                    "INSERT INTO part_results (run_id, component_id, parameter, result_json)"
                    " VALUES (?, ?, ?, ?)",
                    [run_id, component_id, block["parameter"], _dump(block["drift"])],
                )
            worst = payload["worst"]
            summaries.append(
                {
                    "component_id": component_id,
                    "band": worst["band"],
                    "severity": worst["severity"],
                    "recommendation": worst["recommendation"],
                    "worst_parameter": worst["parameter"],
                }
            )
    order = {"REJECT": 3, "EARLY_WARNING": 2, "WATCH": 1, "SAFE": 0}
    summaries.sort(key=lambda item: (-order.get(str(item["band"]), -1), str(item["component_id"])))
    return Envelope[dict[str, Any]](
        data={
            "run_id": run_id,
            "lot_id": lot_id,
            "n_parts": len(parts),
            "queue": summaries,
            "provenance": _run_provenance(state, dataset_hash, profile, parts),
        },
        meta=_meta(request_id, start_ns, state),
    )


@router.get("/lots/{lot_id}/disposition")
def lot_disposition(request: Request, lot_id: str) -> Envelope[dict[str, Any]]:
    """PDA roll-up with both figures (RISK_SCORING_SPEC section 5)."""
    request_id, start_ns, state = _context(request)
    investigator = build_investigator(state)
    dataset_hash = _require_dataset(state)
    profile = state.active_profile()
    parts = _lot_parts(state, dataset_hash, lot_id)
    bands: list[str | None] = []
    absolute_fails: list[bool] = []
    for component_id in parts:
        payload = investigator.assemble(component_id)
        worst = payload["worst"]
        bands.append(worst["band"])
        worst_block = next(
            block for block in payload["parameters"] if block["parameter"] == worst["parameter"]
        )
        absolute_fails.append(worst_block["absolute"].get("verdict") == "FAIL")
    rollup = roll_up_lot(bands, absolute_fails, profile.pda_limit_pct)
    data: dict[str, Any] = {
        "lot_id": lot_id,
        "n_tested": rollup.n_tested,
        "n_reject": rollup.n_reject,
        "n_early_warning": rollup.n_early_warning,
        "n_excluded": rollup.n_excluded,
        "pda_limit_pct": rollup.pda_limit_pct,
        "lot_verdict": str(rollup.lot_verdict) if rollup.lot_verdict is not None else None,
        "refusal_code": rollup.refusal_code,
        "warning": rollup.warning,
    }
    if rollup.pda_pct is not None:
        data["pda_pct"] = _dump_pda(
            rollup.pda_pct, rollup.n_reject, rollup.n_tested, dataset_hash, "lot.pda_pct_v1"
        )
    if rollup.pda_pct_including_early_warning is not None:
        data["pda_pct_including_early_warning"] = _dump_pda(
            rollup.pda_pct_including_early_warning,
            rollup.n_reject + rollup.n_early_warning,
            rollup.n_tested,
            dataset_hash,
            "lot.pda_pct_ew_v1",
        )
    from backend.services.provenance import appendix_block

    data["provenance"] = appendix_block(state, {"lot.pda_pct_v1", "lot.pda_pct_ew_v1"})
    return Envelope[dict[str, Any]](data=data, meta=_meta(request_id, start_ns, state))


def _run_provenance(
    state: Any, dataset_hash: str, profile: Any, parts: list[str]
) -> dict[str, Any]:
    """Union appendix over the run's assembled payloads (exact, from cache)."""
    from backend.services.provenance import appendix_block

    profile_ref = f"{profile.profile_id}@{profile.version}"
    used: set[str] = set()
    cache = state.investigation_cache
    for component_id in parts:
        payload = cache.get(f"{dataset_hash}/{profile_ref}/{component_id}")
        if isinstance(payload, dict):
            provenance = payload.get("provenance") or {}
            for item in provenance.get("formulas_used", []):
                used.add(str(item["formula_id"]))
    return appendix_block(state, used)


def _lot_parts(state: Any, dataset_hash: str, lot_id: str) -> list[str]:
    lot_row = state.store.fetchone(
        "SELECT lot_id FROM lots WHERE lot_id = ? AND dataset_hash = ?",
        [lot_id, dataset_hash],
    )
    if lot_row is None:
        raise ApiError(
            ErrorCode.UNKNOWN_LOT,
            f"Unknown lot {lot_id!r} in this dataset.",
            [{"lot_id": lot_id}],
        )
    rows = state.store.fetchall(
        "SELECT component_id FROM components WHERE lot_id = ? AND dataset_hash = ?"
        " ORDER BY component_id ASC",
        [lot_id, dataset_hash],
    )
    return [str(row[0]) for row in rows]


def _versions_json(state: Any) -> str:
    calibration = state.calibration
    return _json.dumps(dict(calibration.model_versions) if calibration else {})


def _dump(block: Any) -> str:
    return _json.dumps(block, sort_keys=True, default=str)


_PDA_OPERANDS = {"lot.pda_pct_v1": "n_reject", "lot.pda_pct_ew_v1": "n_reject_ew"}


def _dump_pda(
    value: float, n_reject: int, n_tested: int, dataset_hash: str, formula_id: str
) -> dict[str, Any]:
    traced = trace(
        value,
        "percent",
        formula_id,
        {_PDA_OPERANDS[formula_id]: n_reject, "n_tested": n_tested},
        {"percent_scale": PERCENT_SCALE},
        dataset_hash,
        2,
    )
    spec = get_formula(formula_id)
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
