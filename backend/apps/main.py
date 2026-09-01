"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.router import api_router
from apps.core.config import settings


app = FastAPI(title=settings.app_name, version=settings.app_version)

if settings.app_env.lower() == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
