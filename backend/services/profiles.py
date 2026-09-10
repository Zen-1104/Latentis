"""Screening profiles as data, not code (Phase 5, T-502).

Implements FR-106 and API_CONTRACT.md section 5:

- A ``ScreeningProfile`` carries the read-point grid, stress condition,
  absolute limits, delta limits, PDA, ``k``, ``alpha``, ``margin_fraction``,
  ``Ea`` per parameter, and risk weights. Every value the scientific core
  needs as configuration arrives through here — no default lives in a
  route handler (backend-engineer charter).
- Versions are append-only. A version referenced by a persisted
  disposition is immutable: writing to it returns ``PROFILE_IMMUTABLE``
  (FR-607, TEST-PROF-001).

Provenance tags (``assumed`` vs ``derived``) follow PROJECT_MASTER_SPEC
KL-04/L-14: limits and ``Ea`` are configuration; ``k``/``alpha``/weights
are documented policy inputs.
"""

from __future__ import annotations

import json
from typing import Any, Final

from pydantic import BaseModel, Field

from backend.app.errors import ApiError, ErrorCode
from backend.app.runtime import utc_now_z
from backend.db import Store

DEFAULT_PROFILE_ID: Final[str] = "mil_std_883_like"

_PARAMETER_LIMITS: Final[dict[str, dict[str, Any]]] = {
    # Absolute limits denormalised from data/generated screening data
    # (profile configuration, KL-04 — not device truth).
    "iddq_standby": {"low": None, "high": 50.0, "unit": "uA", "delta_max": None, "ea_ev": 0.7},
    "leakage_input": {"low": None, "high": 100.0, "unit": "nA", "delta_max": None, "ea_ev": 0.7},
    "prop_delay": {"low": None, "high": 20.0, "unit": "ns", "delta_max": None, "ea_ev": 0.7},
    "vth_shift": {"low": -50.0, "high": 50.0, "unit": "mV", "delta_max": None, "ea_ev": 0.7},
    "icc_active": {"low": None, "high": 45.0, "unit": "mA", "delta_max": None, "ea_ev": 0.7},
    "output_res": {"low": None, "high": 100.0, "unit": "mOhm", "delta_max": None, "ea_ev": 0.7},
}


class ParameterLimit(BaseModel):
    """Absolute-limit configuration for one parameter (profile data)."""

    low: float | None = None
    high: float | None = None
    unit: str = Field(min_length=1)
    delta_max: float | None = None
    ea_ev: float = Field(gt=0, default=0.7)


class RiskWeightsConfig(BaseModel):
    """Worklist-ordering weights (policy inputs, RISK_SCORING_SPEC section 3)."""

    w_anomaly: float = 0.30
    w_drift: float = 0.30
    w_margin: float = 0.20
    w_quality: float = 0.10
    w_credit: float = 0.10


class ScreeningProfile(BaseModel):
    """Versioned screening configuration (FR-106, API_CONTRACT section 5)."""

    profile_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    k: float = Field(gt=0)
    alpha: float = Field(gt=0, lt=1)
    margin_fraction: float = Field(ge=0, lt=1)
    horizon_hours: float = Field(gt=0)
    pda_limit_pct: float = Field(gt=0)
    readpoint_grid: list[int] = Field(min_length=1)
    limits: dict[str, ParameterLimit]
    risk_weights: RiskWeightsConfig = Field(default_factory=RiskWeightsConfig)
    n_min_zone: int = Field(ge=3, default=20)
    provenance_note: str = Field(
        default="Limits, Ea, k, alpha, margin_fraction, PDA and weights are "
        "configuration (assumed), not device truth (KL-04)."
    )


def default_profile() -> ScreeningProfile:
    """Build the seeded ``mil_std_883_like`` version 1 (runtime data)."""
    return ScreeningProfile(
        profile_id=DEFAULT_PROFILE_ID,
        version=1,
        k=6.0,
        alpha=0.10,
        margin_fraction=0.20,
        horizon_hours=168.0,
        pda_limit_pct=5.0,
        readpoint_grid=[0, 24],
        limits={
            name: ParameterLimit(
                low=spec["low"],
                high=spec["high"],
                unit=str(spec["unit"]),
                delta_max=spec["delta_max"],
                ea_ev=float(spec["ea_ev"]),
            )
            for name, spec in _PARAMETER_LIMITS.items()
        },
    )


class ProfileStore:
    """Append-only profile versions over the DuckDB ``profiles`` table."""

    def __init__(self, store: Store) -> None:
        self._store = store
        self.ensure_default()

    def ensure_default(self) -> ScreeningProfile:
        """Seed the default profile version 1 when the table is empty."""
        existing = self._store.fetchone(
            "SELECT document_json FROM profiles WHERE profile_id = ? AND version = ?",
            [DEFAULT_PROFILE_ID, 1],
        )
        if existing is not None:
            return ScreeningProfile.model_validate_json(existing[0])
        profile = default_profile()
        self._store.execute(
            "INSERT INTO profiles (profile_id, version, document_json, created_at)"
            " VALUES (?, ?, ?, ?)",
            [profile.profile_id, profile.version, profile.model_dump_json(), utc_now_z()],
        )
        return profile

    def latest(self, profile_id: str) -> ScreeningProfile:
        """Return the newest version, or raise ``UNKNOWN_PROFILE``."""
        row = self._store.fetchone(
            "SELECT document_json FROM profiles WHERE profile_id = ?"
            " ORDER BY version DESC LIMIT 1",
            [profile_id],
        )
        if row is None:
            raise ApiError(
                ErrorCode.UNKNOWN_PROFILE,
                f"Unknown profile {profile_id!r}.",
                [{"profile_id": profile_id}],
            )
        return ScreeningProfile.model_validate_json(row[0])

    def get(self, profile_id: str, version: int) -> ScreeningProfile:
        """Return one exact version, or raise ``UNKNOWN_PROFILE``."""
        row = self._store.fetchone(
            "SELECT document_json FROM profiles WHERE profile_id = ? AND version = ?",
            [profile_id, version],
        )
        if row is None:
            raise ApiError(
                ErrorCode.UNKNOWN_PROFILE,
                f"Unknown profile {profile_id!r} version {version}.",
                [{"profile_id": profile_id, "version": version}],
            )
        return ScreeningProfile.model_validate_json(row[0])

    def list_versions(self, profile_id: str) -> list[int]:
        """All stored versions, oldest first."""
        rows = self._store.fetchall(
            "SELECT version FROM profiles WHERE profile_id = ? ORDER BY version ASC",
            [profile_id],
        )
        return [int(row[0]) for row in rows]

    def list_ids(self) -> list[str]:
        """Every known profile id."""
        rows = self._store.fetchall("SELECT DISTINCT profile_id FROM profiles ORDER BY 1")
        return [str(row[0]) for row in rows]

    def is_referenced(self, profile_id: str, version: int) -> bool:
        """True once a disposition or run pins this version (FR-607)."""
        disp = self._store.fetchone(
            "SELECT 1 FROM dispositions WHERE profile_id = ? AND profile_version = ? LIMIT 1",
            [profile_id, version],
        )
        if disp is not None:
            return True
        run = self._store.fetchone(
            "SELECT 1 FROM analysis_runs WHERE profile_id = ? AND profile_version = ? LIMIT 1",
            [profile_id, version],
        )
        return run is not None

    def create_version(self, profile_id: str, document: dict[str, Any]) -> ScreeningProfile:
        """Append a new version. Never mutates an existing row (FR-607)."""
        versions = self.list_versions(profile_id)
        if not versions:
            raise ApiError(
                ErrorCode.UNKNOWN_PROFILE,
                f"Unknown profile {profile_id!r}.",
                [{"profile_id": profile_id}],
            )
        cleaned = {key: value for key, value in document.items() if value is not None}
        cleaned.pop("version", None)
        profile = ScreeningProfile.model_validate(
            {**cleaned, "profile_id": profile_id, "version": max(versions) + 1}
        )
        self._store.execute(
            "INSERT INTO profiles (profile_id, version, document_json, created_at)"
            " VALUES (?, ?, ?, ?)",
            [profile.profile_id, profile.version, profile.model_dump_json(), utc_now_z()],
        )
        return profile

    def rewrite_version(
        self, profile_id: str, version: int, document: dict[str, Any]
    ) -> ScreeningProfile:
        """Refuse to mutate a referenced version (TEST-PROF-001).

        An unreferenced version may be replaced (draft correction); a
        referenced one returns ``PROFILE_IMMUTABLE`` and is left intact.
        """
        self.get(profile_id, version)
        if self.is_referenced(profile_id, version):
            raise ApiError(
                ErrorCode.PROFILE_IMMUTABLE,
                f"Profile {profile_id!r} version {version} is referenced and immutable.",
                [{"profile_id": profile_id, "version": version}],
            )
        cleaned = {key: value for key, value in document.items() if value is not None}
        profile = ScreeningProfile.model_validate(
            {**cleaned, "profile_id": profile_id, "version": version}
        )
        self._store.execute(
            "UPDATE profiles SET document_json = ? WHERE profile_id = ? AND version = ?",
            [profile.model_dump_json(), profile_id, version],
        )
        return profile

    def profile_document(self, profile: ScreeningProfile) -> dict[str, Any]:
        """JSON-safe document for API responses."""
        document: dict[str, Any] = json.loads(profile.model_dump_json())
        return document
