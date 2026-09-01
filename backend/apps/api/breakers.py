"""Breaker API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_breakers() -> dict[str, list[dict[str, str]]]:
    """Return the breaker list using the normalized domain schema."""

    return {"items": []}

