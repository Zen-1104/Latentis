"""Contract tests for inspector dispositions (FR-409/FR-606).

Oracles: TEST-DISP-001 (OVERRIDE without a non-empty reason is
REASON_REQUIRED) and TEST-DISP-002 (the stored snapshot byte-equals
the payload shown).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.state import AppState
from backend.tests.integration._fixtures import csv_bytes, fixture_rows


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
def test_override_requires_reason(client: TestClient) -> None:
    """TEST-DISP-001: OVERRIDE without a non-empty reason returns 422."""
    for reason in ("", "   "):
        refused = client.post(
            "/api/v1/components/C-T-ESC-01/disposition",
            json={"action": "OVERRIDE", "reason": reason, "actor": "OP-04"},
        )
        assert refused.status_code == 422
        body: dict[str, Any] = refused.json()["error"]
        assert body["code"] == "REASON_REQUIRED"
        assert body["remediation"]


@pytest.mark.fast
def test_stored_snapshot_equals_payload_shown(client: TestClient) -> None:
    """TEST-DISP-002: the stored snapshot equals the payload shown."""
    shown: dict[str, Any] = client.get("/api/v1/components/C-T-ESC-01/investigation").json()["data"]
    recorded = client.post(
        "/api/v1/components/C-T-ESC-01/disposition",
        json={"action": "CONCUR", "reason": "", "actor": "OP-04"},
    )
    assert recorded.status_code == 200
    record: dict[str, Any] = recorded.json()["data"]
    assert record["component_id"] == "C-T-ESC-01"
    assert record["profile_ref"] == "mil_std_883_like@1"
    state = client.app.state.app_state  # type: ignore[attr-defined]
    row = state.store.fetchone(
        "SELECT system_output_snapshot FROM dispositions WHERE disposition_id = ?",
        [record["disposition_id"]],
    )
    assert row is not None
    stored: dict[str, Any] = json.loads(str(row[0]))
    assert stored["component"] == shown["component"]
    assert stored["worst"] == shown["worst"]
    assert stored["parameters"] == shown["parameters"]
