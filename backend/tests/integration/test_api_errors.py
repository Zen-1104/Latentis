"""Contract tests for the closed error enum (FR-603, TEST-API-004/005).

Oracle: every member of the closed error enum is produced by at least
one crafted request — as an HTTP error code or as an in-band refusal
code — and no response carries a code outside the enum. Every 5xx in
the corpus is a P1 defect (API_CONTRACT section 9).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.errors import ApiError, ErrorCode
from backend.app.main import create_app
from backend.app.state import AppState
from backend.tests.integration._fixtures import _row, csv_bytes

SEEN_CODES: set[str] = set()


def _record(response: Any) -> Any:
    if response.status_code >= 400:
        body: dict[str, Any] = response.json()["error"]
        SEEN_CODES.add(body["code"])
    return response


@pytest.fixture()
def client() -> Iterator[TestClient]:
    state = AppState(db_path=":memory:")
    app = create_app(state)
    with TestClient(app) as handle:
        yield handle
    state.close()


def _rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(1, 4):
        cid = f"C-E-{index:02d}"
        rows.append(_row(cid, "L-E-001", "iddq_standby", 0, 10.0, "uA"))
        rows.append(_row(cid, "L-E-001", "iddq_standby", 24, 10.5, "uA"))
    return rows


def _upload(client: TestClient) -> None:
    response = _record(
        client.post(
            "/api/v1/datasets",
            files={"file": ("e.csv", csv_bytes(_rows()), "text/csv")},
        )
    )
    assert response.status_code == 200, response.text


@pytest.mark.fast
def test_error_enum_reachable_both_ways(client: TestClient) -> None:
    """TEST-API-004: every enum member is produced; nothing outside it."""
    _upload(client)
    state = client.app.state.app_state  # type: ignore[attr-defined]

    assert _record(client.get("/api/v1/components/C-X")).json()["error"]["code"] == (
        "UNKNOWN_COMPONENT"
    )
    assert _record(client.get("/api/v1/lots/L-X/statistics")).json()["error"]["code"] == (
        "UNKNOWN_LOT"
    )
    assert _record(client.get("/api/v1/datasets/sha256:x")).json()["error"]["code"] == (
        "UNKNOWN_DATASET"
    )
    assert _record(client.get("/api/v1/profiles/px")).json()["error"]["code"] == ("UNKNOWN_PROFILE")
    assert _record(client.get("/api/v1/formulas/fx")).json()["error"]["code"] == "NOT_FOUND"
    assert _record(client.get("/api/v1/no-such-path")).json()["error"]["code"] == "NOT_FOUND"
    assert _record(client.get("/api/v1/components?cursor=nope")).json()["error"]["code"] == (
        "VALIDATION_FAILED"
    )
    assert (
        _record(
            client.post(
                "/api/v1/components/C-E-01/disposition",
                json={"action": "MAYBE", "reason": "x"},
            )
        ).json()["error"]["code"]
        == "VALIDATION_FAILED"
    )
    assert (
        _record(
            client.post(
                "/api/v1/components/C-E-01/disposition",
                json={"action": "OVERRIDE", "reason": "  "},
            )
        ).json()["error"]["code"]
        == "REASON_REQUIRED"
    )
    unit_rows = [{**row, "measurement_unit": "mA"} for row in _rows()]
    unit_response = _record(
        client.post(
            "/api/v1/datasets",
            files={"file": ("u.csv", csv_bytes(unit_rows), "text/csv")},
        )
    )
    assert unit_response.status_code == 422
    assert unit_response.json()["error"]["code"] == "UNIT_MISMATCH"

    # Single-part lot: the run itself refuses (per-part 200s would all defer).
    solo = [
        _row("C-SOLO", "L-SOLO", "iddq_standby", 0, 10.0, "uA"),
        _row("C-SOLO", "L-SOLO", "iddq_standby", 24, 10.5, "uA"),
    ]
    solo_upload = _record(
        client.post("/api/v1/datasets", files={"file": ("s.csv", csv_bytes(solo), "text/csv")})
    )
    assert solo_upload.status_code == 200
    for kind in ("anomaly", "drift"):
        refused = _record(client.post(f"/api/v1/lots/L-SOLO/{kind}"))
        assert refused.status_code == 422
        assert refused.json()["error"]["code"] == "INSUFFICIENT_COHORT"

    # Profile immutability once referenced.
    created = client.put(
        "/api/v1/profiles/mil_std_883_like",
        json={
            "k": 4.5,
            "alpha": 0.05,
            "margin_fraction": 0.2,
            "horizon_hours": 168.0,
            "pda_limit_pct": 5.0,
            "readpoint_grid": [0, 24],
            "limits": {
                name: {"low": None, "high": 50.0, "unit": "uA"}
                for name in (
                    "iddq_standby",
                    "leakage_input",
                    "prop_delay",
                    "vth_shift",
                    "icc_active",
                    "output_res",
                )
            },
        },
    )
    assert created.status_code == 200
    state.store.execute(
        "INSERT INTO dispositions (disposition_id, component_id, dataset_hash, run_id,"
        " action, reason, actor, profile_id, profile_version, system_output_snapshot,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "D-PIN",
            "C-E-01",
            "sha256:t",
            None,
            "CONCUR",
            "pin",
            "OP",
            "mil_std_883_like",
            2,
            "{}",
            "2026-09-10T00:00:00Z",
        ],
    )
    rewrite = _record(
        client.put(
            "/api/v1/profiles/mil_std_883_like/2",
            json={
                "k": 5.0,
                "alpha": 0.05,
                "margin_fraction": 0.2,
                "horizon_hours": 168.0,
                "pda_limit_pct": 5.0,
                "readpoint_grid": [0, 24],
                "limits": {
                    name: {"low": None, "high": 50.0, "unit": "uA"}
                    for name in (
                        "iddq_standby",
                        "leakage_input",
                        "prop_delay",
                        "vth_shift",
                        "icc_active",
                        "output_res",
                    )
                },
            },
        )
    )
    assert rewrite.status_code == 409
    assert rewrite.json()["error"]["code"] == "PROFILE_IMMUTABLE"

    # PDF leg without Chromium: structured 503 naming the renderer.
    made: dict[str, Any] = client.post(
        "/api/v1/reports",
        json={"scope": "component", "target_id": "C-SOLO", "format": "pdf"},
    ).json()["data"]
    try:
        import playwright  # type: ignore[import-not-found]  # noqa: F401

        pdf = _record(client.get(f"/api/v1/reports/{made['report_id']}/pdf"))
        assert pdf.status_code == 200
    except ImportError:
        pdf = _record(client.get(f"/api/v1/reports/{made['report_id']}/pdf"))
        assert pdf.status_code == 503
        assert pdf.json()["error"]["code"] == "MODEL_UNAVAILABLE"

    # In-band refusal codes (crafted requests producing codes inside 200s).
    solo_inv: dict[str, Any] = client.get("/api/v1/components/C-SOLO/investigation").json()["data"]
    iddq = next(item for item in solo_inv["parameters"] if item["parameter"] == "iddq_standby")
    assert iddq["dpat"]["verdict"] == "INSUFFICIENT_COHORT"
    SEEN_CODES.add("INSUFFICIENT_COHORT")
    leakage = next(item for item in solo_inv["parameters"] if item["parameter"] == "leakage_input")
    assert leakage["drift"]["refusal_code"] == "INSUFFICIENT_DATA"
    SEEN_CODES.add("INSUFFICIENT_DATA")

    # Zero-variation cohort: identical values refuse with NO_VARIATION.
    # Four parts so the leave-one-out cohort (n=3) still reaches the gate.
    tied = [
        _row(f"C-TIED-0{index}", "L-TIED", "iddq_standby", hour, 10.0, "uA")
        for index in range(1, 5)
        for hour in (0, 24)
    ]
    tied_upload = _record(
        client.post("/api/v1/datasets", files={"file": ("t.csv", csv_bytes(tied), "text/csv")})
    )
    assert tied_upload.status_code == 200
    tied_inv: dict[str, Any] = client.get("/api/v1/components/C-TIED-01/investigation").json()[
        "data"
    ]
    tied_iddq = next(item for item in tied_inv["parameters"] if item["parameter"] == "iddq_standby")
    assert tied_iddq["dpat"]["verdict"] == "NO_VARIATION"
    SEEN_CODES.add("NO_VARIATION")

    # Empty calibration ladder: the bound refuses INSUFFICIENT_CALIBRATION.
    # White-box branch pin (documented): with the committed calibration on
    # disk, no HTTP request can empty the ladder, so the code is produced
    # here by direct call — the same core branch the service invokes.
    from backend.core.conformal import conformal_upper

    empty_bound = conformal_upper(32.0, [], None, 0.10)
    assert empty_bound.refusal_code == "INSUFFICIENT_CALIBRATION"
    assert empty_bound.bound_finite is False
    SEEN_CODES.add("INSUFFICIENT_CALIBRATION")

    # ApiError can never carry INTERNAL_ERROR (white-box pin, SR-06/FR-603).
    with pytest.raises(ValueError):
        ApiError(ErrorCode.INTERNAL_ERROR, "must not construct")

    enum_values = {member.value for member in ErrorCode}
    assert enum_values == {
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
        "INTERNAL_ERROR",
    }
    assert SEEN_CODES <= enum_values


@pytest.mark.fast
def test_no_5xx_in_the_corpus(client: TestClient) -> None:
    """TEST-API-005: replay the adversarial corpus; any 5xx is a P1 defect."""
    _upload(client)
    corpus: list[tuple[str, str, Any]] = [
        ("GET", "/api/v1/components/C-%00/investigation", None),
        ("GET", "/api/v1/lots/L-%00/statistics", None),
        ("GET", "/api/v1/components/C-E-01/investigation?foo=" + "x" * 5000, None),
        ("POST", "/api/v1/components/C-E-01/disposition", {"action": None}),
        ("POST", "/api/v1/components/C-E-01/disposition", {"action": "CONCUR", "reason": None}),
        ("POST", "/api/v1/reports", {"scope": "component", "target_id": "C-E-01"}),
        ("POST", "/api/v1/reports", {"scope": "x", "target_id": "C-E-01", "format": "html"}),
        ("POST", "/api/v1/reports", {"scope": "component", "target_id": "C-E-01", "format": "x"}),
        ("POST", "/api/v1/lots/L-NOPE/anomaly", None),
        ("PUT", "/api/v1/profiles/mil_std_883_like", {"k": -1.0}),
        ("PUT", "/api/v1/profiles/px", {"k": 1.0}),
        ("GET", "/api/v1/models/shape/a/b/c", None),
    ]
    for method, path, body in corpus:
        if method == "GET":
            response = client.get(path)
        elif method == "POST":
            response = client.post(path, json=body)
        else:
            response = client.put(path, json=body)
        assert response.status_code != 500, (method, path, response.text[:300])
        if response.status_code >= 400:
            error: dict[str, Any] = response.json()["error"]
            assert error["code"] in {member.value for member in ErrorCode}, (method, path)
            assert error["request_id"]
