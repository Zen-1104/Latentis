"""A restart must not empty a service that still holds the data.

The active dataset selection used to live only in ``AppState`` memory: it was
set by the ingest handler and lost on every restart. The consequence was a
service holding every measurement in DuckDB while reporting ``degraded`` with
a null ``dataset_hash`` and answering 404 for every lot, until an operator
re-uploaded the byte-identical file. These tests pin the restored behaviour.

A file-backed database is required — ``:memory:`` cannot outlive the process
it belongs to, which is precisely the thing under test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.state import AppState
from backend.tests.integration.test_ingest import BASE_ROWS, _csv_bytes


def _upload(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/v1/datasets",
        files={"file": ("fixture.csv", _csv_bytes(BASE_ROWS), "text/csv")},
    )
    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()["data"]
    return payload


def test_active_dataset_survives_a_restart(tmp_path: Path) -> None:
    """TEST-API-003 extension: a second process on the same file is ready."""
    db = str(tmp_path / "restart.duckdb")

    first = AppState(db_path=db)
    app = create_app(first)
    with TestClient(app) as client:
        report = _upload(client)
        expected_hash = report["dataset_hash"]
        health = client.get("/api/v1/healthz").json()["data"]
        assert health["dataset_hash"] == expected_hash
        # `status` may be "degraded" in a fresh database because no model
        # artifacts are registered (T-401); that is unrelated to the dataset,
        # so assert the dataset is not among the missing stores.
        assert not any("dataset" in item for item in health["missing"]), health["missing"]
    first.close()

    # A brand-new AppState on the same file stands in for the restart.
    second = AppState(db_path=db)
    try:
        assert second.active_dataset_hash == expected_hash
        assert second.active_profile_id == report["profile_id"]
        assert second.active_profile_version == report["profile_version"]

        app2 = create_app(second)
        with TestClient(app2) as client:
            health = client.get("/api/v1/healthz").json()["data"]
            assert health["dataset_hash"] == expected_hash
            assert not any("dataset" in item for item in health["missing"]), health["missing"]
            # The routes that 404ed before the fix now answer from stored data.
            lots = client.get("/api/v1/lots")
            assert lots.status_code == 200, lots.text
            assert len(lots.json()["data"]) > 0
    finally:
        second.close()


def test_empty_store_still_reports_degraded(tmp_path: Path) -> None:
    """Restoration must not invent a dataset where none was ever ingested."""
    state = AppState(db_path=str(tmp_path / "empty.duckdb"))
    try:
        assert state.active_dataset_hash is None
        assert state.restore_active_selection() is False

        app = create_app(state)
        with TestClient(app) as client:
            health = client.get("/api/v1/healthz").json()["data"]
            assert health["status"] == "degraded"
            assert health["dataset_hash"] is None
            assert any("dataset" in item for item in health["missing"])
    finally:
        state.close()


def test_restore_is_deterministic_across_repeated_loads(tmp_path: Path) -> None:
    """The same database must always restore to the same dataset."""
    db = str(tmp_path / "determinism.duckdb")
    first = AppState(db_path=db)
    app = create_app(first)
    with TestClient(app) as client:
        expected = _upload(client)["dataset_hash"]
    first.close()

    seen = set()
    for _ in range(3):
        state = AppState(db_path=db)
        seen.add(state.active_dataset_hash)
        state.close()
    assert seen == {expected}
