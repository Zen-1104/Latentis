"""Provisional drift calibration from committed artifacts (Phase 5, T-503).

Status: **provisional adapter, pending T-401/T-402.** The fitted-artifact
registry (``models/registry``) does not exist yet, but the investigation
surface needs a population shape ``phi_168`` and conformal residual
ladders to produce real forecasts. This module computes both at runtime
from the committed ``train``/``calib`` artifacts — no new fitting
machinery, no invented numbers:

- ``phi_168`` per ``(component_type, parameter)`` via authoritative
  ``backend.core.shape.estimate_phi`` on training lots only (DRIFT_SPEC
  section 4; the fit sees 96/168 h trajectories exactly as specified —
  calibration fitting is not a Module B decision input, INV-4 holds at
  inference because the service only ever feeds 0/24 h reads).
- Signed-residual ladders per Mondrian group via the specified
  construction (CONFORMAL_SPEC section 2): level 0 ``(type, parameter)``,
  level 1 ``(parameter)``, level 2 marginal. ``conformal_upper`` reads
  these ladders; the ladder level used travels in every payload.
- Guard context per group (calibration distributions the
  exchangeability guard compares against, CONFORMAL_SPEC section 5.1).

Never touches ``test.parquet`` (D-030/T-406 ownership). Versions are
content-derived (``prov-<hash8>``): the ``prov-`` prefix marks them as
provisional until the T-401 registry lands. If the artifacts are absent,
callers receive ``MODEL_UNAVAILABLE`` and health reports ``degraded``
(charter non-negotiable 5) — never a silent fallback.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import polars as pl

import backend.core.shape as shape_core
from backend.app.errors import ApiError, ErrorCode
from backend.app.runtime import code_info, utc_now_z

TRAIN_NAME: Final[str] = "train.parquet"
CALIB_NAME: Final[str] = "calib.parquet"
MANIFEST_NAME: Final[str] = "manifest.json"


@dataclass
class GroupCalibration:
    """Fitted quantities for one ``(component_type, parameter)`` group."""

    component_type: str
    parameter: str
    phi_168: float | None
    family: str
    family_param: float | None
    n_phi_used: int
    phi_warning: str | None
    residuals_l0: list[float] = field(default_factory=list)
    calib_v0: list[float] = field(default_factory=list)
    calib_delta24: list[float] = field(default_factory=list)
    calib_lot_medians: list[float] = field(default_factory=list)
    calib_temperatures: list[float] = field(default_factory=list)
    calib_tester_ids: list[str] = field(default_factory=list)


@dataclass
class Calibration:
    """Runtime drift calibration with its own provenance manifest."""

    groups: dict[tuple[str, str], GroupCalibration]
    residuals_l1: dict[str, list[float]]
    residuals_l2: list[float]
    group_keys: list[str]
    train_hash: str
    calib_hash: str
    code_sha: str
    created_at: str
    model_versions: dict[str, str]

    @property
    def dataset_hash(self) -> str:
        """Identity of the calibration data (travels in ``meta``)."""
        return self.calib_hash


def _series_frame(frame: pl.DataFrame) -> pl.DataFrame:
    """Pivot long rows to one row per (component, parameter) with 0/24/168 h."""
    ok = frame.filter(pl.col("status") == "OK")
    # Injected duplicates mirror the ingest rule: first retained (T-502).
    deduped = ok.unique(
        subset=["component_id", "parameter", "elapsed_hours"], keep="first", maintain_order=True
    )
    return deduped.group_by(
        ["component_id", "lot_id", "component_type", "parameter", "tester_id"],
        maintain_order=True,
    ).agg(
        pl.col("measurement_value").filter(pl.col("elapsed_hours") == 0).first().alias("v0"),
        pl.col("measurement_value").filter(pl.col("elapsed_hours") == 24).first().alias("v24"),
        pl.col("measurement_value").filter(pl.col("elapsed_hours") == 168).first().alias("v168"),
        pl.col("temperature_c").filter(pl.col("elapsed_hours") == 0).first().alias("temp0"),
        pl.col("temperature_c").filter(pl.col("elapsed_hours") == 24).first().alias("temp24"),
    )


def build_calibration(data_dir: Path) -> Calibration:
    """Fit the provisional calibration from the committed artifacts."""
    train_path = data_dir / TRAIN_NAME
    calib_path = data_dir / CALIB_NAME
    manifest_path = data_dir / MANIFEST_NAME
    if not train_path.exists() or not calib_path.exists():
        missing = sorted(
            name
            for name, path in ((TRAIN_NAME, train_path), (CALIB_NAME, calib_path))
            if not path.exists()
        )
        raise ApiError(
            ErrorCode.MODEL_UNAVAILABLE,
            f"Drift calibration artifacts missing: {', '.join(missing)}.",
            [{"missing": missing, "data_dir": str(data_dir)}],
        )
    train = pl.read_parquet(train_path)
    calib = pl.read_parquet(calib_path)
    train_hash = f"sha256:{hashlib.sha256(train_path.read_bytes()).hexdigest()}"
    calib_hash = f"sha256:{hashlib.sha256(calib_path.read_bytes()).hexdigest()}"
    _ = manifest_path.exists()  # manifest informs; hashes above are authoritative.

    train_series = _series_frame(train).filter(
        pl.col("v0").is_not_null() & pl.col("v24").is_not_null() & pl.col("v168").is_not_null()
    )
    calib_series = _series_frame(calib).filter(
        pl.col("v0").is_not_null() & pl.col("v24").is_not_null() & pl.col("v168").is_not_null()
    )

    train_lot_ids = sorted(train_series["lot_id"].unique().to_list())
    groups: dict[tuple[str, str], GroupCalibration] = {}
    residuals_l1: dict[str, list[float]] = {}
    residuals_l2: list[float] = []

    for (component_type, parameter), part in train_series.group_by(
        ["component_type", "parameter"], maintain_order=True
    ):
        key = (str(component_type), str(parameter))
        v0 = part["v0"].to_list()
        v24 = part["v24"].to_list()
        v168 = part["v168"].to_list()
        lots = part["lot_id"].to_list()
        estimate = shape_core.estimate_phi(v0, v24, v168, lots, train_lot_ids, "empirical")
        groups[key] = GroupCalibration(
            component_type=key[0],
            parameter=key[1],
            phi_168=estimate.phi_168,
            family=estimate.family,
            family_param=estimate.family_param,
            n_phi_used=estimate.n_used,
            phi_warning=estimate.warning,
        )

    lot_median_v0 = (
        calib_series.group_by(["lot_id", "component_type", "parameter"])
        .agg(pl.col("v0").median().alias("lot_median_v0"))
        .rename({"lot_median_v0": "median_v0"})
    )
    calib_enriched = calib_series.join(
        lot_median_v0, on=["lot_id", "component_type", "parameter"], how="left"
    )
    for row in calib_enriched.iter_rows(named=True):
        key = (str(row["component_type"]), str(row["parameter"]))
        group = groups.get(key)
        if group is None or group.phi_168 is None:
            continue
        v0c = float(row["v0"])
        v24c = float(row["v24"])
        point = v0c + (v24c - v0c) * float(group.phi_168)
        residual = float(row["v168"]) - point
        group.residuals_l0.append(residual)
        group.calib_v0.append(v0c)
        group.calib_delta24.append(v24c - v0c)
        if row["median_v0"] is not None:
            group.calib_lot_medians.append(float(row["median_v0"]))
        temps = [value for value in (row.get("temp0"), row.get("temp24")) if value is not None]
        if temps:
            group.calib_temperatures.append(float(sum(temps) / len(temps)))
        if row.get("tester_id"):
            group.calib_tester_ids.append(str(row["tester_id"]))
        residuals_l1.setdefault(key[1], []).append(residual)
        residuals_l2.append(residual)

    for group in groups.values():
        if not group.calib_lot_medians:
            group.calib_lot_medians = list(group.calib_v0[:50])
        group.calib_tester_ids = sorted(set(group.calib_tester_ids))

    content = hashlib.sha256()
    for key in sorted(groups):
        group = groups[key]
        content.update(f"{key[0]}/{key[1]}:{group.phi_168}:{group.n_phi_used}".encode())
    digest8 = content.hexdigest()[:8]
    versions = {"drift_shape": f"prov-{digest8}", "conformal": f"prov-{digest8}"}
    return Calibration(
        groups=groups,
        residuals_l1=residuals_l1,
        residuals_l2=residuals_l2,
        group_keys=[f"{ctype}/{param}" for ctype, param in sorted(groups)],
        train_hash=train_hash,
        calib_hash=calib_hash,
        code_sha=code_info().git_sha,
        created_at=utc_now_z(),
        model_versions=versions,
    )


def generated_data_dir() -> Path:
    """Committed artifact directory (``data/generated`` at the repo root)."""
    here = Path(__file__).resolve()
    for candidate in [here.parents[2] / "data" / "generated", Path("data/generated")]:
        if (candidate / CALIB_NAME).exists():
            return candidate
    return Path("data/generated")


def ensure_calibration(state: Any) -> Calibration:
    """Return the cached calibration, building it once on first use."""
    cached = state.calibration
    if cached is not None:
        return cached  # type: ignore[no-any-return]
    calibration = build_calibration(generated_data_dir())
    state.calibration = calibration
    return calibration


def calibration_manifest(calibration: Calibration) -> dict[str, Any]:
    """JSON-safe manifest for ``/models`` and health responses."""
    return {
        "train_hash": calibration.train_hash,
        "calib_hash": calibration.calib_hash,
        "code_sha": calibration.code_sha,
        "created_at": calibration.created_at,
        "model_versions": dict(calibration.model_versions),
        "groups": [
            {
                "group": f"{key[0]}/{key[1]}",
                "phi_168": group.phi_168,
                "family": group.family,
                "n_phi_used": group.n_phi_used,
                "n_cal": len(group.residuals_l0),
                "warning": group.phi_warning,
            }
            for key, group in sorted(calibration.groups.items())
        ],
        "provisional": True,
        "note": "Runtime calibration from committed train/calib artifacts;"
        " replaced by the T-401 registry when it lands. Never reads test.parquet.",
    }


def load_manifest_hashes() -> dict[str, str]:
    """Content hashes from the committed generator manifest (informational)."""
    manifest_path = generated_data_dir() / MANIFEST_NAME
    if not manifest_path.exists():
        return {}
    try:
        document: dict[str, Any] = json.loads(manifest_path.read_text())
    except (OSError, ValueError):
        return {}
    hashes = document.get("file_hashes", {})
    return (
        {str(name): str(value) for name, value in hashes.items()}
        if isinstance(hashes, dict)
        else {}
    )
