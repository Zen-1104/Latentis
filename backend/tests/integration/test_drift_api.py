"""Contract test for the drift baseline in API payloads (TEST-DRIFT-007).

Oracle: API_CONTRACT schema — ``baseline_linear`` is a required field
on every forecast object, so the naive comparison can never be quietly
dropped. Refusal states carry the field as null with a named reason.
"""

from __future__ import annotations

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
def test_baseline_linear_present_in_every_payload(client: TestClient) -> None:
    """TEST-DRIFT-007: the naive baseline can never be quietly dropped."""
    payload: dict[str, Any] = client.get("/api/v1/components/C-T-ESC-01/investigation").json()
    data: dict[str, Any] = payload["data"]
    for block in data["parameters"]:
        assert "baseline_linear" in block["drift"], block["parameter"]
        if block["parameter"] in ("iddq_standby", "prop_delay"):
            baseline = block["drift"]["baseline_linear"]
            assert baseline is not None, block["parameter"]
            assert baseline["formula_id"] == "forecast.baseline_linear_v1"
        elif block["parameter"] == "vth_shift":
            assert block["drift"]["baseline_linear"] == 5.5
            assert block["fully_traced"] is False
        else:
            assert block["drift"]["refusal_code"] == "INSUFFICIENT_DATA"
