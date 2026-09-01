"""Normalized user-profile domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class UserRole(str, Enum):
    STUDENT = "student"
    STAFF = "staff"
    ADMIN = "admin"


@dataclass(slots=True)
class UserProfile:
    """Minimal normalized user record used by app services and APIs."""

    user_id: str
    email: str | None = None
    full_name: str | None = None
    role: UserRole = UserRole.STUDENT
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
