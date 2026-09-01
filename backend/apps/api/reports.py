"""Report API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_reports() -> dict[str, list[dict[str, str]]]:
    """Return report metadata in normalized domain format."""

    return {"items": []}

