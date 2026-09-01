"""Administrator-only user administration routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.core.permissions import require_admin
from apps.db.session import get_db
from apps.models.persistence import UserRecord
from apps.schemas.auth import CurrentUser
from apps.schemas.user import UserCreate, UserList, UserUpdate
from apps.services.user_service import UserConflictError, UserNotFoundError, UserService


router = APIRouter(dependencies=[Depends(require_admin)])


def public_user(user: UserRecord) -> CurrentUser:
    return CurrentUser(id=str(user.id), email=user.email, full_name=user.full_name, role=user.role, is_active=user.is_active)


@router.get("", response_model=UserList)
async def list_users(session: Session = Depends(get_db)) -> UserList:
    users = UserService(session).list_users()
    return UserList(items=[public_user(user) for user in users], total=len(users))


@router.post("", response_model=CurrentUser, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: Session = Depends(get_db)) -> CurrentUser:
    try:
        return public_user(UserService(session).create_user(payload))
    except UserConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.patch("/{user_id}", response_model=CurrentUser)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    session: Session = Depends(get_db),
    actor: UserRecord = Depends(require_admin),
) -> CurrentUser:
    try:
        return public_user(UserService(session).update_user(user_id, payload, actor.id))
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None
    except UserConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
