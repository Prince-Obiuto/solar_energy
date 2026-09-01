"""Control API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_controls() -> dict[str, list[dict[str, str]]]:
    """Return control-plane actions without vendor-specific field names."""

    return {"items": []}

