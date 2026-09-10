"""Integration tests for the T-501 system surface (FR-601/602/603/605/606).

Oracle: behavioural contract over live HTTP through the real FastAPI app
(``fastapi.testclient.TestClient`` — no mocks, no stubbed core). Every
assertion is structural (envelope keys, status codes, degradation naming,
repeat equivalence), never a snapshot of a computed number.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.core.formulas import FORMULAS

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


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def _volatile_stripped(payload: dict[str, Any]) -> dict[str, Any]:
    scrubbed = {"data": payload["data"], "meta": dict(payload["meta"])}
    for key in ("request_id", "computed_at", "duration_ms"):
        scrubbed["meta"].pop(key, None)
    return scrubbed


@pytest.mark.fast
def test_healthz_envelope_and_degraded_names_missing_stores(client: TestClient) -> None:
    """Valid request: 200, full meta envelope, honest degraded naming T-502/T-401."""
    response = client.get("/api/v1/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"data", "meta"}
    assert META_KEYS <= set(payload["meta"])
    assert payload["meta"]["data_provenance"] == "SYNTHETIC"
    assert payload["meta"]["code_git_sha"]
    data = payload["data"]
    assert data["status"] == "degraded"
    assert data["dataset_hash"] is None
    assert data["models"] == {}
    assert data["profile_id"] is None
    joined_missing = " ".join(data["missing"])
    assert "T-502" in joined_missing
    assert "T-401" in joined_missing
    assert data["remediation"].strip()
    assert data["formula_registry"]["entries"] == len(FORMULAS)
    assert data["formula_registry"]["hash"].startswith("sha256:")


@pytest.mark.fast
def test_health_alias_agrees_with_healthz(client: TestClient) -> None:
    """API_CONTRACT § 3 path and TASKS.md path serve the same truth."""
    first = client.get("/api/v1/healthz").json()
    second = client.get("/api/v1/health").json()
    assert _volatile_stripped(first) == _volatile_stripped(second)


@pytest.mark.fast
def test_version_is_runtime_derived(client: TestClient) -> None:
    """Version carries the running code identity, not a committed literal."""
    payload = client.get("/api/v1/version").json()
    assert META_KEYS <= set(payload["meta"])
    data = payload["data"]
    assert data["service"] == "latentis"
    assert data["api_version"] == "v1"
    assert (
        data["code"]["git_sha"] == client.get("/api/v1/healthz").json()["data"]["code"]["git_sha"]
    )
    assert data["formula_registry"]["entries"] == len(FORMULAS)


@pytest.mark.fast
def test_openapi_document_serves_contract_paths(client: TestClient) -> None:
    """TEST-API-001 enabler: the generated OpenAPI 3.1 doc is served, not maintained."""
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert document["openapi"].startswith("3.1")
    assert "/api/v1/healthz" in document["paths"]
    assert "/api/v1/version" in document["paths"]


@pytest.mark.fast
def test_unknown_path_is_structured_404_not_500(client: TestClient) -> None:
    """Invalid request: envelope error with request_id and remediation; never 500."""
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    payload = response.json()
    assert set(payload) == {"error"}
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["details"] == [{"path": "/api/v1/does-not-exist"}]
    assert payload["error"]["remediation"]
    assert payload["error"]["request_id"]


@pytest.mark.fast
def test_repeat_requests_are_deterministically_equivalent(client: TestClient) -> None:
    """FR-604: identical input ⇒ identical body modulo volatile metadata."""
    first = client.get("/api/v1/healthz").json()
    second = client.get("/api/v1/healthz").json()
    assert first["meta"]["request_id"] != second["meta"]["request_id"]
    assert _volatile_stripped(first) == _volatile_stripped(second)


@pytest.mark.fast
def test_request_id_header_round_trips(client: TestClient) -> None:
    """A caller-supplied request id is honoured in meta and echoed in headers."""
    response = client.get("/api/v1/healthz", headers={"X-Request-ID": "caller-123"})
    assert response.status_code == 200
    assert response.json()["meta"]["request_id"] == "caller-123"
    assert response.headers["X-Request-ID"] == "caller-123"
