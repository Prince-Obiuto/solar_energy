"""Secure first-run installation state and administrator bootstrap."""

from __future__ import annotations

import secrets
import threading
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.core.config import settings
from apps.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from apps.models.persistence import InstallationStateRecord, SystemEventRecord, UserRecord
from apps.services.auth_service import AuthService

SETUP_ROW_ID = 1
TOKEN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_SETUP_MUTATION_LOCK = threading.Lock()


class SetupLockedError(RuntimeError):
    pass


class SetupStateError(RuntimeError):
    pass


class SetupService:
    def __init__(self, session: Session, *, clock=None) -> None:
        self.session = session
        self.clock = clock or (lambda: datetime.now(UTC))

    def get_state(self) -> InstallationStateRecord:
        state = self._state()
        self._reconcile_existing_users(state)
        self.session.flush()
        return state

    def reconcile_existing_installation(self) -> InstallationStateRecord:
        """Mark first-admin setup unavailable when users already exist."""

        state = self._state(lock=True)
        self._reconcile_existing_users(state)
        self.session.flush()
        return state

    def _state(self, *, lock: bool = False) -> InstallationStateRecord:
        statement = select(InstallationStateRecord).where(
            InstallationStateRecord.id == SETUP_ROW_ID
        )
        if lock:
            statement = statement.with_for_update()
        state = self.session.scalar(statement.execution_options(populate_existing=lock))
        if state is not None:
            return state
        now = self.clock()
        state = InstallationStateRecord(
            id=SETUP_ROW_ID,
            setup_initialized=False,
            admin_configured=False,
            installation_version=settings.app_version,
        )
        self.session.add(state)
        self.session.flush()
        return state

    def initialize(self, *, rotate: bool = False) -> str | None:
        with _SETUP_MUTATION_LOCK:
            state = self._state(lock=True)
            self._reconcile_existing_users(state)
            self._ensure_unlocked(state)
            if state.setup_initialized and not rotate:
                return None
            code = self._generate_code()
            state.setup_token_hash = hash_password(code)
            state.setup_initialized = True
            state.initialized_at = state.initialized_at or self.clock()
            state.installation_version = settings.app_version
            self._audit("Setup token rotated" if rotate else "Setup initialized")
            self.session.flush()
            return code

    def verify(self, code: str) -> bool:
        state = self.get_state()
        valid = self._verify_state_code(state, code)
        if not valid:
            self._audit("Setup code verification failed", severity="warning")
            self.session.flush()
        return valid

    def create_administrator(
        self,
        *,
        code: str,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> UserRecord:
        # The process lock makes SQLite/development behavior deterministic. The
        # SELECT FOR UPDATE below is the cross-process PostgreSQL guarantee.
        with _SETUP_MUTATION_LOCK:
            state = self._state(lock=True)
            self._ensure_unlocked(state)
            if self._has_users():
                self._reconcile_existing_users(state)
                self._audit("Existing installation administrator state reconciled")
                self.session.commit()
                raise SetupStateError("Initial administrator setup is unavailable")
            if not state.setup_initialized or state.admin_configured:
                raise SetupStateError("Initial administrator setup is unavailable")
            if not self._verify_state_code(state, code):
                self._audit("Setup administrator authorization failed", severity="warning")
                self.session.commit()
                raise SetupStateError("Setup authorization failed")

            user = AuthService(self.session).bootstrap_admin(
                email, password, full_name, commit=False
            )
            state.admin_configured = True
            state.admin_configured_at = self.clock()
            self._audit("Initial administrator configured")
            self.session.commit()
            self.session.refresh(user)
            return user

    def authorize_beve_stage(self, code: str) -> InstallationStateRecord:
        """Authorize the token-driven BEVE setup stage and lock its state row."""

        state = self._state(lock=True)
        self._reconcile_existing_users(state)
        self._ensure_unlocked(state)
        eligible = state.setup_initialized and state.admin_configured
        if not eligible or not self._verify_state_code(state, code):
            self._audit("BEVE setup authorization failed", severity="warning")
            self.session.commit()
            raise SetupStateError("Setup authorization failed")
        return state

    def authorize_tuya_stage(self, code: str) -> InstallationStateRecord:
        """Authorize Tuya onboarding only after verified BEVE configuration."""

        state = self._state(lock=True)
        self._reconcile_existing_users(state)
        self._ensure_unlocked(state)
        eligible = (
            state.setup_initialized
            and state.admin_configured
            and state.beve_configured
        )
        if not eligible or not self._verify_state_code(state, code):
            self._audit("Tuya setup authorization failed", severity="warning")
            self.session.commit()
            raise SetupStateError("Setup authorization failed")
        return state

    def progress(self) -> dict[str, object]:
        state = self.get_state()
        if state.setup_completed:
            return {"setup_required": False, "setup_completed": True}
        if not state.setup_initialized:
            next_step = "initialize"
        elif not state.admin_configured:
            next_step = "administrator"
        elif not state.beve_configured:
            next_step = "beve"
        elif not state.tuya_configured:
            next_step = "tuya"
        elif not state.devices_verified:
            next_step = "devices"
        else:
            next_step = "confirm"
        return {
            "setup_required": True,
            "setup_initialized": state.setup_initialized,
            "admin_configured": state.admin_configured,
            "beve_configured": state.beve_configured,
            "tuya_configured": state.tuya_configured,
            "devices_verified": state.devices_verified,
            "setup_completed": False,
            "next_step": next_step,
        }

    @staticmethod
    def _generate_code() -> str:
        raw = "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(12))
        return "-".join(raw[index:index + 4] for index in range(0, 12, 4))

    @staticmethod
    def _ensure_unlocked(state: InstallationStateRecord) -> None:
        if state.setup_completed:
            raise SetupLockedError("Installation setup is complete")

    def _has_users(self) -> bool:
        return bool(self.session.scalar(select(func.count()).select_from(UserRecord)))

    def _reconcile_existing_users(self, state: InstallationStateRecord) -> bool:
        if state.admin_configured or not self._has_users():
            return False
        now = self.clock()
        state.setup_initialized = True
        state.admin_configured = True
        state.initialized_at = state.initialized_at or now
        state.admin_configured_at = state.admin_configured_at or now
        state.installation_version = state.installation_version or settings.app_version
        return True

    @staticmethod
    def _verify_state_code(state: InstallationStateRecord, code: str) -> bool:
        eligible = (
            not state.setup_completed
            and state.setup_initialized
            and state.setup_token_hash is not None
        )
        matches = verify_password(code, state.setup_token_hash or DUMMY_PASSWORD_HASH)
        return bool(eligible and matches)

    def _audit(self, message: str, *, severity: str = "info") -> None:
        self.session.add(SystemEventRecord(
            timestamp=self.clock(), category="installation.setup", severity=severity, message=message,
            details=None,
        ))
