"""FastAPI application factory."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from ..config import settings
from ..ingestion.storage import ensure_bucket
from ..logging import configure_logging, get_logger
from ..metrics import render_latest
from .analytics import router as analytics_router
from .auth_routes import router as auth_router
from .campaigns import router as campaigns_router
from .documents import router as documents_router
from .errors import AppError, app_error_handler, unhandled_error_handler
from .extraction import router as extraction_router
from .oauth import router as connections_router
from .review import router as review_router
from .suppressions import public_router as unsubscribe_router
from .suppressions import router as suppressions_router
from .webhooks import router as webhooks_router

log = get_logger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    try:
        await ensure_bucket()
    except Exception as exc:  # storage may be briefly unavailable at boot
        log.warning("startup.ensure_bucket_failed", error=str(exc))
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="SendPilot", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = rid
        structlog.contextvars.bind_contextvars(request_id=rid)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["x-request-id"] = rid
        return response

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(auth_router)
    app.include_router(connections_router)
    app.include_router(documents_router)
    app.include_router(extraction_router)
    app.include_router(review_router)
    app.include_router(campaigns_router)
    app.include_router(suppressions_router)
    app.include_router(unsubscribe_router)
    app.include_router(analytics_router)
    app.include_router(webhooks_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/metrics", tags=["meta"])
    async def metrics() -> Response:
        data, content_type = render_latest()
        return Response(content=data, media_type=content_type)

    return app
