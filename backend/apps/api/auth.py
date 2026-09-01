"""Authentication API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def auth_status() -> dict[str, str]:
    """Return an auth-status placeholder until real auth is implemented."""

    return {"status": "not-configured"}

