"""Authentication and initial-administrator application service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from apps.models import UserRole
from apps.models.persistence import SystemEventRecord, UserRecord


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def authenticate(self, email: str, password: str) -> UserRecord | None:
        normalized = normalize_email(email)
        user = self.session.scalar(select(UserRecord).where(UserRecord.email == normalized))
        valid = verify_password(password, user.password_hash if user else DUMMY_PASSWORD_HASH)
        if user is None or not valid or not user.is_active:
            self._audit("auth.login.failed", "warning", "Login attempt failed", {"email": normalized})
            self.session.commit()
            return None
        self._audit("auth.login.succeeded", "info", "User login succeeded", {"user_id": str(user.id)})
        self.session.commit()
        return user

    def bootstrap_admin(self, email: str, password: str, full_name: str | None = None) -> UserRecord:
        normalized = normalize_email(email)
        if "@" not in normalized:
            raise ValueError("A valid initial administrator email is required")
        existing = self.session.scalar(select(UserRecord).where(UserRecord.email == normalized))
        if existing is not None:
            if existing.role != UserRole.ADMIN.value:
                raise ValueError("Existing user will not be elevated by bootstrap")
            return existing
        if self.session.scalar(select(func.count()).select_from(UserRecord)):
            raise ValueError("Bootstrap is only available before any users exist")
        user = UserRecord(
            id=uuid.uuid4(), email=normalized, full_name=full_name,
            password_hash=hash_password(password), role=UserRole.ADMIN.value, is_active=True,
        )
        self.session.add(user)
        self._audit("auth.admin.bootstrapped", "info", "Initial administrator created", {"user_id": str(user.id)})
        self.session.commit()
        self.session.refresh(user)
        return user

    def _audit(self, category: str, severity: str, message: str, details: dict[str, str]) -> None:
        self.session.add(SystemEventRecord(
            timestamp=datetime.now(UTC), category=category, severity=severity,
            message=message, details=details,
        ))
