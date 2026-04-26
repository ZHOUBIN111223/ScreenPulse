"""Request-scoped logging helpers for HTTP diagnostics."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import Request, Response

from app.config import get_settings

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)

LOGGER = logging.getLogger("screenpulse.http")
REQUEST_ID_HEADER = "X-Request-ID"


def get_request_id() -> str | None:
    return request_id_context.get()


def _coerce_request_id(value: str | None) -> str:
    if value is None:
        return uuid.uuid4().hex
    normalized = value.strip()
    if not normalized or len(normalized) > 128:
        return uuid.uuid4().hex
    return normalized


def _log_http_request(request: Request, response: Response, duration_ms: int, request_id: str) -> None:
    settings = get_settings()
    payload = {
        "event": "http.request.finished",
        "service": settings.app_name,
        "env": "runtime",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
        "client_host": request.client.host if request.client else None,
    }
    LOGGER.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _log_http_exception(request: Request, duration_ms: int, request_id: str) -> None:
    settings = get_settings()
    payload = {
        "event": "http.request.failed",
        "service": settings.app_name,
        "env": "runtime",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": 500,
        "duration_ms": duration_ms,
        "client_host": request.client.host if request.client else None,
    }
    LOGGER.exception(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


async def request_observability_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = _coerce_request_id(request.headers.get(REQUEST_ID_HEADER))
    token = request_id_context.set(request_id)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        _log_http_exception(request, duration_ms, request_id)
        raise
    finally:
        request_id_context.reset(token)

    response.headers[REQUEST_ID_HEADER] = request_id
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    _log_http_request(request, response, duration_ms, request_id)
    return response
