"""Dashboard API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def get_dashboard() -> dict[str, object]:
    """Return dashboard summary values in a vendor-neutral payload."""

    return {"items": []}

