"""Report content builder (Phase 5, T-504).

Assembles Jinja2 contexts from live payloads — the same assembled
investigation and disposition structures the API serves, never a
parallel computation. The renderer (``backend.reporting``) turns the
context into self-contained HTML; PDF is a rendering of that HTML.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Final

from backend.app.errors import ApiError, ErrorCode
from backend.app.runtime import code_info, utc_now_z
from backend.reporting import render_html
from backend.services.investigation import build_investigator

_SCOPES: Final[tuple[str, ...]] = ("component", "lot")
_FORMATS: Final[tuple[str, ...]] = ("html", "pdf")


def _short(dataset_hash: str) -> str:
    return dataset_hash.replace("sha256:", "")[:12]


def build_report(state: Any, scope: str, target_id: str, format: str) -> dict[str, Any]:
    """Build and store one report; returns its metadata (T-504)."""
    if scope not in _SCOPES:
        raise ApiError(
            ErrorCode.VALIDATION_FAILED,
            f"Unknown report scope {scope!r}; expected one of {list(_SCOPES)}.",
            [{"scope": scope}],
        )
    if format not in _FORMATS:
        raise ApiError(
            ErrorCode.VALIDATION_FAILED,
            f"Unknown report format {format!r}; expected one of {list(_FORMATS)}.",
            [{"format": format}],
        )
    investigator = build_investigator(state)
    profile = state.active_profile()
    dataset_hash = str(state.active_dataset_hash)
    report_id = uuid.uuid4().hex
    created_at = utc_now_z()
    calibration = state.calibration
    model_versions = dict(calibration.model_versions) if calibration else {}
    base: dict[str, Any] = {
        "report_id": report_id,
        "scope": scope,
        "target_id": target_id,
        "dataset_hash": dataset_hash,
        "dataset_hash_short": _short(dataset_hash),
        "profile_ref": f"{profile.profile_id}@{profile.version}",
        "model_versions": json.dumps(model_versions, sort_keys=True),
        "code_sha": code_info().git_sha,
        "generated_at": created_at,
        "alpha": profile.alpha,
        "k": profile.k,
        "margin_fraction": profile.margin_fraction,
        "pda_limit_pct": profile.pda_limit_pct,
        "dispositions": [],
    }
    if scope == "component":
        payload = investigator.assemble(target_id)
        base.update(
            {
                "worst": payload["worst"],
                "narrative": payload["explanation"].get("narrative", ""),
                "parameters": payload["parameters"],
                "appendix": payload["provenance"].get("formulas_used", []),
            }
        )
        base["dispositions"] = _dispositions_for(state, target_id, None)
    else:
        _require_lot(state, dataset_hash, target_id)
        queue: list[dict[str, Any]] = []
        appendix: dict[str, dict[str, str]] = {}
        parts = _lot_parts(state, dataset_hash, target_id)
        for component_id in parts:
            payload = investigator.assemble(component_id)
            worst = payload["worst"]
            queue.append(
                {
                    "component_id": component_id,
                    "severity": worst["severity"],
                    "band": worst["band"],
                    "recommendation": worst["recommendation"],
                    "worst_parameter": worst["parameter"],
                }
            )
            for item in payload["provenance"].get("formulas_used", []):
                appendix[str(item["formula_id"])] = {
                    "formula_id": str(item["formula_id"]),
                    "expression": str(item["expression"]),
                }
        disposition = _lot_disposition(state, investigator, target_id)
        if isinstance(disposition.get("pda_pct"), dict):
            appendix["lot.pda_pct_v1"] = {
                "formula_id": "lot.pda_pct_v1",
                "expression": "percent_scale * n_reject / n_tested",
            }
        base.update(
            {
                "queue": queue,
                "disposition": disposition,
                "appendix": sorted(appendix.values(), key=lambda item: item["formula_id"]),
            }
        )
        base["dispositions"] = _dispositions_for(state, None, target_id)
    html = render_html(base)
    state.store.execute(
        "INSERT INTO reports (report_id, dataset_hash, scope, target_id, format,"
        " profile_id, profile_version, html, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            report_id,
            dataset_hash,
            scope,
            target_id,
            format,
            profile.profile_id,
            profile.version,
            html,
            created_at,
        ],
    )
    return {
        "report_id": report_id,
        "scope": scope,
        "target_id": target_id,
        "format": format,
        "profile_ref": base["profile_ref"],
        "dataset_hash": dataset_hash,
        "created_at": created_at,
        "pdf_available": format == "pdf",
    }


def get_report(state: Any, report_id: str) -> dict[str, Any]:
    """Fetch one stored report's metadata and HTML."""
    row = state.store.fetchone(
        "SELECT report_id, dataset_hash, scope, target_id, format, profile_id,"
        " profile_version, html, created_at FROM reports WHERE report_id = ?",
        [report_id],
    )
    if row is None:
        raise ApiError(
            ErrorCode.NOT_FOUND,
            f"Unknown report {report_id!r}.",
            [{"report_id": report_id}],
        )
    return {
        "report_id": str(row[0]),
        "dataset_hash": str(row[1]),
        "scope": str(row[2]),
        "target_id": str(row[3]),
        "format": str(row[4]),
        "profile_ref": f"{row[5]}@{row[6]}",
        "html": str(row[7]),
        "created_at": str(row[8]),
        "data_provenance": "SYNTHETIC",
    }


def _require_lot(state: Any, dataset_hash: str, lot_id: str) -> None:
    row = state.store.fetchone(
        "SELECT lot_id FROM lots WHERE lot_id = ? AND dataset_hash = ?",
        [lot_id, dataset_hash],
    )
    if row is None:
        raise ApiError(
            ErrorCode.UNKNOWN_LOT,
            f"Unknown lot {lot_id!r} in this dataset.",
            [{"lot_id": lot_id}],
        )


def _lot_parts(state: Any, dataset_hash: str, lot_id: str) -> list[str]:
    rows = state.store.fetchall(
        "SELECT component_id FROM components WHERE lot_id = ? AND dataset_hash = ?"
        " ORDER BY component_id ASC",
        [lot_id, dataset_hash],
    )
    return [str(row[0]) for row in rows]


def _lot_disposition(state: Any, investigator: Any, lot_id: str) -> dict[str, Any]:
    from backend.core.risk import roll_up_lot

    profile = state.active_profile()
    components = _lot_parts(state, str(state.active_dataset_hash), lot_id)
    bands: list[str | None] = []
    absolute_fails: list[bool] = []
    for component_id in components:
        payload = investigator.assemble(component_id)
        worst = payload["worst"]
        bands.append(worst["band"])
        worst_block = next(
            block for block in payload["parameters"] if block["parameter"] == worst["parameter"]
        )
        absolute_fails.append(worst_block["absolute"].get("verdict") == "FAIL")
    rollup = roll_up_lot(bands, absolute_fails, profile.pda_limit_pct)
    return {
        "lot_id": lot_id,
        "n_tested": rollup.n_tested,
        "n_reject": rollup.n_reject,
        "n_early_warning": rollup.n_early_warning,
        "lot_verdict": str(rollup.lot_verdict) if rollup.lot_verdict is not None else None,
        "pda_pct": {"value": rollup.pda_pct} if rollup.pda_pct is not None else None,
        "pda_limit_pct": rollup.pda_limit_pct,
    }


def _dispositions_for(
    state: Any, component_id: str | None, lot_id: str | None
) -> list[dict[str, Any]]:
    if component_id is not None:
        rows = state.store.fetchall(
            "SELECT component_id, action, reason, actor, created_at FROM dispositions"
            " WHERE component_id = ? ORDER BY created_at ASC",
            [component_id],
        )
    elif lot_id is not None:
        rows = state.store.fetchall(
            "SELECT d.component_id, d.action, d.reason, d.actor, d.created_at"
            " FROM dispositions d JOIN components c"
            " ON d.component_id = c.component_id AND d.dataset_hash = c.dataset_hash"
            " WHERE c.lot_id = ? ORDER BY d.created_at ASC",
            [lot_id],
        )
    else:
        rows = []
    return [
        {
            "component_id": str(row[0]),
            "action": str(row[1]),
            "reason": str(row[2]),
            "actor": str(row[3]),
            "created_at": str(row[4]),
        }
        for row in rows
    ]
