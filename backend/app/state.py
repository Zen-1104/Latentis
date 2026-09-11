"""Application-scoped runtime state (Phase 5, T-502).

Holds everything the routers need beyond the request: the DuckDB store,
the profile store, the active dataset/profile selection, the provisional
drift calibration cache, and the per-payload analysis cache.

Test isolation: ``create_app(state)`` accepts an explicit state, so
tests build ``AppState(db_path=":memory:")`` and never share storage
with each other or with the demo database.
"""

from __future__ import annotations

import os
from typing import Any, Final

from backend.app.errors import ApiError
from backend.db import Store
from backend.services.profiles import DEFAULT_PROFILE_ID, ProfileStore, ScreeningProfile

_DEFAULT_DB_PATH: Final[str] = "backend/data/latentis.duckdb"
_DB_ENV_VAR: Final[str] = "LATENTIS_DB_PATH"


def resolve_db_path(explicit: str | None = None) -> str:
    """Choose the DuckDB path: explicit, environment, then the default."""
    if explicit is not None:
        return explicit
    return os.environ.get(_DB_ENV_VAR, _DEFAULT_DB_PATH)


class AppState:
    """Mutable-but-scoped service hub for one FastAPI application."""

    def __init__(self, db_path: str | None = None) -> None:
        resolved = resolve_db_path(db_path)
        if resolved != ":memory:":
            directory = os.path.dirname(resolved)
            if directory:
                os.makedirs(directory, exist_ok=True)
        self.store = Store(resolved)
        self.profiles = ProfileStore(self.store)
        self.active_dataset_hash: str | None = None
        default = self.profiles.latest(DEFAULT_PROFILE_ID)
        self.active_profile_id: str | None = None
        self.active_profile_version: int | None = None
        self._default_profile = default
        self.calibration: Any | None = None
        self.investigation_cache: dict[str, Any] = {}
        # A restarted service must come back up on the data it already holds.
        self.restore_active_selection()

    def restore_active_selection(self) -> bool:
        """Re-pin the most recently ingested dataset and the profile it used.

        The selection used to live only in memory: it was set when a dataset
        was ingested and lost on every restart. A restarted service therefore
        still held every measurement in DuckDB while reporting ``degraded``
        with a null ``dataset_hash``, and answered 404 for every lot until
        somebody re-uploaded the identical file. Reading it back from the
        store makes a restart invisible.

        Ordering is ``created_at DESC, dataset_hash ASC``: the hash tie-break
        keeps the choice deterministic when two ingests share a timestamp, so
        one database always restores to the same dataset.

        Returns True when a dataset was pinned. An empty store leaves the
        selection unset, so a genuinely fresh service still reports
        ``degraded`` and names the dataset as missing rather than pretending
        to hold one.
        """
        row = self.store.fetchone(
            "SELECT dataset_hash, profile_id, profile_version FROM datasets"
            " ORDER BY created_at DESC, dataset_hash ASC LIMIT 1"
        )
        if row is None:
            return False

        profile_id, profile_version = str(row[1]), int(row[2])
        try:
            self.profiles.get(profile_id, profile_version)
        except ApiError:
            # A dataset naming a profile version the store no longer holds
            # must not take the service down on boot. Pin the dataset and let
            # `active_profile()` fall back to the seeded default, which is the
            # same behaviour as a fresh upload that names no profile.
            self.active_dataset_hash = str(row[0])
            return True

        self.active_dataset_hash = str(row[0])
        self.active_profile_id = profile_id
        self.active_profile_version = profile_version
        return True

    @property
    def default_profile(self) -> ScreeningProfile:
        """The seeded profile used when an upload names none."""
        return self._default_profile

    def set_active_dataset(self, dataset_hash: str) -> None:
        """Pin the working dataset (provenance travels in every ``meta``)."""
        self.active_dataset_hash = dataset_hash
        self.investigation_cache.clear()

    def set_active_profile(self, profile_id: str, version: int) -> None:
        """Pin the working profile version."""
        self.active_profile_id = profile_id
        self.active_profile_version = version
        self.investigation_cache.clear()

    def active_profile(self) -> ScreeningProfile:
        """The pinned profile, falling back to the seeded default."""
        if self.active_profile_id is not None and self.active_profile_version is not None:
            return self.profiles.get(self.active_profile_id, self.active_profile_version)
        return self._default_profile

    def reset(self) -> None:
        """Clear selections and caches (tests only; storage is separate)."""
        self.active_dataset_hash = None
        self.active_profile_id = None
        self.active_profile_version = None
        self.calibration = None
        self.investigation_cache.clear()

    def close(self) -> None:
        """Release the backing store."""
        self.store.close()
