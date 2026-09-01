"""Administrator-only user management application service."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.core.security import hash_password
from apps.models.persistence import UserRecord
from apps.schemas.user import UserCreate, UserUpdate


class UserConflictError(ValueError):
    pass


class UserNotFoundError(LookupError):
    pass


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_users(self) -> list[UserRecord]:
        return list(self.session.scalars(select(UserRecord).order_by(UserRecord.email)))

    def create_user(self, payload: UserCreate) -> UserRecord:
        if self.session.scalar(select(UserRecord).where(UserRecord.email == payload.email)):
            raise UserConflictError("A user with that email already exists")
        user = UserRecord(
            id=uuid.uuid4(), email=payload.email, full_name=payload.full_name,
            password_hash=hash_password(payload.password), role=payload.role.value, is_active=True,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def update_user(self, user_id: uuid.UUID, payload: UserUpdate, actor_id: uuid.UUID) -> UserRecord:
        user = self.session.get(UserRecord, user_id)
        if user is None:
            raise UserNotFoundError
        if user.id == actor_id and (payload.is_active is False or (payload.role and payload.role.value != user.role)):
            raise UserConflictError("Administrators cannot deactivate or change their own role")
        if payload.role is not None:
            user.role = payload.role.value
        if payload.is_active is not None:
            user.is_active = payload.is_active
        return user
