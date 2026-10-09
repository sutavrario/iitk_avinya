"""Domain errors and the handlers that turn them into the standard error envelope:

{"error": {"code": str, "message": str, "request_id": str | None, "details": Any}}
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from google.api_core import exceptions as gcp_exceptions
from google.auth import exceptions as google_auth_exceptions
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)


class AppError(Exception):
    """Base for expected, user-facing errors. Raise subclasses from services."""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str, details: Any = None, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code


class UnauthorizedError(AppError):
    """Missing, invalid, expired or revoked credentials."""

    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    """Authenticated, but not allowed to perform this action."""

    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class UnsupportedMediaTypeError(AppError):
    status_code = 415
    code = "unsupported_media_type"


class ExternalServiceError(AppError):
    """Gemini, Firestore, Translation, etc. failed."""

    status_code = 502
    code = "external_service_error"


class ServiceUnavailableError(AppError):
    """A dependency is not configured or temporarily unreachable."""

    status_code = 503
    code = "service_unavailable"


def _envelope(
    status: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        headers=headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id_ctx.get(),
                "details": details,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("%s: %s", exc.code, exc.message)
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return _envelope(exc.status_code, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _envelope(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return _envelope(422, "validation_error", "Some fields are invalid", details)

    @app.exception_handler(gcp_exceptions.GoogleAPICallError)
    async def _gcp_error(_: Request, exc: gcp_exceptions.GoogleAPICallError) -> JSONResponse:
        logger.error("Google API call failed: %s", type(exc).__name__)
        return _envelope(
            503, "service_unavailable", "A storage service is temporarily unavailable. Try again."
        )

    @app.exception_handler(google_auth_exceptions.GoogleAuthError)
    async def _server_credentials_error(_: Request, exc: Exception) -> JSONResponse:
        # Server-side credential problem (not the user's sign-in). Never echo details.
        logger.error("Server Google credentials unavailable: %s", type(exc).__name__)
        return _envelope(
            503,
            "server_credentials_missing",
            "The server isn't connected to Firebase yet. Ask the administrator to configure it.",
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return _envelope(500, "internal_error", "An unexpected error occurred")
