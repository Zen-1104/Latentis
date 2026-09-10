"""Distribution, posture, and report routes (Phase 5, T-504).

TASKS T-504 maps onto the contract surface as follows:

- ``/lots/{id}/distribution`` — the S2 Lot Explorer payload.
- ``/posture`` — the Mission Risk Posture payload (S5 surface data).
- ``/export/{id}.pdf`` — realised as ``POST /reports`` (create) plus
  ``GET /reports/{id}`` (HTML + metadata) and ``GET /reports/{id}/pdf``
  (the PDF rendering), per API_CONTRACT.md section 8. The PDF leg needs
  Playwright Chromium; without it the route answers 503 naming the
  renderer while HTML stays fully available.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.app.errors import ApiError, ErrorCode
from backend.app.runtime import build_meta
from backend.app.schemas import Envelope
from backend.reporting import render_pdf
from backend.services import lot_views
from backend.services import reports as reports_service

router = APIRouter(tags=["reports"])


class ReportRequest(BaseModel):
    """Report creation request (API_CONTRACT section 8)."""

    scope: str = Field(pattern="^(component|lot)$")
    target_id: str = Field(min_length=1)
    format: str = Field(pattern="^(html|pdf)$", default="html")


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


@router.get("/lots/{lot_id}/distribution")
def get_distribution(request: Request, lot_id: str) -> Envelope[dict[str, Any]]:
    """Per-parameter distributions with DPAT limits and member positions."""
    request_id, start_ns, state = _context(request)
    return Envelope[dict[str, Any]](
        data=lot_views.lot_distribution(state, lot_id),
        meta=_meta(request_id, start_ns, state),
    )


@router.get("/posture")
def get_posture(request: Request) -> Envelope[dict[str, Any]]:
    """Mission Risk Posture: risk configuration with model identity."""
    request_id, start_ns, state = _context(request)
    return Envelope[dict[str, Any]](
        data=lot_views.system_posture(state), meta=_meta(request_id, start_ns, state)
    )


@router.post("/reports")
def post_reports(request: Request, body: ReportRequest) -> Envelope[dict[str, Any]]:
    """Create a disposition report (HTML always; PDF rendered on fetch)."""
    request_id, start_ns, state = _context(request)
    metadata = reports_service.build_report(state, body.scope, body.target_id, body.format)
    return Envelope[dict[str, Any]](data=metadata, meta=_meta(request_id, start_ns, state))


@router.get("/reports/{report_id}")
def get_report(request: Request, report_id: str) -> Envelope[dict[str, Any]]:
    """Fetch one stored report's metadata and self-contained HTML."""
    request_id, start_ns, state = _context(request)
    return Envelope[dict[str, Any]](
        data=reports_service.get_report(state, report_id),
        meta=_meta(request_id, start_ns, state),
    )


@router.get("/reports/{report_id}/pdf")
def get_report_pdf(request: Request, report_id: str) -> Response:
    """The PDF rendering of a report (TASKS ``/export/{id}.pdf``)."""
    _, _, state = _context(request)
    stored = reports_service.get_report(state, report_id)
    try:
        pdf_bytes = render_pdf(stored["html"])
    except RuntimeError as err:
        raise ApiError(
            ErrorCode.MODEL_UNAVAILABLE,
            str(err),
            [{"report_id": report_id, "renderer": "playwright-chromium"}],
        ) from err
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{report_id}.pdf"'},
    )
