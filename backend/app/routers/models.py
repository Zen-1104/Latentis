"""Formula registry and model-info routes (Phase 5, T-503).

Implements API_CONTRACT.md section 8 (models, explanations, reports —
reports land in T-504):

- ``GET /formulas`` / ``GET /formulas/{id}`` — registry entries with
  expression, description, operands, unit rule, source reference.
- ``GET /models`` — registered calibration identity, versions, loaded
  state, feature schema note.
- ``GET /models/coverage`` — conformal ladder capacity per group
  (``n_cal``, attainable alpha, target). Held-out coverage is pending
  T-402/T-406 and is labelled so — never estimated.
- ``GET /models/shape/{group}`` — the fitted population shape as
  plottable points plus family, parameter, and fit quality.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Request

from backend.app.errors import ApiError, ErrorCode
from backend.app.runtime import build_meta
from backend.app.schemas import Envelope
from backend.core.formulas import FORMULAS, get_formula
from backend.core.shape import ShapeFamily, phi_at
from backend.services.calibration import calibration_manifest, ensure_calibration

router = APIRouter(tags=["models"])

_ALLOWLIST_NOTE = "Module B input allow-list (DRIFT_SPEC section 3)"


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


@router.get("/formulas")
def list_formulas(request: Request) -> Envelope[list[dict[str, Any]]]:
    """Every registry entry with its human-readable contract."""
    request_id, start_ns, state = _context(request)
    entries = [
        {
            "formula_id": spec.formula_id,
            "expression": spec.expression,
            "description": spec.description,
            "operands": list(spec.operands),
            "parameters": list(spec.parameters),
            "unit_rule": spec.unit_rule,
            "source_ref": spec.source_ref,
        }
        for _, spec in sorted(FORMULAS.items())
    ]
    return Envelope[list[dict[str, Any]]](data=entries, meta=_meta(request_id, start_ns, state))


@router.get("/formulas/{formula_id}")
def get_formula_entry(request: Request, formula_id: str) -> Envelope[dict[str, Any]]:
    """One registry entry (unknown ids are structured 404s)."""
    request_id, start_ns, state = _context(request)
    try:
        spec = get_formula(formula_id)
    except ValueError:
        raise ApiError(
            ErrorCode.NOT_FOUND,
            f"Unknown formula {formula_id!r}.",
            [{"formula_id": formula_id}],
        ) from None
    return Envelope[dict[str, Any]](
        data={
            "formula_id": spec.formula_id,
            "expression": spec.expression,
            "description": spec.description,
            "operands": list(spec.operands),
            "parameters": list(spec.parameters),
            "unit_rule": spec.unit_rule,
            "source_ref": spec.source_ref,
        },
        meta=_meta(request_id, start_ns, state),
    )


@router.get("/models")
def list_models(request: Request) -> Envelope[dict[str, Any]]:
    """Calibration identity: versions, manifests, loaded state, cards note."""
    request_id, start_ns, state = _context(request)
    calibration = ensure_calibration(state)
    manifest = calibration_manifest(calibration)
    data = {
        "artifacts": [
            {
                "name": name,
                "version": version,
                "loaded": True,
                "provisional": True,
                "card": None,
                "card_note": "Model cards ship with the T-401 registry (T-405);"
                " this provisional calibration is card-pending by design.",
            }
            for name, version in sorted(calibration.model_versions.items())
        ],
        "manifest": manifest,
        "feature_schema_note": _ALLOWLIST_NOTE,
    }
    return Envelope[dict[str, Any]](data=data, meta=_meta(request_id, start_ns, state))


@router.get("/models/coverage")
def models_coverage(request: Request) -> Envelope[dict[str, Any]]:
    """Ladder capacity per Mondrian group; held-out coverage pending T-402."""
    request_id, start_ns, state = _context(request)
    calibration = ensure_calibration(state)
    profile = state.active_profile()
    groups = []
    for key in sorted(calibration.groups):
        group = calibration.groups[key]
        n_cal = len(group.residuals_l0)
        attainable = 1.0 / (n_cal + 1) if n_cal else None
        groups.append(
            {
                "group": f"{key[0]}/{key[1]}",
                "n_cal": n_cal,
                "alpha": profile.alpha,
                "coverage_target": 1.0 - profile.alpha,
                "attainable_alpha": attainable,
                "alpha_supported": attainable is not None and profile.alpha >= attainable,
                "measured_coverage": None,
                "measured_coverage_note": "Held-out coverage is measured at T-402/T-406"
                " on the test split, scored once per tag (D-030). Not estimated here.",
            }
        )
    return Envelope[dict[str, Any]](
        data={"groups": groups, "method": "split_conformal", "score": "signed_residual"},
        meta=_meta(request_id, start_ns, state),
    )


@router.get("/models/shape/{group:path}")
def model_shape(request: Request, group: str) -> Envelope[dict[str, Any]]:
    """The fitted population shape as plottable points (DRIFT_SPEC 4.2)."""
    request_id, start_ns, state = _context(request)
    calibration = ensure_calibration(state)
    try:
        component_type, parameter = group.split("/", 1)
    except ValueError:
        raise ApiError(
            ErrorCode.NOT_FOUND,
            f"Unknown shape group {group!r}; expected <component_type>/<parameter>.",
            [{"group": group}],
        ) from None
    entry = calibration.groups.get((component_type, parameter))
    if entry is None or entry.phi_168 is None:
        raise ApiError(
            ErrorCode.NOT_FOUND,
            f"Unknown shape group {group!r}.",
            [{"group": group}],
        )
    times = [0.0, 6.0, 12.0, 24.0, 48.0, 96.0, 168.0]
    family = cast(ShapeFamily, entry.family)
    points = [
        {"t_hours": time, "phi": phi_at(time, entry.phi_168, family, entry.family_param)}
        for time in times
    ]
    return Envelope[dict[str, Any]](
        data={
            "group": group,
            "family": entry.family,
            "family_param": entry.family_param,
            "phi_168": entry.phi_168,
            "fitted_on_lots": entry.n_phi_used,
            "points": points,
            "normalisation": "phi_g(24) = 1 by construction",
            "warning": entry.phi_warning,
        },
        meta=_meta(request_id, start_ns, state),
    )
