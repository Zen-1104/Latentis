"""Contract tests for ScreeningProfile versioning (FR-106/FR-607).

Oracle: TEST-PROF-001 — a PUT against an already-referenced version
returns PROFILE_IMMUTABLE; reads serve the seeded default.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.state import AppState


@pytest.fixture()
def client() -> Iterator[TestClient]:
    state = AppState(db_path=":memory:")
    app = create_app(state)
    with TestClient(app) as handle:
        yield handle
    state.close()


def _profile_body() -> dict[str, object]:
    return {
        "k": 4.5,
        "alpha": 0.05,
        "margin_fraction": 0.2,
        "horizon_hours": 168.0,
        "pda_limit_pct": 5.0,
        "readpoint_grid": [0, 24],
        "limits": {
            "iddq_standby": {"low": None, "high": 50.0, "unit": "uA"},
            "leakage_input": {"low": None, "high": 100.0, "unit": "nA"},
            "prop_delay": {"low": None, "high": 20.0, "unit": "ns"},
            "vth_shift": {"low": -50.0, "high": 50.0, "unit": "mV"},
            "icc_active": {"low": None, "high": 45.0, "unit": "mA"},
            "output_res": {"low": None, "high": 100.0, "unit": "mOhm"},
        },
    }


@pytest.mark.fast
def test_referenced_profile_version_is_immutable(client: TestClient) -> None:
    """TEST-PROF-001: a referenced version answers 409 and is left intact."""
    created = client.put("/api/v1/profiles/mil_std_883_like", json=_profile_body())
    assert created.status_code == 200
    assert created.json()["data"]["version"] == 2

    # Pin version 2 the way a persisted disposition will in T-503.
    state = client.app.state.app_state  # type: ignore[attr-defined]
    state.store.execute(
        "INSERT INTO dispositions (disposition_id, component_id, dataset_hash, run_id,"
        " action, reason, actor, profile_id, profile_version, system_output_snapshot,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "D-TEST-1",
            "C-T-001",
            "sha256:test",
            None,
            "CONCUR",
            "test pin",
            "OP-TEST",
            "mil_std_883_like",
            2,
            "{}",
            "2026-09-10T00:00:00Z",
        ],
    )
    rewrite = client.put("/api/v1/profiles/mil_std_883_like/2", json=_profile_body())
    assert rewrite.status_code == 409
    assert rewrite.json()["error"]["code"] == "PROFILE_IMMUTABLE"
    current = client.get("/api/v1/profiles/mil_std_883_like/2").json()["data"]
    assert current["version"] == 2
    assert current["k"] == 4.5


@pytest.mark.fast
def test_profiles_round_trip(client: TestClient) -> None:
    """Reads serve the seeded default with its provenance tags."""
    listing = client.get("/api/v1/profiles").json()["data"]
    assert {"profile_id": "mil_std_883_like", "versions": [1]} in listing
    profile = client.get("/api/v1/profiles/mil_std_883_like").json()["data"]
    assert profile["k"] == 6.0
    assert profile["alpha"] == 0.10
    assert profile["limits"]["iddq_standby"]["high"] == 50.0
    unknown = client.get("/api/v1/profiles/nope")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "UNKNOWN_PROFILE"
