"""Integration tests for T-504 distribution, posture, and reports.

Oracles: TEST-REP-001 (appendix covers every payload formula exactly),
TEST-REP-002 (synthetic banner on page one and in the footer), plus the
distribution/posture behavioural contracts. PDF assertions degrade
honestly when Chromium is absent.
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
def test_distribution_bins_limits_and_flagged_members(client: TestClient) -> None:
    """The S2 payload partitions the cohort with limits and flags the escape."""
    data: dict[str, Any] = client.get("/api/v1/lots/L-T-001/distribution").json()["data"]
    assert data["lot_id"] == "L-T-001"
    iddq = next(item for item in data["parameters"] if item["parameter"] == "iddq_standby")
    assert iddq["n"] == 9
    assert iddq["cohort_mode"] == "cohort"
    assert sum(bucket["count"] for bucket in iddq["bins"]) == 9
    assert iddq["limit_high"] is not None
    assert iddq["limit_high"]["formula_id"] == "dpat.limit_high_v1"
    assert iddq["median"]["formula_id"] == "robust.median_v1"
    escape = next(item for item in iddq["members"] if item["component_id"] == "C-T-ESC-01")
    assert escape["flagged"] is True
    assert escape["z"] > 6.0
    nominal = next(item for item in iddq["members"] if item["component_id"] == "C-T-002")
    assert nominal["flagged"] is False
    unknown = client.get("/api/v1/lots/L-NOPE/distribution")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "UNKNOWN_LOT"


@pytest.mark.fast
def test_posture_reports_risk_configuration(client: TestClient) -> None:
    """S5 data: posture parameters with model identity, computed nowhere."""
    data: dict[str, Any] = client.get("/api/v1/posture").json()["data"]
    assert data["profile_id"] == "mil_std_883_like"
    posture = data["mission_risk_posture"]
    assert posture["alpha"] == 0.10
    assert posture["k"] == 6.0
    assert posture["margin_fraction"] == 0.20
    assert posture["pda_limit_pct"] == 5.0
    assert data["risk_weights"]["w_anomaly"] == 0.30
    assert data["model_versions"]
    assert data["dataset_hash"]
    assert data["data_provenance"] == "SYNTHETIC"


@pytest.mark.fast
def test_provenance_appendix_lists_every_formula_used(client: TestClient) -> None:
    """TEST-REP-001: appendix rows equal the payload formula set exactly."""
    created: dict[str, Any] = client.post(
        "/api/v1/reports",
        json={"scope": "component", "target_id": "C-T-ESC-01", "format": "html"},
    ).json()["data"]
    report: dict[str, Any] = client.get(f"/api/v1/reports/{created['report_id']}").json()["data"]
    html: str = report["html"]
    investigation: dict[str, Any] = client.get(
        "/api/v1/components/C-T-ESC-01/investigation"
    ).json()["data"]
    payload_formulas = {item["formula_id"] for item in investigation["provenance"]["formulas_used"]}
    assert payload_formulas
    for formula_id in payload_formulas:
        assert formula_id in html, formula_id
    assert investigation["worst"]["severity"] in html
    assert report["scope"] == "component"
    assert report["data_provenance"] == "SYNTHETIC"


@pytest.mark.fast
def test_synthetic_banner_on_page_1_and_every_footer(client: TestClient) -> None:
    """TEST-REP-002 (HTML leg): the banner opens the page and closes it."""
    created: dict[str, Any] = client.post(
        "/api/v1/reports",
        json={"scope": "component", "target_id": "C-T-ESC-01", "format": "html"},
    ).json()["data"]
    html: str = client.get(f"/api/v1/reports/{created['report_id']}").json()["data"]["html"]
    banner = "SYNTHETIC DATA — NOT ISRO OPERATIONAL DATA"
    first = html.find(banner)
    last = html.rfind(banner)
    assert first != -1 and last != -1 and last > first
    assert first < len(html) // 4


@pytest.mark.fast
def test_lot_report_queue_and_disposition(client: TestClient) -> None:
    """Lot reports carry the queue, the PDA roll-up, and the appendix."""
    created: dict[str, Any] = client.post(
        "/api/v1/reports", json={"scope": "lot", "target_id": "L-T-001", "format": "html"}
    ).json()["data"]
    report: dict[str, Any] = client.get(f"/api/v1/reports/{created['report_id']}").json()["data"]
    html: str = report["html"]
    assert "C-T-ESC-01" in html
    assert "lot.pda_pct_v1" in html
    assert "SYNTHETIC DATA — NOT ISRO OPERATIONAL DATA" in html
    bad_scope = client.post(
        "/api/v1/reports", json={"scope": "fleet", "target_id": "L-T-001", "format": "html"}
    )
    assert bad_scope.status_code == 422
    unknown = client.post(
        "/api/v1/reports", json={"scope": "lot", "target_id": "L-NOPE", "format": "html"}
    )
    assert unknown.status_code == 404
    missing = client.get("/api/v1/reports/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.fast
def test_pdf_degrades_honestly_without_chromium(client: TestClient) -> None:
    """No Chromium here: the PDF leg is 503 naming the renderer, HTML stands."""
    created: dict[str, Any] = client.post(
        "/api/v1/reports",
        json={"scope": "component", "target_id": "C-T-ESC-01", "format": "pdf"},
    ).json()["data"]
    response = client.get(f"/api/v1/reports/{created['report_id']}/pdf")
    try:
        import playwright  # type: ignore[import-not-found]  # noqa: F401

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
    except ImportError:
        assert response.status_code == 503
        body: dict[str, Any] = response.json()["error"]
        assert body["code"] == "MODEL_UNAVAILABLE"
        assert "Chromium" in body["message"]
