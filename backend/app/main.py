"""FastAPI application factory (Phase 5, T-501).

Owns the transport boundary: request ids, timing, the success envelope,
and the closed error handlers. Imports the numeric core only through the
schema mirror (``TracedValueSchema.from_core``), which looks values up —
never recomputes them.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.errors import (
    ApiError,
    ErrorCode,
    api_error_response,
    internal_error_handler,
    not_found_response,
    validation_failed_response,
)
from backend.app.routers.components import router as components_router
from backend.app.routers.datasets import router as datasets_router
from backend.app.routers.lots import router as lots_router
from backend.app.routers.models import router as models_router
from backend.app.routers.reports import router as reports_router
from backend.app.routers.system import router as system_router
from backend.app.runtime import API_VERSION
from backend.app.state import AppState

_OPENAPI_URL: str = f"/api/{API_VERSION}/openapi.json"
_DOCS_URL: str = f"/api/{API_VERSION}/docs"


def create_app(state: AppState | None = None) -> FastAPI:
    """Build the LATENTIS API application (base path ``/api/v1``)."""
    app = FastAPI(
        title="LATENTIS API",
        description="LATENTIS — LATENT-defect Inspection & Screening "
        "(SIH26170). Synthetic data only; single-operator local tool "
        "with no authentication (SR-09).",
        version=API_VERSION,
        openapi_url=_OPENAPI_URL,
        docs_url=_DOCS_URL,
        redoc_url=None,
    )
    app.state.app_state = state if state is not None else AppState()

    @app.middleware("http")
    async def _request_context_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        request.state.start_ns = time.perf_counter_ns()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(ApiError)
    async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        request_id: str = getattr(request.state, "request_id", "unknown")
        return api_error_response(exc, request_id)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        details = [
            {
                "loc": list(err.get("loc", [])),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        return validation_failed_response(request_id, details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Only 404 is routed here by design (no other Starlette HTTP error is
        # reachable on the T-501 surface); anything else keeps its status with
        # the structured envelope rather than a bare {"detail"} body.
        request_id = getattr(request.state, "request_id", "unknown")
        if exc.status_code == 404:
            return not_found_response(request, request_id)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": ErrorCode.NOT_FOUND.value,
                    "message": str(exc.detail),
                    "details": [{"path": request.url.path}],
                    "remediation": "Check the path and method against " "GET /api/v1/openapi.json.",
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        return await internal_error_handler(request, exc)

    app.include_router(system_router, prefix=f"/api/{API_VERSION}")
    app.include_router(datasets_router, prefix=f"/api/{API_VERSION}")
    app.include_router(components_router, prefix=f"/api/{API_VERSION}")
    app.include_router(lots_router, prefix=f"/api/{API_VERSION}")
    app.include_router(models_router, prefix=f"/api/{API_VERSION}")
    app.include_router(reports_router, prefix=f"/api/{API_VERSION}")
    return app


app = create_app()
