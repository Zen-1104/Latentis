"""Contract test for the meta envelope (FR-602, TEST-API-002).

Oracle: the full ``meta`` envelope on the representative decision and
introspection routes. Exhaustive GET enumeration lives in
``test_api_provenance.py``; this module pins the registered path.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.state import AppState
from backend.tests.integration._fixtures import csv_bytes, fixture_rows

META_KEYS = {
    "request_id",
    "computed_at",
    "dataset_hash",
    "profile_id",
    "profile_version",
    "model_versions",
    "data_provenance",
    "code_git_sha",
    "duration_ms",
}


@pytest.fixture()
def client() -> Iterator[TestClient]:
    state = AppState(db_path=":memory:")
    app = create_app(state)
    with TestClient(app) as handle:
        response = handle.post(
            "/api/v1/datasets",
            files={"file": ("escape.csv", csv_bytes(fixture_rows()), "text/csv")},
        )
        assert response.status_code == 200, response.text
        yield handle
    state.close()


@pytest.mark.fast
def test_meta_envelope_on_every_response(client: TestClient) -> None:
    """TEST-API-002: every response carries the non-trimmable meta."""
    routes = [
        "/api/v1/healthz",
        "/api/v1/version",
        "/api/v1/datasets",
        "/api/v1/profiles",
        "/api/v1/components",
        "/api/v1/components/C-T-ESC-01",
        "/api/v1/components/C-T-ESC-01/investigation",
        "/api/v1/lots",
        "/api/v1/lots/L-T-001/statistics",
        "/api/v1/lots/L-T-001/disposition",
        "/api/v1/lots/L-T-001/distribution",
        "/api/v1/posture",
        "/api/v1/formulas",
        "/api/v1/models",
        "/api/v1/models/coverage",
    ]
    for route in routes:
        payload: dict[str, Any] = client.get(route).json()
        assert META_KEYS <= set(payload["meta"]), route
        assert payload["meta"]["data_provenance"] == "SYNTHETIC", route
