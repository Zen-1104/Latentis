"""Adversarial coverage for the Phase 5 API surface (T-503).

Oracles: INV-2 (no verdict may depend on an identifier), FR-603 (no 500
for malformed input), and the refusal-state discipline (None/NaN/inf
never coerce into a decision). All assertions are behavioural.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.state import AppState
from backend.tests.integration._fixtures import _row, csv_bytes


@pytest.fixture()
def client() -> Iterator[TestClient]:
    state = AppState(db_path=":memory:")
    app = create_app(state)
    with TestClient(app) as handle:
        yield handle
    state.close()


def _upload(client: TestClient, rows: list[dict[str, Any]], name: str = "f.csv") -> Any:
    return client.post("/api/v1/datasets", files={"file": (name, csv_bytes(rows), "text/csv")})


def _good_rows(prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(1, 6):
        cid = f"{prefix}-{index:02d}"
        rows.append(_row(cid, "L-ADV", "iddq_standby", 0, 10.0 + index * 0.2, "uA"))
        rows.append(_row(cid, "L-ADV", "iddq_standby", 24, 10.5 + index * 0.2, "uA"))
    return rows


@pytest.mark.fast
def test_nan_and_infinite_values_rejected_not_coerced(client: TestClient) -> None:
    """None/NaN/inf never become 0 or enter a decision input."""
    rows = _good_rows("C-N")
    rows[0] = {**rows[0], "measurement_value": "nan"}
    rows[1] = {**rows[1], "measurement_value": "inf"}
    rows[2] = {**rows[2], "measurement_value": "-inf"}
    report: dict[str, Any] = _upload(client, rows).json()["data"]
    assert report["rows_rejected"] == 3
    assert report["rejection_classes"]["RANGE"] == 3
    stored = client.app.state.app_state.store.fetchall(  # type: ignore[attr-defined]
        "SELECT value FROM measurements WHERE dataset_hash = ?", [report["dataset_hash"]]
    )
    assert all(value[0] == value[0] and abs(value[0]) != float("inf") for value in stored)


@pytest.mark.fast
def test_malformed_uploads_are_422_never_500(client: TestClient) -> None:
    """FR-603/TEST-API-005: every malformed input is a 4xx with remediation."""
    cases = [
        ("empty.csv", b"", "text/csv"),
        ("notes.txt", b"hello", "text/plain"),
        ("fake.parquet", b"PAR1-not-really", "application/octet-stream"),
        ("noext", b"a,b\n1,2\n", "text/csv"),
    ]
    for name, payload, content_type in cases:
        response = client.post("/api/v1/datasets", files={"file": (name, payload, content_type)})
        assert response.status_code in (404, 422), (name, response.text)
        body: dict[str, Any] = response.json()["error"]
        assert body["code"] in (
            "VALIDATION_FAILED",
            "UNIT_MISMATCH",
            "UNKNOWN_COMPONENT",
            "UNKNOWN_LOT",
            "UNKNOWN_DATASET",
            "UNKNOWN_PROFILE",
            "INSUFFICIENT_COHORT",
            "INSUFFICIENT_DATA",
            "INSUFFICIENT_CALIBRATION",
            "NO_VARIATION",
            "MODEL_UNAVAILABLE",
            "PROFILE_IMMUTABLE",
            "REASON_REQUIRED",
            "NOT_FOUND",
        )
        assert body["request_id"]


@pytest.mark.fast
def test_error_enum_closed_over_unknown_resources(client: TestClient) -> None:
    """Unknown ids across surfaces map to the closed enum (TEST-API-004 lite)."""
    assert client.get("/api/v1/components/C-X").status_code == 404
    assert client.get("/api/v1/lots/L-X/statistics").status_code == 404
    assert client.get("/api/v1/datasets/sha256:x").status_code == 404
    assert client.get("/api/v1/profiles/px").status_code == 404
    assert client.get("/api/v1/formulas/fx").status_code == 404
    bad_action = client.post(
        "/api/v1/components/C-X/disposition", json={"action": "MAYBE", "reason": "x"}
    )
    assert bad_action.status_code == 422
    assert bad_action.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.fast
def test_id_permutation_leaves_verdicts_unchanged() -> None:
    """INV-2/RT-004: verdicts depend on values, never on identifiers."""
    first = AppState(db_path=":memory:")
    second = AppState(db_path=":memory:")
    try:
        from backend.services import ingest as ingest_service
        from backend.services.calibration import build_calibration, generated_data_dir
        from backend.services.investigation import Investigator
        from backend.services.profiles import default_profile

        rows_a = _good_rows("C-PERM-A")
        rows_b = [
            {**row, "component_id": row["component_id"].replace("C-PERM-A", "C-PERM-B")}
            for row in rows_a
        ]
        profile = default_profile()
        report_a = ingest_service.ingest_payload(first.store, csv_bytes(rows_a), "a.csv", profile)
        report_b = ingest_service.ingest_payload(second.store, csv_bytes(rows_b), "b.csv", profile)
        calibration = build_calibration(generated_data_dir())
        first.calibration = calibration
        second.calibration = calibration
        inv_a = Investigator(first, profile, calibration, report_a.dataset_hash)
        inv_b = Investigator(second, profile, calibration, report_b.dataset_hash)
        for index in range(1, 6):
            out_a = inv_a.assemble(f"C-PERM-A-{index:02d}")
            out_b = inv_b.assemble(f"C-PERM-B-{index:02d}")
            assert [block["severity"] for block in out_a["parameters"]] == [
                block["severity"] for block in out_b["parameters"]
            ]
            assert [block["band"] for block in out_a["parameters"]] == [
                block["band"] for block in out_b["parameters"]
            ]
            assert out_a["worst"]["parameter"] == out_b["worst"]["parameter"]
            assert out_a["recommendation"] == out_b["recommendation"]
    finally:
        first.close()
        second.close()


@pytest.mark.fast
def test_single_part_lot_defers_without_500(client: TestClient) -> None:
    """Degenerate lot: INSUFFICIENT states in the payload, HTTP stays 200."""
    rows = [
        _row("C-SOLO", "L-SOLO", "iddq_standby", 0, 10.0, "uA"),
        _row("C-SOLO", "L-SOLO", "iddq_standby", 24, 10.5, "uA"),
    ]
    upload = _upload(client, rows, "solo.csv")
    assert upload.status_code == 200
    response = client.get("/api/v1/components/C-SOLO/investigation")
    assert response.status_code == 200
    data: dict[str, Any] = response.json()["data"]
    iddq = next(item for item in data["parameters"] if item["parameter"] == "iddq_standby")
    assert iddq["dpat"]["verdict"] == "INSUFFICIENT_COHORT"
    assert iddq["dpat"]["z"] is None
    stats = client.get("/api/v1/lots/L-SOLO/statistics").json()["data"]
    solo_stats = next(item for item in stats["parameters"] if item["parameter"] == "iddq_standby")
    assert solo_stats["refusal"] == "INSUFFICIENT_COHORT"
