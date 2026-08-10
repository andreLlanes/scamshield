"""Application-level exceptions and their HTTP translation."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class ScamShieldError(Exception):
    """Base class for every error raised inside ScamShield."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(ScamShieldError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ValidationError(ScamShieldError):
    # Literal rather than the Starlette constant: it was renamed to
    # HTTP_422_UNPROCESSABLE_CONTENT, and the literal works on both versions.
    status_code = 422
    code = "validation_error"


class UnsupportedMediaError(ScamShieldError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_media"


class PayloadTooLargeError(ScamShieldError):
    # Renamed to HTTP_413_CONTENT_TOO_LARGE upstream; see note above.
    status_code = 413
    code = "payload_too_large"


class DependencyUnavailableError(ScamShieldError):
    """An optional runtime dependency (model, vector store, LLM) is missing."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "dependency_unavailable"


class TranscriptionError(ScamShieldError):
    code = "transcription_failed"


class AnalysisError(ScamShieldError):
    code = "analysis_failed"


def register_exception_handlers(app: FastAPI) -> None:
    """Map ScamShield errors (and stray exceptions) onto a stable JSON shape."""

    @app.exception_handler(ScamShieldError)
    async def _handle_known(_: Request, exc: ScamShieldError) -> JSONResponse:
        logger.warning("request_failed", code=exc.code, message=exc.message, **exc.details)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(Exception)
    async def _handle_unknown(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "details": {},
                }
            },
        )
