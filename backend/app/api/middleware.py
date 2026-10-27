import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.auth import NotAuthenticatedError, is_authenticated
from app.core.logging import request_id_var
from app.services.analytics import InvalidRangeError, NotFoundError

log = logging.getLogger("app.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Request id in/out, access log with latency, and ETag/304 keyed on the data version."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            version = getattr(request.app.state, "data_version", None)
            etag = f'W/"{version}-{request.url.path}?{request.url.query}"' if version else None
            if (
                etag
                and request.method == "GET"
                and request.url.path.startswith("/api/v1/")
                and request.headers.get("if-none-match") == etag
                and is_authenticated(request)  # never answer unauthenticated callers
            ):
                response: Response = Response(status_code=304)
            else:
                response = await call_next(request)
                if etag and response.status_code == 200 and request.url.path.startswith("/api/v1/"):
                    response.headers["ETag"] = etag
                    response.headers["Cache-Control"] = "private, max-age=60"
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
            request_id_var.reset(token)


def _error(status: int, code: str, message: str) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "request_id": request_id_var.get()}}
    return JSONResponse(body, status_code=status)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return _error(404, "not_found", str(exc))

    @app.exception_handler(NotAuthenticatedError)
    async def _unauthenticated(_: Request, exc: NotAuthenticatedError) -> JSONResponse:
        return _error(401, "unauthenticated", str(exc))

    @app.exception_handler(InvalidRangeError)
    async def _bad_range(_: Request, exc: InvalidRangeError) -> JSONResponse:
        return _error(422, "invalid_range", str(exc))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return _error(500, "internal_error", "Unexpected server error")

    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first["loc"] if p != "query")
        return _error(422, "validation_error", f"{loc}: {first['msg']}")
