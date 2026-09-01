"""Log API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_logs() -> dict[str, list[dict[str, str]]]:
    """Return system logs in a normalized structure."""

    return {"items": []}

