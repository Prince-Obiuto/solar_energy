"""Secure first-run installation state and administrator bootstrap."""
from __future__ import annotations
import secrets
from datetime import UTC, datetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from apps.core.security import hash_password, verify_password
from apps.models.persistence import InstallationStateRecord, SystemEventRecord, UserRecord
from apps.services.auth_service import AuthService

SETUP_ROW_ID = 1
TOKEN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class SetupLockedError(RuntimeError): pass
class SetupStateError(RuntimeError): pass


class SetupService:
    def __init__(self, session: Session, *, clock=None) -> None:
        self.session = session
        self.clock = clock or (lambda: datetime.now(UTC))

    def get_state(self) -> InstallationStateRecord:
        state = self.session.get(InstallationStateRecord, SETUP_ROW_ID)
        if state is not None:
            return state
        has_users = bool(self.session.scalar(select(func.count()).select_from(UserRecord)))
        now = self.clock()
        state = InstallationStateRecord(
            id=SETUP_ROW_ID, setup_initialized=has_users, admin_configured=has_users,
            initialized_at=now if has_users else None, admin_configured_at=now if has_users else None,
        )
        self.session.add(state)
        self.session.flush()
        return state

    def initialize(self, *, rotate: bool = False) -> str | None:
        state = self.get_state()
        self._ensure_unlocked(state)
        if state.setup_initialized and not rotate:
            return None
        code = self._generate_code()
        state.setup_token_hash = hash_password(code)
        state.setup_initialized = True
        state.initialized_at = state.initialized_at or self.clock()
        self._audit("Setup token rotated" if rotate else "Setup initialized")
        self.session.flush()
        return code

    def verify(self, code: str) -> bool:
        state = self.get_state()
        if state.setup_completed or not state.setup_initialized or not state.setup_token_hash:
            return False
        return verify_password(code, state.setup_token_hash)

    def create_administrator(self, *, code: str, email: str, password: str,
                             full_name: str | None = None) -> UserRecord:
        state = self.get_state()
        self._ensure_unlocked(state)
        if not state.setup_initialized or state.admin_configured:
            raise SetupStateError("Initial administrator setup is unavailable")
        if not self.verify(code):
            raise SetupStateError("Setup authorization failed")
        user = AuthService(self.session).bootstrap_admin(email, password, full_name, commit=False)
        state = self.get_state()
        state.admin_configured = True
        state.admin_configured_at = self.clock()
        self._audit("Initial administrator configured")
        self.session.flush()
        return user

    def progress(self) -> dict[str, object]:
        state = self.get_state()
        if state.setup_completed:
            return {"setup_required": False, "setup_completed": True}
        next_step = "initialize" if not state.setup_initialized else "administrator" if not state.admin_configured else "energy_sources"
        return {
            "setup_required": True, "setup_initialized": state.setup_initialized,
            "admin_configured": state.admin_configured, "beve_configured": state.beve_configured,
            "tuya_configured": state.tuya_configured, "devices_verified": state.devices_verified,
            "setup_completed": False, "next_step": next_step,
        }

    @staticmethod
    def _generate_code() -> str:
        raw = "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(12))
        return "-".join(raw[index:index + 4] for index in range(0, 12, 4))

    @staticmethod
    def _ensure_unlocked(state: InstallationStateRecord) -> None:
        if state.setup_completed:
            raise SetupLockedError("Installation setup is complete")

    def _audit(self, message: str) -> None:
        self.session.add(SystemEventRecord(
            timestamp=self.clock(), category="installation.setup", severity="info", message=message,
            details=None,
        ))
