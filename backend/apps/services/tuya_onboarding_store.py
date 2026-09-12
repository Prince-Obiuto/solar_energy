"""Short-lived, process-local storage for secret Tuya onboarding material."""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from pydantic import SecretStr

from apps.integrations.tuya.onboarding import TuyaCloudDevice, TuyaLanDevice


class TuyaOnboardingSessionError(LookupError):
    """Raised for missing or expired opaque onboarding sessions."""


@dataclass(slots=True, repr=False)
class TuyaOnboardingCandidate:
    device_ref: str
    device_id: str
    local_key: SecretStr | None
    name: str | None
    product_id: str | None
    category: str | None
    model: str | None
    online: bool | None
    cloud_protocol_version: str | None
    lan: TuyaLanDevice | None = None

    def __repr__(self) -> str:
        return "TuyaOnboardingCandidate(<redacted>)"


@dataclass(slots=True, repr=False)
class TuyaOnboardingSession:
    expires_at: float
    candidates: dict[str, TuyaOnboardingCandidate] = field(default_factory=dict)

    def __repr__(self) -> str:
        return "TuyaOnboardingSession(<redacted>)"


class TuyaOnboardingStore:
    """Bounded in-memory session store; raw cloud credentials are never accepted."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 900,
        max_sessions: int = 10,
        monotonic=time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or max_sessions <= 0:
            raise ValueError("Onboarding session bounds must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.monotonic = monotonic
        self._sessions: OrderedDict[str, TuyaOnboardingSession] = OrderedDict()
        self._lock = threading.RLock()

    def create(self, devices: list[TuyaCloudDevice]) -> tuple[str, TuyaOnboardingSession]:
        with self._lock:
            self._cleanup()
            while len(self._sessions) >= self.max_sessions:
                _, removed = self._sessions.popitem(last=False)
                removed.candidates.clear()
            token = secrets.token_urlsafe(32)
            candidates: dict[str, TuyaOnboardingCandidate] = {}
            for device in devices:
                device_ref = secrets.token_urlsafe(18)
                candidates[device_ref] = TuyaOnboardingCandidate(
                    device_ref=device_ref,
                    device_id=device.device_id,
                    local_key=device.local_key,
                    name=device.name,
                    product_id=device.product_id,
                    category=device.category,
                    model=device.model,
                    online=device.online,
                    cloud_protocol_version=device.protocol_version,
                )
            session = TuyaOnboardingSession(
                expires_at=self.monotonic() + self.ttl_seconds,
                candidates=candidates,
            )
            self._sessions[token] = session
            return token, session

    def get(self, token: str) -> TuyaOnboardingSession:
        with self._lock:
            self._cleanup()
            session = self._sessions.get(token)
            if session is None:
                raise TuyaOnboardingSessionError(
                    "Tuya onboarding session is invalid or expired"
                )
            return session

    def destroy(self, token: str) -> None:
        with self._lock:
            session = self._sessions.pop(token, None)
            if session is not None:
                session.candidates.clear()

    def _cleanup(self) -> None:
        now = self.monotonic()
        expired = [
            token for token, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for token in expired:
            session = self._sessions.pop(token)
            session.candidates.clear()

    @property
    def active_session_count(self) -> int:
        with self._lock:
            self._cleanup()
            return len(self._sessions)


__all__ = [
    "TuyaOnboardingCandidate",
    "TuyaOnboardingSession",
    "TuyaOnboardingSessionError",
    "TuyaOnboardingStore",
]
