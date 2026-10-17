import logging

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from utils.csrf import validate_csrf_token
from utils.http_metrics import http_runtime_metrics, should_observe_http_path

logger = logging.getLogger(__name__)


def apply_response_security_headers(request: Request, response):
    """Apply browser hardening without exposing or transforming response bodies."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    path = request.url.path
    if path.startswith("/uploads/"):
        # Public user content must never become an active same-origin document.
        response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if path.startswith("/uploads/documents/"):
            response.headers["Content-Disposition"] = "attachment"
    return response


def security_headers_middleware(app):
    @app.middleware("http")
    async def security_headers_handler(request: Request, call_next):
        response = await call_next(request)
        return apply_response_security_headers(request, response)


def http_observability_middleware(app):
    @app.middleware("http")
    async def http_observability_handler(request: Request, call_next):
        if not should_observe_http_path(request.url.path):
            return await call_next(request)

        started = http_runtime_metrics.request_started()
        try:
            response = await call_next(request)
        except Exception:
            http_runtime_metrics.request_aborted(started)
            raise
        http_runtime_metrics.request_finished(started, response.status_code)
        return response


def csrf_middleware(app):
    @app.middleware("http")
    async def csrf_handler(request: Request, call_next):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)

        try:
            if not validate_csrf_token(request):
                raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        except Exception:
            logger.exception("CSRF validation failed")
            return JSONResponse(status_code=400, content={"detail": "CSRF validation error"})

        # Keep downstream application execution outside the CSRF validator's
        # exception handler. Otherwise unrelated endpoint/database failures are
        # mislabeled as 400 "CSRF validation error" responses.
        return await call_next(request)


def error_handling_middleware(app):
    @app.middleware("http")
    async def error_handler(request: Request, call_next):
        try:
            return await call_next(request)
        except OperationalError as exc:
            logger.error(f"Database connection error: {str(exc)}")
            return JSONResponse(status_code=503, content={"detail": "Database is temporarily unavailable."})
        except Exception:
            logger.exception("Unexpected error occurred")
            return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})
