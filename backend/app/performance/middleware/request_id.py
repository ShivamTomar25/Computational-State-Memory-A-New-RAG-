from __future__ import annotations

from contextvars import ContextVar
from typing import Optional
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware


current_request_id: ContextVar[Optional[str]] = ContextVar("current_request_id", default=None)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        token = current_request_id.set(request_id)

        try:
            response = await call_next(request)
        finally:
            current_request_id.reset(token)

        response.headers["X-Request-ID"] = request_id
        return response
