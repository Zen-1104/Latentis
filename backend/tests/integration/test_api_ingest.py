"""Contract tests for the T-502 dataset HTTP surface (FR-101, FR-602/603).

Oracle: TEST-API-003 — an uploaded fixture must be retrievable with an
identical row count and identical content hash, through live HTTP.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.state import AppState
from backend.tests.integration.test_ingest import BASE_ROWS, _csv_bytes


@pytest.fixture()
def client() -> Iterator[TestClient]:
    state = AppState(db_path=":memory:")
    app = create_app(state)
    with TestClient(app) as handle:
        yield handle
    state.close()


def _upload(client: TestClient, name: str = "fixture.csv") -> dict[str, Any]:
    response = client.post(
        "/api/v1/datasets", files={"file": (name, _csv_bytes(BASE_ROWS), "text/csv")}
    )
    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    return payload


@pytest.mark.fast
def test_upload_roundtrip(client: TestClient) -> None:
    """TEST-API-003: upload ⇒ retrievable manifest with identical counts and hash."""
    payload = _upload(client)
    data = payload["data"]
    assert data["rows_accepted"] == 12
    dataset_hash = data["dataset_hash"]

    listing = client.get("/api/v1/datasets").json()
    assert listing["meta"]["data_provenance"] == "SYNTHETIC"
    entries = listing["data"]
    assert len(entries) == 1
    assert entries[0]["dataset_hash"] == dataset_hash
    assert entries[0]["rows_accepted"] == 12

    manifest = client.get(f"/api/v1/datasets/{dataset_hash}").json()
    assert manifest["data"]["dataset_hash"] == dataset_hash
    assert manifest["data"]["row_counts"]["accepted"] == 12
    assert manifest["meta"]["dataset_hash"] == dataset_hash


@pytest.mark.fast
def test_unknown_dataset_is_structured_404(client: TestClient) -> None:
    """Invalid request: UNKNOWN_DATASET with remediation, never 500."""
    response = client.get("/api/v1/datasets/sha256:nope")
    assert response.status_code == 404
    error_body: dict[str, Any] = response.json()["error"]
    assert error_body["code"] == "UNKNOWN_DATASET"
    assert error_body["remediation"]
    assert error_body["request_id"]


@pytest.mark.fast
def test_rejected_file_is_422_with_itemised_details(client: TestClient) -> None:
    """FR-102 over HTTP: total rejection is 422, row-and-column-precise."""
    rows = [{**row, "measurement_unit": "furlongs"} for row in BASE_ROWS]
    response = client.post(
        "/api/v1/datasets", files={"file": ("bad.csv", _csv_bytes(rows), "text/csv")}
    )
    assert response.status_code == 422
    failed_body: dict[str, Any] = response.json()["error"]
    assert failed_body["code"] == "UNIT_MISMATCH"
    assert failed_body["details"]
    assert failed_body["remediation"]


@pytest.mark.fast
def test_validate_endpoint_rechecks_stored_data(client: TestClient) -> None:
    """POST /datasets/{hash}/validate passes on a clean ingest."""
    payload = _upload(client)
    dataset_hash = payload["data"]["dataset_hash"]
    response = client.post(f"/api/v1/datasets/{dataset_hash}/validate")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["dataset_hash"] == dataset_hash
    assert data["passed"] is True
    assert data["findings"] == []


@pytest.mark.fast
def test_health_reflects_ingested_dataset(client: TestClient) -> None:
    """Health carries the dataset hash once ingested; models still absent."""
    payload = _upload(client)
    health = client.get("/api/v1/healthz").json()
    assert health["data"]["dataset_hash"] == payload["data"]["dataset_hash"]
    assert health["data"]["profile_id"] == "mil_std_883_like"
    assert health["data"]["status"] == "degraded"
    assert health["meta"]["dataset_hash"] == payload["data"]["dataset_hash"]
