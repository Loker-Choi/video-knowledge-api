from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 200, warnings: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.warnings = warnings or []


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": exc.code,
            "message": exc.message,
            "warnings": exc.warnings,
        },
    )


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    message = str(exc.detail) if exc.detail else "HTTP request failed."
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": "HTTP_ERROR",
            "message": message,
            "warnings": [],
        },
    )


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "loc": list(error.get("loc", [])),
            "type": str(error.get("type", "")),
            "msg": str(error.get("msg", "")),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=200,
        content={
            "ok": False,
            "error": "VALIDATION_ERROR",
            "message": "Request parameters are invalid.",
            "details": details,
            "warnings": ["Check the request body and parameter types."],
        },
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "ok": False,
            "error": "INTERNAL_ERROR",
            "message": str(exc),
            "warnings": ["Unexpected server error."],
        },
    )
