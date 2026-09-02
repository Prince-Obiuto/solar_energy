"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from apps.api.router import api_router
from apps.core.config import settings
from apps.core.logging import configure_logging
from apps.jobs.energy_collector import get_energy_collector
from apps.jobs.health_monitor import health_monitor
from apps.realtime.manager import connection_manager


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Start and stop an optionally configured telemetry collector cleanly."""

    collector = get_energy_collector()
    await connection_manager.start()
    await health_monitor.start()
    if collector is not None:
        await collector.start()
    try:
        yield
    finally:
        if collector is not None:
            await collector.stop()
        await health_monitor.stop()
        await connection_manager.stop()


configure_logging(settings.log_level)
request_logger = logging.getLogger("apps.request")

app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)


@app.exception_handler(RequestValidationError)
async def sanitized_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return validation locations/messages without echoing submitted secrets."""

    errors = [
        {"location": list(error.get("loc", ())), "message": error.get("msg"), "type": error.get("type")}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": errors})

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def harden_http(request: Request, call_next):
    """Enforce a basic body limit and log only non-sensitive request metadata."""

    started = time.monotonic()
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            too_large = int(content_length) > settings.max_request_body_bytes
        except ValueError:
            too_large = True
        if too_large:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body is too large"},
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith(f"{settings.api_v1_prefix}/auth") else response.headers.get("Cache-Control", "no-cache")
    request_logger.info(
        "request method=%s path=%s status=%s duration_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        (time.monotonic() - started) * 1000,
    )
    return response

app.include_router(api_router, prefix=settings.api_v1_prefix)


def health_response() -> dict[str, str]:
    """Build the common service health payload."""

    return {
        "status": "ok",
        "service": "solar-energy-backend",
        "version": settings.app_version,
    }


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """Return basic application metadata."""

    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return the public service health status."""

    return health_response()
