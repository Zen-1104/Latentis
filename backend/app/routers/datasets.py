"""Datasets, profiles, and ingest routes (Phase 5, T-502).

Implements API_CONTRACT.md sections 4-5 over the T-501 envelope:

- ``POST /datasets`` — multipart CSV/Parquet intake with the four-class
  rejection report. Transactional: no partial commit (NFR-12).
- ``GET /datasets`` / ``GET /datasets/{hash}`` — manifests and hashes.
- ``POST /datasets/{hash}/validate`` — re-run the structural gates.
- ``GET /profiles`` / ``GET /profiles/{id}`` / ``PUT /profiles/{id}``
  — profile reads plus append-only versioning (FR-607).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Request, UploadFile
from pydantic import BaseModel, Field

from backend.app.runtime import build_meta
from backend.app.schemas import Envelope
from backend.services import ingest as ingest_service
from backend.services.ingest import IngestReport

router = APIRouter(tags=["datasets"])


def _context(request: Request) -> tuple[str, int, Any]:
    return (
        getattr(request.state, "request_id", "unknown"),
        getattr(request.state, "start_ns", 0),
        request.app.state.app_state,
    )


def _meta(request_id: str, start_ns: int, state: Any) -> Any:
    return build_meta(
        request_id,
        start_ns,
        dataset_hash=state.active_dataset_hash,
        profile_id=state.active_profile_id,
        profile_version=state.active_profile_version,
        model_versions=_loaded_model_versions(state),
    )


def _loaded_model_versions(state: Any) -> dict[str, str]:
    calibration = state.calibration
    if calibration is None:
        return {}
    versions = dict(calibration.model_versions)
    versions["calibration_dataset"] = calibration.dataset_hash
    return versions


class ProfileUpdateRequest(BaseModel):
    """Full profile document for a new version (fields mirror ScreeningProfile)."""

    k: float = Field(gt=0)
    alpha: float = Field(gt=0, lt=1)
    margin_fraction: float = Field(ge=0, lt=1)
    horizon_hours: float = Field(gt=0)
    pda_limit_pct: float = Field(gt=0)
    readpoint_grid: list[int] = Field(min_length=1)
    limits: dict[str, Any]
    risk_weights: dict[str, float] | None = None
    n_min_zone: int = Field(ge=3, default=20)


@router.post("/datasets", response_model=Envelope[IngestReport])
async def post_datasets(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008 — canonical FastAPI declaration
    profile_id: str | None = None,
) -> Envelope[IngestReport]:
    """Ingest one CSV/Parquet file; returns the rejection report (T-502)."""
    request_id, start_ns, state = _context(request)
    payload = await file.read()
    if profile_id:
        profile = state.profiles.latest(profile_id)
    else:
        profile = state.profiles.latest("mil_std_883_like")
    report = ingest_service.ingest_payload(state.store, payload, file.filename or "upload", profile)
    state.set_active_dataset(report.dataset_hash)
    state.set_active_profile(report.profile_id, report.profile_version)
    return Envelope[IngestReport](data=report, meta=_meta(request_id, start_ns, state))


@router.get("/datasets")
def get_datasets(request: Request) -> Envelope[list[dict[str, Any]]]:
    """List ingested datasets with hashes and row counts."""
    request_id, start_ns, state = _context(request)
    return Envelope[list[dict[str, Any]]](
        data=ingest_service.list_datasets(state.store),
        meta=_meta(request_id, start_ns, state),
    )


@router.get("/datasets/{dataset_hash}")
def get_dataset(request: Request, dataset_hash: str) -> Envelope[dict[str, Any]]:
    """Fetch one dataset manifest by content hash."""
    request_id, start_ns, state = _context(request)
    return Envelope[dict[str, Any]](
        data=ingest_service.get_manifest(state.store, dataset_hash),
        meta=_meta(request_id, start_ns, state),
    )


@router.post("/datasets/{dataset_hash}/validate")
def post_dataset_validate(request: Request, dataset_hash: str) -> Envelope[dict[str, Any]]:
    """Re-run the structural validation gates over stored data."""
    request_id, start_ns, state = _context(request)
    return Envelope[dict[str, Any]](
        data=ingest_service.validate_dataset(state.store, dataset_hash),
        meta=_meta(request_id, start_ns, state),
    )


@router.get("/profiles")
def get_profiles(request: Request) -> Envelope[list[dict[str, Any]]]:
    """Every profile with its stored versions."""
    request_id, start_ns, state = _context(request)
    data = [
        {"profile_id": profile_id, "versions": state.profiles.list_versions(profile_id)}
        for profile_id in state.profiles.list_ids()
    ]
    return Envelope[list[dict[str, Any]]](data=data, meta=_meta(request_id, start_ns, state))


@router.get("/profiles/{profile_id}")
def get_profile(request: Request, profile_id: str) -> Envelope[dict[str, Any]]:
    """The latest version of one profile, with provenance tags."""
    request_id, start_ns, state = _context(request)
    profile = state.profiles.latest(profile_id)
    return Envelope[dict[str, Any]](
        data=state.profiles.profile_document(profile),
        meta=_meta(request_id, start_ns, state),
    )


@router.get("/profiles/{profile_id}/{version}")
def get_profile_version(
    request: Request, profile_id: str, version: int
) -> Envelope[dict[str, Any]]:
    """One exact profile version (dispositions pin these, FR-607)."""
    request_id, start_ns, state = _context(request)
    profile = state.profiles.get(profile_id, version)
    return Envelope[dict[str, Any]](
        data=state.profiles.profile_document(profile),
        meta=_meta(request_id, start_ns, state),
    )


@router.put("/profiles/{profile_id}")
def put_profile(
    request: Request, profile_id: str, body: ProfileUpdateRequest
) -> Envelope[dict[str, Any]]:
    """Append a new profile version; existing versions are never mutated."""
    request_id, start_ns, state = _context(request)
    profile = state.profiles.create_version(profile_id, body.model_dump())
    return Envelope[dict[str, Any]](
        data=state.profiles.profile_document(profile),
        meta=_meta(request_id, start_ns, state),
    )


@router.put("/profiles/{profile_id}/{version}")
def rewrite_profile(
    request: Request, profile_id: str, version: int, body: ProfileUpdateRequest
) -> Envelope[dict[str, Any]]:
    """Replace an unreferenced draft version; referenced ones are 409 (TEST-PROF-001)."""
    request_id, start_ns, state = _context(request)
    profile = state.profiles.rewrite_version(profile_id, version, body.model_dump())
    return Envelope[dict[str, Any]](
        data=state.profiles.profile_document(profile),
        meta=_meta(request_id, start_ns, state),
    )
