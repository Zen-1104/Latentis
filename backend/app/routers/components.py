"""Component and investigation routes (Phase 5, T-503).

Implements API_CONTRACT.md section 7 over the T-501 envelope. Every
route resolves the investigator, projects its JSON-safe payload into the
typed response model, and stamps ``meta``. Unknown ids are structured
404s; refusal states inside a payload are 200s (the analysis answered,
deferring where evidence is insufficient).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request

from backend.app.errors import ApiError, ErrorCode
from backend.app.runtime import build_meta, utc_now_z
from backend.app.schemas import Envelope
from backend.app.schemas_phase5 import (
    ComponentIdentity,
    ComponentSummary,
    DispositionRecord,
    DispositionRequest,
    InvestigationData,
)
from backend.services.investigation import build_investigator

router = APIRouter(tags=["components"])

_PAGE_DEFAULT: int = 50
_PAGE_MAX: int = 200


def _context(request: Request) -> tuple[str, int, Any]:
    return (
        getattr(request.state, "request_id", "unknown"),
        getattr(request.state, "start_ns", 0),
        request.app.state.app_state,
    )


def _meta(request_id: str, start_ns: int, state: Any, investigator: Any = None) -> Any:
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
            ErrorCode.UNKNOWN_COMPONENT,
            "No dataset ingested yet; ingest one before listing components.",
            [{"remediation": "POST /api/v1/datasets with a screening CSV or Parquet file"}],
        )
    return str(dataset_hash)


@router.get("/components")
def list_components(
    request: Request, lot_id: str | None = None, limit: int = _PAGE_DEFAULT, cursor: str = "0"
) -> Envelope[dict[str, Any]]:
    """Paginated component directory (metadata only; analysis lives downstream)."""
    request_id, start_ns, state = _context(request)
    dataset_hash = _require_dataset(state)
    safe_limit = max(1, min(limit, _PAGE_MAX))
    try:
        offset = max(0, int(cursor))
    except ValueError:
        raise ApiError(
            ErrorCode.VALIDATION_FAILED,
            f"Invalid cursor {cursor!r}; expected an integer offset.",
            [{"cursor": cursor}],
        ) from None
    params: list[Any] = [dataset_hash]
    where = "dataset_hash = ?"
    if lot_id is not None:
        where = "lot_id = ? AND dataset_hash = ?"
        params = [lot_id, dataset_hash]
    rows = state.store.fetchall(
        "SELECT component_id, lot_id, component_type, board_id, socket_id,"
        " thermal_zone, tester_id FROM components"
        f" WHERE {where} ORDER BY component_id ASC LIMIT ? OFFSET ?",
        [*params, safe_limit + 1, offset],
    )
    page = rows[:safe_limit]
    next_cursor = str(offset + safe_limit) if len(rows) > safe_limit else None
    summaries = [
        ComponentSummary(
            component_id=str(row[0]),
            lot_id=str(row[1]),
            component_type=str(row[2]),
            board_id=row[3],
            socket_id=row[4],
            thermal_zone=row[5],
            tester_id=row[6],
        ).model_dump()
        for row in page
    ]
    return Envelope[dict[str, Any]](
        data={"items": summaries, "next_cursor": next_cursor},
        meta=_meta(request_id, start_ns, state),
    )


@router.get("/components/{component_id}")
def get_component(request: Request, component_id: str) -> Envelope[ComponentIdentity]:
    """Static metadata for one component (no decision content)."""
    request_id, start_ns, state = _context(request)
    dataset_hash = _require_dataset(state)
    row = state.store.fetchone(
        "SELECT component_id, lot_id, component_type, board_id, socket_id,"
        " thermal_zone, tester_id FROM components"
        " WHERE component_id = ? AND dataset_hash = ?",
        [component_id, dataset_hash],
    )
    if row is None:
        raise ApiError(
            ErrorCode.UNKNOWN_COMPONENT,
            f"Unknown component {component_id!r} in this dataset.",
            [{"component_id": component_id}],
        )
    identity = ComponentIdentity(
        component_id=str(row[0]),
        lot_id=str(row[1]),
        component_type=str(row[2]),
        board_id=row[3],
        socket_id=row[4],
        thermal_zone=row[5],
        tester_id=row[6],
    )
    return Envelope[ComponentIdentity](data=identity, meta=_meta(request_id, start_ns, state))


@router.get("/components/{component_id}/investigation")
def get_investigation(request: Request, component_id: str) -> Envelope[InvestigationData]:
    """Flagship composite: anomaly + drift + risk + explanation (T-503)."""
    request_id, start_ns, state = _context(request)
    investigator = build_investigator(state)
    payload = investigator.assemble(component_id)
    data = InvestigationData.model_validate(payload)
    return Envelope[InvestigationData](data=data, meta=_meta(request_id, start_ns, state))


@router.get("/components/{component_id}/anomaly")
def get_anomaly(request: Request, component_id: str) -> Envelope[dict[str, Any]]:
    """ANOMALY_SPEC section 8 contract projected from the investigation."""
    request_id, start_ns, state = _context(request)
    investigator = build_investigator(state)
    payload = investigator.assemble(component_id)
    profile = state.active_profile()
    parameters = []
    for block in payload["parameters"]:
        readings = {item["elapsed_hours"]: item for item in block["readings"]}
        obs24 = readings.get(24, {})
        value_tv = obs24.get("value") if isinstance(obs24, dict) else None
        parameters.append(
            {
                "parameter": block["parameter"],
                "read_point_h": 24,
                "observed": value_tv,
                "cohort": block["cohort"],
                "lot_statistics": block["lot_statistics"],
                "dpat": block["dpat"],
                "absolute": block["absolute"],
                "members": block["members"],
                "severity": block["severity"],
                "attribution": block["attribution"],
                "guards": block["guards"],
                "threshold": None,
                "threshold_note": "Neyman-Pearson operating threshold pending T-402 calibration;"
                " flagged mirrors the DPAT verdict meanwhile.",
                "flagged": block["dpat"].get("verdict") == "FAIL"
                or block["absolute"].get("verdict") == "FAIL",
            }
        )
    data = {
        "component": payload["component"],
        "profile_k": profile.k,
        "parameters": parameters,
        "worst": payload["worst"],
        "provenance": payload["provenance"],
    }
    return Envelope[dict[str, Any]](data=data, meta=_meta(request_id, start_ns, state))


@router.get("/components/{component_id}/drift")
def get_drift(request: Request, component_id: str) -> Envelope[dict[str, Any]]:
    """DRIFT_SPEC section 8 contract projected from the investigation."""
    request_id, start_ns, state = _context(request)
    investigator = build_investigator(state)
    payload = investigator.assemble(component_id)
    profile = state.active_profile()
    parameters = []
    for block in payload["parameters"]:
        drift = block["drift"]
        parameters.append(
            {
                "parameter": block["parameter"],
                "unit": block["unit"],
                "drift": drift,
                "guards": block["guards"],
            }
        )
    data = {
        "component": payload["component"],
        "horizon_hours": profile.horizon_hours,
        "alpha": profile.alpha,
        "parameters": parameters,
        "worst": payload["worst"],
        "provenance": payload["provenance"],
    }
    return Envelope[dict[str, Any]](data=data, meta=_meta(request_id, start_ns, state))


@router.get("/components/{component_id}/explanation")
def get_explanation(request: Request, component_id: str) -> Envelope[dict[str, Any]]:
    """Narrative, attribution, and counterfactuals for one component."""
    request_id, start_ns, state = _context(request)
    investigator = build_investigator(state)
    payload = investigator.assemble(component_id)
    parameters = [
        {
            "parameter": block["parameter"],
            "narratives": block["narratives"],
            "attribution": block["attribution"],
            "recommendation": block["recommendation"],
            "severity": block["severity"],
            "band": block["band"],
        }
        for block in payload["parameters"]
    ]
    data = {
        "component": payload["component"],
        "explanation": payload["explanation"],
        "parameters": parameters,
        "worst": payload["worst"],
        "provenance": payload["provenance"],
    }
    return Envelope[dict[str, Any]](data=data, meta=_meta(request_id, start_ns, state))


@router.post("/components/{component_id}/disposition")
def post_disposition(
    request: Request, component_id: str, body: DispositionRequest
) -> Envelope[DispositionRecord]:
    """Record an inspector disposition; append-only with evidence snapshot."""
    request_id, start_ns, state = _context(request)
    investigator = build_investigator(state)
    if body.action == "OVERRIDE" and not body.reason.strip():
        raise ApiError(
            ErrorCode.REASON_REQUIRED,
            "OVERRIDE requires a non-empty reason (FR-409).",
            [{"component_id": component_id, "action": body.action}],
        )
    payload = investigator.assemble(component_id)
    profile = state.active_profile()
    disposition_id = uuid.uuid4().hex
    created_at = utc_now_z()
    # Snapshot the exact validated payload the operator saw (P4 decision
    # provenance): response-model defaults included, byte-stable keys.
    shown = InvestigationData.model_validate(payload)
    snapshot = shown.model_dump_json()
    state.store.execute(
        "INSERT INTO dispositions (disposition_id, component_id, dataset_hash, run_id,"
        " action, reason, actor, profile_id, profile_version, system_output_snapshot,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            disposition_id,
            component_id,
            state.active_dataset_hash,
            body.run_id,
            body.action,
            body.reason,
            body.actor,
            profile.profile_id,
            profile.version,
            snapshot,
            created_at,
        ],
    )
    record = DispositionRecord(
        disposition_id=disposition_id,
        component_id=component_id,
        action=body.action,
        reason=body.reason,
        actor=body.actor,
        profile_ref=f"{profile.profile_id}@{profile.version}",
        created_at=created_at,
    )
    return Envelope[DispositionRecord](data=record, meta=_meta(request_id, start_ns, state))
