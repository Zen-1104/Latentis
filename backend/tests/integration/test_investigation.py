"""Integration tests for the T-503 investigation surface.

Oracles: behavioural contract over live HTTP through the real FastAPI app
with a hand-built two-lot fixture. The escape part (C-T-ESC) pins the
flagship juxtaposition — ``dpat FAIL`` beside ``absolute PASS`` — from
fixture values, never from implementation output. Calibration comes from
the committed train/calib artifacts (read-only; test.parquet untouched).
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


def _investigation(client: TestClient, component_id: str = "C-T-ESC-01") -> dict[str, Any]:
    response = client.get(f"/api/v1/components/{component_id}/investigation")
    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    assert set(payload) == {"data", "meta"}
    assert payload["meta"]["data_provenance"] == "SYNTHETIC"
    data: dict[str, Any] = payload["data"]
    return data


@pytest.mark.fast
def test_escape_part_flags_lot_relative_while_passing_absolute(client: TestClient) -> None:
    """Flagship juxtaposition from fixture values: DPAT FAIL + absolute PASS."""
    data = _investigation(client)
    assert data["component"]["component_id"] == "C-T-ESC-01"
    iddq = next(item for item in data["parameters"] if item["parameter"] == "iddq_standby")
    assert iddq["dpat"]["verdict"] == "FAIL"
    assert iddq["absolute"]["verdict"] == "PASS"
    assert iddq["severity"] == "SEVERE"
    assert data["worst"]["parameter"] == "iddq_standby"
    assert data["worst"]["severity"] == "SEVERE"
    assert data["worst"]["selection_rule"].startswith("severity rank")


@pytest.mark.fast
def test_investigation_carries_traced_evidence_and_provenance(client: TestClient) -> None:
    """TracedValues, risk decomposition, narratives, and provenance travel together."""
    data = _investigation(client)
    iddq = next(item for item in data["parameters"] if item["parameter"] == "iddq_standby")
    limit_high = iddq["dpat"]["limit_high"]
    assert limit_high["formula_id"] == "dpat.limit_high_v1"
    assert limit_high["expression"] == "median + k * robust_sigma"
    assert set(limit_high["inputs"]) == {"median", "k", "robust_sigma"}
    assert iddq["dpat"]["z"]["formula_id"] == "dpat.z_v1"
    risk = data["risk"]
    assert risk["parameter"] == "iddq_standby"
    assert risk["risk_index"]["formula_id"] == "risk.total_v1"
    names = {item["name"] for item in risk["components"]}
    assert names == {"anomaly", "drift", "margin", "quality", "attribution_credit"}
    assert risk["sum_check"]["tolerance"] == 1e-9
    assert abs(risk["sum_check"]["abs_diff"]) <= 1e-9
    assert "arithmetic" in data["explanation"]["layers"]
    assert data["explanation"]["counterfactuals"]["k_sensitivity"]["k_star"] > 6.0
    assert data["provenance"]["data_provenance"] == "SYNTHETIC"
    assert data["provenance"]["profile_ref"] == "mil_std_883_like@1"
    assert data["provenance"]["formulas_used"]
    assert data["recommendation"]["action"]
    assert data["recommendation"]["severity"] == "SEVERE"


@pytest.mark.fast
def test_unknown_component_is_structured_404(client: TestClient) -> None:
    """Invalid request: UNKNOWN_COMPONENT with remediation, never 500."""
    response = client.get("/api/v1/components/C-NOPE/investigation")
    assert response.status_code == 404
    body: dict[str, Any] = response.json()["error"]
    assert body["code"] == "UNKNOWN_COMPONENT"
    assert body["remediation"]
    assert body["request_id"]


@pytest.mark.fast
def test_repeat_investigation_is_deterministic(client: TestClient) -> None:
    """FR-604: identical input gives identical body modulo volatile metadata."""
    first = client.get("/api/v1/components/C-T-ESC-01/investigation").json()
    second = client.get("/api/v1/components/C-T-ESC-01/investigation").json()
    assert first["meta"]["request_id"] != second["meta"]["request_id"]

    def scrubbed(payload: dict[str, Any]) -> dict[str, Any]:
        body = {"data": payload["data"], "meta": dict(payload["meta"])}
        for key in ("request_id", "computed_at", "duration_ms"):
            body["meta"].pop(key, None)
        return body

    assert scrubbed(first) == scrubbed(second)


@pytest.mark.fast
def test_component_directory_and_filters(client: TestClient) -> None:
    """GET /components lists metadata with stable pagination."""
    page = client.get("/api/v1/components?limit=5").json()["data"]
    assert len(page["items"]) == 5
    assert page["next_cursor"] == "5"
    second = client.get("/api/v1/components?limit=5&cursor=5").json()["data"]
    assert second["items"]
    assert {item["component_id"] for item in page["items"]}.isdisjoint(
        {item["component_id"] for item in second["items"]}
    )
    lot_page = client.get("/api/v1/components?lot_id=L-T-002").json()["data"]
    assert [item["component_id"] for item in lot_page["items"]] == ["C-T-101"]
    bad = client.get("/api/v1/components?cursor=nope")
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.fast
def test_anomaly_drift_explanation_projections_agree(client: TestClient) -> None:
    """The three views project the same assembled evidence (one pipeline)."""
    investigation = _investigation(client)
    anomaly = client.get("/api/v1/components/C-T-ESC-01/anomaly").json()["data"]
    drift = client.get("/api/v1/components/C-T-ESC-01/drift").json()["data"]
    explanation = client.get("/api/v1/components/C-T-ESC-01/explanation").json()["data"]
    assert anomaly["worst"] == investigation["worst"]
    assert drift["worst"] == investigation["worst"]
    assert explanation["worst"] == investigation["worst"]
    iddq_anomaly = next(
        item for item in anomaly["parameters"] if item["parameter"] == "iddq_standby"
    )
    assert iddq_anomaly["flagged"] is True
    assert iddq_anomaly["threshold"] is None
    assert "T-402" in iddq_anomaly["threshold_note"]


@pytest.mark.fast
def test_lots_directory_statistics_and_disposition(client: TestClient) -> None:
    """Lots list, cohort statistics with mode naming, and the PDA roll-up."""
    lots = client.get("/api/v1/lots").json()["data"]
    assert {entry["lot_id"] for entry in lots} == {"L-T-001", "L-T-002"}
    stats = client.get("/api/v1/lots/L-T-001/statistics").json()["data"]
    assert stats["cohort_mode"] == "cohort"
    iddq_stats = next(item for item in stats["parameters"] if item["parameter"] == "iddq_standby")
    assert iddq_stats["n"] == 9
    assert iddq_stats["median"] is not None
    loo = client.get("/api/v1/lots/L-T-001/statistics?for_component=C-T-ESC-01").json()["data"]
    assert loo["cohort_mode"] == "leave-one-out"
    iddq_loo = next(item for item in loo["parameters"] if item["parameter"] == "iddq_standby")
    assert iddq_loo["n"] == 8
    disposition = client.get("/api/v1/lots/L-T-001/disposition").json()["data"]
    assert disposition["n_tested"] == 9
    assert disposition["lot_verdict"] in ("PASS_LOT", "REVIEW", "FAIL_LOT")
    assert disposition["pda_pct"]["formula_id"] == "lot.pda_pct_v1"
    unknown = client.get("/api/v1/lots/L-NOPE/statistics")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "UNKNOWN_LOT"


@pytest.mark.fast
def test_lot_runs_persist_and_rank_queues(client: TestClient) -> None:
    """POST anomaly/drift runs store runs and return risk/band-ordered queues."""
    anomaly = client.post("/api/v1/lots/L-T-001/anomaly").json()["data"]
    assert anomaly["n_parts"] == 9
    assert anomaly["queue"][0]["component_id"] == "C-T-ESC-01"
    drift = client.post("/api/v1/lots/L-T-001/drift").json()["data"]
    assert drift["n_parts"] == 9
    state = client.app.state.app_state  # type: ignore[attr-defined]
    runs = state.store.fetchall(
        "SELECT kind, COUNT(*) FROM analysis_runs GROUP BY kind ORDER BY kind"
    )
    assert ("anomaly", 1) in [(row[0], row[1]) for row in runs]
    assert ("drift", 1) in [(row[0], row[1]) for row in runs]
    parts = state.store.fetchone("SELECT COUNT(*) FROM part_results")
    assert parts is not None and parts[0] > 0


@pytest.mark.fast
def test_formulas_and_models_surfaces(client: TestClient) -> None:
    """Registry and provisional calibration are introspectable (T-503)."""
    formulas = client.get("/api/v1/formulas").json()["data"]
    assert len(formulas) == 33
    entry = client.get("/api/v1/formulas/dpat.limit_high_v1").json()["data"]
    assert entry["expression"] == "median + k * robust_sigma"
    assert entry["source_ref"]
    assert entry["operands"] == ["median", "k", "robust_sigma"]
    unknown = client.get("/api/v1/formulas/nope.v1")
    assert unknown.status_code == 404
    models = client.get("/api/v1/models").json()["data"]
    assert models["manifest"]["provisional"] is True
    assert models["manifest"]["groups"]
    coverage = client.get("/api/v1/models/coverage").json()["data"]
    assert coverage["groups"]
    assert coverage["groups"][0]["measured_coverage"] is None
    shape = client.get("/api/v1/models/shape/CMOS_LOGIC/iddq_standby").json()["data"]
    assert shape["phi_168"] is not None
    assert len(shape["points"]) == 7
    assert shape["points"][3]["t_hours"] == 24.0
    assert shape["points"][3]["phi"] == 1.0
    bad_shape = client.get("/api/v1/models/shape/NOPE/nope")
    assert bad_shape.status_code == 404
