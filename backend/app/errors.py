"""Consistent error model: ``{"error": {"code", "message", "details"}}`` with no internals leaked."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")

_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
}


class AppError(Exception):
    """A domain error carrying an HTTP status and a stable machine-readable code."""

    def __init__(self, status: int, code: str, message: str, details: Any = None) -> None:
        """Create the error."""
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def unauthorized(message: str = "Authentication required") -> AppError:
    """401."""
    return AppError(401, "unauthorized", message)


def forbidden(message: str = "You do not have permission to do that") -> AppError:
    """403."""
    return AppError(403, "forbidden", message)


def not_found(message: str = "Resource not found") -> AppError:
    """404."""
    return AppError(404, "not_found", message)


def conflict(message: str, code: str = "conflict", details: Any = None) -> AppError:
    """409."""
    return AppError(409, code, message, details)


def invalid(message: str, details: Any = None) -> AppError:
    """422 for semantic validation failures."""
    return AppError(422, "validation_error", message, details)


def _body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def install_error_handlers(app: FastAPI) -> None:
    """Register handlers that map every failure to the shared error envelope."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _CODES.get(exc.status_code, "error")
        return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()
        ]
        return JSONResponse(_body("validation_error", "Request validation failed", details), status_code=422)

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("integrity error: %s", exc.orig)
        return JSONResponse(_body("conflict", "The request conflicts with existing data"), status_code=409)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled error", exc_info=exc)
        return JSONResponse(_body("internal_error", "Internal server error"), status_code=500)
