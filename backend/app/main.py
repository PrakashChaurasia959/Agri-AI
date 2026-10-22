"""FastAPI application factory for AgriVision AI."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging, get_logger
from app.core.rate_limit import RateLimitMiddleware, RateLimitRule
from app.database.connection import db_manager

settings = get_settings()
configure_logging(
    level="DEBUG" if settings.debug else "INFO",
    json_output=settings.environment == "production",
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Open and close the MongoDB connection with the application."""
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    connected = await db_manager.connect()
    if not connected:
        logger.warning(
            "The API is starting without a database. Data endpoints will return "
            "HTTP 503 until MONGODB_URI is configured."
        )
    try:
        yield
    finally:
        await db_manager.disconnect()
        logger.info("Shutdown complete")


DESCRIPTION = """
**AgriVision AI** - smart agriculture, crop disease detection and data-driven
farming.

### Authentication
Two strategies are supported:

* `Authorization: Bearer <access_token>` for API clients and scripts.
* An HTTP-only session cookie for the browser SPA. Cookie-authenticated
  mutations additionally require the `X-CSRF-Token` header, whose value must
  match the `agrivision_csrf` cookie (double-submit pattern).

### Machine learning
The disease, crop recommendation and yield endpoints report `503` with an
actionable message when the corresponding trained model has not been installed
on the server. They never return a fabricated prediction.
""".strip()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={"name": "AgriVision AI"},
    license_info={"name": "For academic and educational use"},
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-CSRF-Token",
        "X-Requested-With",
    ],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
    max_age=600,
)

app.add_middleware(
    RateLimitMiddleware,
    rule=RateLimitRule(
        name="global",
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    ),
    enabled=settings.rate_limit_enabled,
)


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Attach a server-timing header to every response."""
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Return a consistent JSON body for every HTTP error."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return field level validation errors in a stable shape."""
    field_errors: dict[str, str] = {}
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        field_errors[location or "body"] = error.get("msg", "Invalid value")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "The request payload failed validation.",
            "error_code": "validation_error",
            "field_errors": field_errors,
            "path": request.url.path,
        },
    )


@app.exception_handler(PyMongoError)
async def mongo_exception_handler(request: Request, exc: PyMongoError) -> JSONResponse:
    """Translate database errors into a safe 503 without leaking details."""
    logger.error("Database error on %s: %s", request.url.path, type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "The database is currently unavailable. Please try again shortly.",
            "error_code": "database_unavailable",
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler - never leak a stack trace to the client."""
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred. Please try again.",
            "error_code": "internal_error",
            "path": request.url.path,
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, Any]:
    """Service banner with links to the documentation."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "api": settings.api_v1_prefix,
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
    }


@app.get("/api", include_in_schema=False)
async def api_root() -> dict[str, Any]:
    """API version banner."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "api_version": "v1",
        "endpoints": [
            f"{settings.api_v1_prefix}/auth/register",
            f"{settings.api_v1_prefix}/auth/login",
            f"{settings.api_v1_prefix}/disease/predict",
            f"{settings.api_v1_prefix}/crops/recommend",
            f"{settings.api_v1_prefix}/yield/predict",
            f"{settings.api_v1_prefix}/dashboard/overview",
            f"{settings.api_v1_prefix}/weather/current",
            f"{settings.api_v1_prefix}/health",
            f"{settings.api_v1_prefix}/models/status",
        ],
    }


__all__ = ["app"]
