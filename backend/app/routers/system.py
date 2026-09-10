"""System routes: health and version (Phase 5, T-501).

Both endpoints are introspection over the running process — registry
identity, code identity, store readiness — and call no decision function.
The ``/health`` path is an alias of ``/healthz``: TASKS.md T-501 names
``/healthz`` while API_CONTRACT § 3, ARCHITECTURE § 7, and PROVENANCE_SPEC
§ 8 name ``/health``. One handler serves both so the two references can
never disagree.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.runtime import (
    API_VERSION,
    SERVICE_NAME,
    build_meta,
    code_info,
    formula_registry_summary,
)
from backend.app.schemas import CodeInfo, Envelope, FormulaRegistryInfo, HealthData, VersionData

router = APIRouter(tags=["system"])

_MISSING_DATASET: str = "dataset: no dataset ingested yet (T-502)"
_MISSING_MODELS: str = "models: no artifacts registered yet (T-401)"
_MISSING_PROFILE: str = "profile: no profile store yet"

_HEALTH_REMEDIATION: str = (
    "Ingest a dataset (T-502) and register model artifacts (T-401); "
    "introspection endpoints remain available while degraded."
)


def _request_context(request: Request) -> tuple[str, int]:
    return (
        getattr(request.state, "request_id", "unknown"),
        getattr(request.state, "start_ns", 0),
    )


def _health_data(state: object | None = None) -> HealthData:
    """Assemble the health payload; introspection failures degrade, never raise."""
    # Narrow guard, not a blind catch: health must never 500 (API_CONTRACT § 3),
    # and these are the conceivable failure modes of registry/code introspection.
    try:
        registry = formula_registry_summary()
    except (OSError, ValueError, RuntimeError, AttributeError):
        registry = FormulaRegistryInfo(entries=0, hash="sha256:unavailable")
    try:
        code = code_info()
    except (OSError, ValueError, RuntimeError, AttributeError):
        code = CodeInfo(git_sha="unknown", dirty=False)
    dataset_hash: str | None = None
    models: dict[str, str] = {}
    profile_id: str | None = None
    profile_version: int | None = None
    missing = [_MISSING_DATASET, _MISSING_MODELS, _MISSING_PROFILE]
    if state is not None:
        dataset_hash = state.active_dataset_hash  # type: ignore[attr-defined]
        calibration = state.calibration  # type: ignore[attr-defined]
        if calibration is not None:
            models = dict(calibration.model_versions)
        profile_id = state.active_profile_id  # type: ignore[attr-defined]
        profile_version = state.active_profile_version  # type: ignore[attr-defined]
        missing = []
        if dataset_hash is None:
            missing.append(_MISSING_DATASET)
        if not models:
            missing.append(_MISSING_MODELS)
        if profile_id is None:
            missing.append(_MISSING_PROFILE)
    status = "ok" if not missing else "degraded"
    return HealthData(
        status=status,
        dataset_hash=dataset_hash,
        models=models,
        profile_id=profile_id,
        profile_version=profile_version,
        formula_registry=registry,
        code=code,
        missing=missing,
        remediation=_HEALTH_REMEDIATION if missing else "All stores loaded.",
    )


def _version_data() -> VersionData:
    """Assemble the version payload; same degradation rule as health."""
    try:
        registry = formula_registry_summary()
    except (OSError, ValueError, RuntimeError, AttributeError):
        registry = FormulaRegistryInfo(entries=0, hash="sha256:unavailable")
    try:
        code = code_info()
    except (OSError, ValueError, RuntimeError, AttributeError):
        code = CodeInfo(git_sha="unknown", dirty=False)
    return VersionData(
        service=SERVICE_NAME,
        api_version=API_VERSION,
        code=code,
        formula_registry=registry,
    )


@router.get("/healthz", response_model=Envelope[HealthData])
def get_healthz(request: Request) -> Envelope[HealthData]:
    """Liveness + readiness with provenance identity (T-501)."""
    request_id, start_ns = _request_context(request)
    state = getattr(request.app.state, "app_state", None)
    data = _health_data(state)
    return Envelope[HealthData](
        data=data,
        meta=build_meta(
            request_id,
            start_ns,
            dataset_hash=data.dataset_hash,
            profile_id=data.profile_id,
            profile_version=data.profile_version,
            model_versions=dict(data.models),
        ),
    )


@router.get("/health", response_model=Envelope[HealthData])
def get_health(request: Request) -> Envelope[HealthData]:
    """Contract-named alias of ``/healthz`` (API_CONTRACT § 3). Same handler truth."""
    request_id, start_ns = _request_context(request)
    state = getattr(request.app.state, "app_state", None)
    data = _health_data(state)
    return Envelope[HealthData](
        data=data,
        meta=build_meta(
            request_id,
            start_ns,
            dataset_hash=data.dataset_hash,
            profile_id=data.profile_id,
            profile_version=data.profile_version,
            model_versions=dict(data.models),
        ),
    )


@router.get("/version", response_model=Envelope[VersionData])
def get_version(request: Request) -> Envelope[VersionData]:
    """Service identity: code SHA, registry hash, API version (T-501)."""
    request_id, start_ns = _request_context(request)
    return Envelope[VersionData](data=_version_data(), meta=build_meta(request_id, start_ns))
