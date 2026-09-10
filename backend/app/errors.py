"""Closed API error enum and envelope error responses (Phase 5, T-501).

Implements ``docs/API_CONTRACT.md § 9`` and FR-603:

- Every error response is ``{"error": {"code", "message", "details",
  "remediation", "request_id"}}``. Never a 200 carrying an error.
- ``4xx`` for anything caused by input; ``5xx`` only for genuine internal
  faults, and every ``5xx`` in a test run is a P1 defect.
- The enum is closed: the handlers in ``backend/app/main.py`` are the only
  producers, and each member maps to exactly one HTTP status.

One deliberate delta from the contract text: ``NOT_FOUND`` (404) for
unmatched paths. The contract enum lists resource-specific ``UNKNOWN_*``
codes; answering ``GET /api/v1/nope`` with ``UNKNOWN_COMPONENT`` would be a
dishonest attribution, and leaving Starlette's default bare ``{"detail"}``
body would violate FR-603's structured-error rule. Recorded as PROPOSED
amendment ``D-042`` for Lead Orchestrator sign-off; no other code is added.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any, Final

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    """Closed error enum (API_CONTRACT § 9 + PROPOSED ``NOT_FOUND``)."""

    VALIDATION_FAILED = "VALIDATION_FAILED"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    UNKNOWN_COMPONENT = "UNKNOWN_COMPONENT"
    UNKNOWN_LOT = "UNKNOWN_LOT"
    UNKNOWN_DATASET = "UNKNOWN_DATASET"
    UNKNOWN_PROFILE = "UNKNOWN_PROFILE"
    INSUFFICIENT_COHORT = "INSUFFICIENT_COHORT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INSUFFICIENT_CALIBRATION = "INSUFFICIENT_CALIBRATION"
    NO_VARIATION = "NO_VARIATION"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    PROFILE_IMMUTABLE = "PROFILE_IMMUTABLE"
    REASON_REQUIRED = "REASON_REQUIRED"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


ERROR_STATUS: Final[dict[ErrorCode, int]] = {
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

ERROR_REMEDIATION: Final[dict[ErrorCode, str]] = {
    ErrorCode.VALIDATION_FAILED: "Fix the listed fields and retry the request.",
    ErrorCode.UNIT_MISMATCH: "Resubmit with units matching the active profile.",
    ErrorCode.UNKNOWN_COMPONENT: "Check the component_id against a lot listing.",
    ErrorCode.UNKNOWN_LOT: "Check the lot_id against the lots listing.",
    ErrorCode.UNKNOWN_DATASET: "Check the dataset hash against the datasets listing.",
    ErrorCode.UNKNOWN_PROFILE: "Check the profile id against the profiles listing.",
    ErrorCode.INSUFFICIENT_COHORT: "Analysis deferred to absolute limits. "
    "Ingest more parts or accept limit-only screening.",
    ErrorCode.INSUFFICIENT_DATA: "Supply the missing read-point; no imputation is performed.",
    ErrorCode.INSUFFICIENT_CALIBRATION: "Widen the calibration set or accept the attainable alpha.",
    ErrorCode.NO_VARIATION: "The cohort carries no variation to judge against; "
    "ingest a wider lot or accept limit-only screening.",
    ErrorCode.MODEL_UNAVAILABLE: "The named artifact is missing or corrupt; "
    "re-run training or restore the registry entry.",
    ErrorCode.PROFILE_IMMUTABLE: "Referenced profile versions are immutable; "
    "submit the change as a new version.",
    ErrorCode.REASON_REQUIRED: "Provide a non-empty reason for the override.",
    ErrorCode.NOT_FOUND: "Check the path against GET /api/v1/openapi.json.",
}

_GENERIC_500_MESSAGE: Final[str] = "An unexpected internal fault occurred."


class ApiError(Exception):
    """A structured, anticipated API failure (never a 500)."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        if code is ErrorCode.INTERNAL_ERROR:
            raise ValueError("ApiError must not carry INTERNAL_ERROR; raise the fault instead")
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = list(details) if details is not None else []


def error_body(
    code: ErrorCode, message: str, request_id: str, details: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build the ``{"error": {...}}`` envelope (API_CONTRACT § 9)."""
    body: dict[str, Any] = {
        "error": {
            "code": code.value,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }
    if code in ERROR_REMEDIATION:
        body["error"]["remediation"] = ERROR_REMEDIATION[code]
    return body


def api_error_response(exc: ApiError, request_id: str) -> JSONResponse:
    """Render an anticipated failure with its contract status."""
    return JSONResponse(
        status_code=ERROR_STATUS[exc.code],
        content=error_body(exc.code, exc.message, request_id, exc.details),
    )


def not_found_response(request: Request, request_id: str) -> JSONResponse:
    """Render an unmatched path as a structured 404 (PROPOSED ``NOT_FOUND``)."""
    return JSONResponse(
        status_code=ERROR_STATUS[ErrorCode.NOT_FOUND],
        content=error_body(
            ErrorCode.NOT_FOUND,
            f"No route matches {request.url.path}.",
            request_id,
            [{"path": request.url.path}],
        ),
    )


def validation_failed_response(request_id: str, details: list[dict[str, Any]]) -> JSONResponse:
    """Render a Pydantic boundary rejection as 422 ``VALIDATION_FAILED``."""
    return JSONResponse(
        status_code=ERROR_STATUS[ErrorCode.VALIDATION_FAILED],
        content=error_body(
            ErrorCode.VALIDATION_FAILED,
            "Request validation failed.",
            request_id,
            details,
        ),
    )


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for genuine faults: 500, generic message, nothing leaked.

    SR-06: stack traces and filesystem paths never reach the client. The
    fault *is* logged server-side with the request id for diagnosis.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("internal fault request_id=%s path=%s", request_id, request.url.path)
    return JSONResponse(
        status_code=ERROR_STATUS[ErrorCode.INTERNAL_ERROR],
        content=error_body(ErrorCode.INTERNAL_ERROR, _GENERIC_500_MESSAGE, request_id, []),
    )
