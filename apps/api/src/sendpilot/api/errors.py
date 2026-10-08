"""Stable error envelope (PRD §25, §26).

Every error response is ``{"error": {"code", "message", "request_id"}}`` with a
stable ``code`` that maps to an HTTP status.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

# Stable code -> HTTP status (PRD Appendix B).
ERROR_STATUS: dict[str, int] = {
    "unauthorized": 401,
    "forbidden": 403,
    "not_found": 404,
    "invalid_state": 400,
    "file_too_large": 413,
    "unsupported_type": 415,
    "reauthorization_required": 401,
    "missing_merge_field": 422,
    "rate_limited": 429,
    "validation_error": 422,
    "conflict": 409,
    "internal": 500,
}


class AppError(Exception):
    """Domain error carrying a stable code."""

    def __init__(self, code: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status or ERROR_STATUS.get(code, 400)


def error_body(code: str, message: str, request_id: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    return JSONResponse(
        status_code=exc.status,
        content=error_body(exc.code, exc.message, request_id),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    return JSONResponse(
        status_code=500,
        content=error_body("internal", "internal server error", request_id),
    )
