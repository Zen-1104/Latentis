"""Unit tests for the closed API error enum (T-501, FR-603, API_CONTRACT § 9).

Oracle: behavioural contract — the enum member set, the status table, and
the remediation rule are asserted against the contract text, not against
the implementation's current output. Any drift (a renamed code, a dropped
remediation, a leaked 500 message) fails here first.
"""

from __future__ import annotations

import pytest
from fastapi import Request

from backend.app.errors import (
    ERROR_REMEDIATION,
    ERROR_STATUS,
    ApiError,
    ErrorCode,
    api_error_response,
    error_body,
)


def _scope() -> dict[str, object]:
    return {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/healthz",
        "query_string": b"",
        "headers": [],
        "server": ("test", 80),
        "client": ("test", 50000),
    }


@pytest.mark.fast
def test_error_enum_is_closed_and_statuses_match_contract() -> None:
    """The enum holds exactly the contract codes; each maps to its § 9 status."""
    assert {code.value for code in ErrorCode} == {
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
    assert ERROR_STATUS == {
        ErrorCode.VALIDATION_FAILED: 422,
        ErrorCode.UNIT_MISMATCH: 422,
        ErrorCode.UNKNOWN_COMPONENT: 404,
        ErrorCode.UNKNOWN_LOT: 404,
        ErrorCode.UNKNOWN_DATASET: 404,
        ErrorCode.UNKNOWN_PROFILE: 404,
        ErrorCode.INSUFFICIENT_COHORT: 422,
        ErrorCode.INSUFFICIENT_DATA: 422,
        ErrorCode.INSUFFICIENT_CALIBRATION: 422,
        ErrorCode.NO_VARIATION: 422,
        ErrorCode.MODEL_UNAVAILABLE: 503,
        ErrorCode.PROFILE_IMMUTABLE: 409,
        ErrorCode.REASON_REQUIRED: 422,
        ErrorCode.NOT_FOUND: 404,
        ErrorCode.INTERNAL_ERROR: 500,
    }


@pytest.mark.fast
def test_every_non_500_code_carries_remediation() -> None:
    """API_CONTRACT § 9: remediation is present on every 4xx (and 503/409)."""
    for code in ErrorCode:
        if code is ErrorCode.INTERNAL_ERROR:
            assert code not in ERROR_REMEDIATION
            continue
        assert ERROR_REMEDIATION[code].strip(), f"{code.value} has an empty remediation"
    body = error_body(ErrorCode.INSUFFICIENT_DATA, "m", "r", [])
    assert body["error"]["remediation"]
    assert "remediation" not in error_body(ErrorCode.INTERNAL_ERROR, "m", "r", [])


@pytest.mark.fast
def test_api_error_envelope_shape_and_status() -> None:
    """Anticipated failures render the § 9 shape with the mapped status."""
    exc = ApiError(ErrorCode.INSUFFICIENT_COHORT, "Too few parts.", [{"n": 2, "n_min": 3}])
    response = api_error_response(exc, "req-1")
    assert response.status_code == 422
    import json

    payload = json.loads(bytes(response.body).decode())
    assert set(payload) == {"error"}
    assert payload["error"]["code"] == "INSUFFICIENT_COHORT"
    assert payload["error"]["message"] == "Too few parts."
    assert payload["error"]["details"] == [{"n": 2, "n_min": 3}]
    assert payload["error"]["remediation"]
    assert payload["error"]["request_id"] == "req-1"


@pytest.mark.fast
def test_api_error_refuses_internal_error_code() -> None:
    """INTERNAL_ERROR is reserved for genuine faults; it cannot be raised deliberately."""
    with pytest.raises(ValueError):
        ApiError(ErrorCode.INTERNAL_ERROR, "must not be constructible")


@pytest.mark.fast
def test_internal_fault_is_500_without_leaks() -> None:
    """SR-06: a genuine fault is 500 with a generic message — no trace, no paths."""
    import asyncio

    from backend.app.errors import internal_error_handler

    request = Request(_scope())
    request.state.request_id = "req-9"
    response = asyncio.run(
        internal_error_handler(request, RuntimeError("boom in /secret/worktree/backend/app/x.py"))
    )
    assert response.status_code == 500
    import json

    payload = json.loads(bytes(response.body).decode())
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert "boom" not in payload["error"]["message"]
    assert "/secret/worktree" not in payload["error"]["message"]
    assert payload["error"]["details"] == []
    assert payload["error"]["request_id"] == "req-9"
