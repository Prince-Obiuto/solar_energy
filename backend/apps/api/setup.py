"""Unauthenticated but one-time-token-protected first-run setup routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from apps.db.session import get_db
from apps.schemas.setup import InitialAdministratorRequest, SetupCodeRequest
from apps.services.setup_service import SetupLockedError, SetupService, SetupStateError

router = APIRouter()


@router.get("/status")
async def setup_status(session: Session = Depends(get_db)) -> dict[str, object]:
    return SetupService(session).progress()


@router.post("/verify")
async def verify_setup_code(request: SetupCodeRequest,
                            session: Session = Depends(get_db)) -> dict[str, bool]:
    return {"valid": SetupService(session).verify(request.setup_code)}


@router.post("/administrator", status_code=status.HTTP_201_CREATED)
async def create_initial_administrator(
    request: InitialAdministratorRequest, session: Session = Depends(get_db),
) -> dict[str, object]:
    service = SetupService(session)
    try:
        user = service.create_administrator(
            code=request.setup_code, email=request.email,
            password=request.password, full_name=request.full_name,
        )
    except SetupLockedError:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Installation setup is unavailable") from None
    except (SetupStateError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Administrator setup could not be completed") from None
    return {
        "administrator": {
            "id": str(user.id), "email": user.email, "full_name": user.full_name,
            "role": user.role, "is_active": user.is_active,
        },
        "setup": service.progress(),
    }
