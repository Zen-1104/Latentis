"""Contract tests for DuckDB persistence (FR-606) and profiles (FR-607).

Oracles: TEST-DB-001 (fresh database yields the declared schema exactly),
TEST-PROV-005 (dispositions are append-only), TEST-PROF-001 (a referenced
profile version is immutable).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.state import AppState
from backend.db import Store
from backend.tests.integration.test_ingest import BASE_ROWS, _csv_bytes


@pytest.fixture()
def client() -> Iterator[TestClient]:
    state = AppState(db_path=":memory:")
    app = create_app(state)
    with TestClient(app) as handle:
        yield handle
    state.close()


@pytest.mark.fast
def test_schema_migrations_apply_to_an_empty_db() -> None:
    """TEST-DB-001: a fresh store exposes every declared table, empty."""
    store = Store(":memory:")
    try:
        for table in (
            "ingest_records",
            "datasets",
            "lots",
            "components",
            "measurements",
            "quality",
            "profiles",
            "analysis_runs",
            "part_results",
            "dispositions",
            "reports",
        ):
            assert store.count(table) == 0
    finally:
        store.close()


@pytest.mark.fast
def test_dispositions_are_append_only(client: TestClient) -> None:
    """TEST-PROV-005: no UPDATE/DELETE path exists to the dispositions table."""
    response = client.put("/api/v1/components/C-X/disposition", json={"action": "CONCUR"})
    assert response.status_code in (404, 405)
    response = client.delete("/api/v1/components/C-X/disposition")
    assert response.status_code in (404, 405)
    openapi = client.get("/api/v1/openapi.json").json()
    mutating = [
        path
        for path, item in openapi["paths"].items()
        if "disposition" in path and any(verb in item for verb in ("put", "delete", "patch"))
    ]
    assert mutating == []


@pytest.mark.fast
def test_ingest_persists_lots_components_measurements(client: TestClient) -> None:
    """Storage holds the normalised rows behind the report counts."""
    upload = client.post(
        "/api/v1/datasets", files={"file": ("f.csv", _csv_bytes(BASE_ROWS), "text/csv")}
    )
    dataset_hash = upload.json()["data"]["dataset_hash"]
    state = client.app.state.app_state  # type: ignore[attr-defined]
    lots = state.store.fetchall(
        "SELECT lot_id, n_parts FROM lots WHERE dataset_hash = ?", [dataset_hash]
    )
    assert lots == [("L-T-001", 6)]
    assert state.store.count("measurements") == 12
    quality = state.store.fetchall(
        "SELECT COUNT(*), MIN(score), MAX(score) FROM quality WHERE dataset_hash = ?",
        [dataset_hash],
    )
    assert quality[0][0] == 6
    assert 0.0 <= float(quality[0][1]) <= float(quality[0][2]) <= 1.0
