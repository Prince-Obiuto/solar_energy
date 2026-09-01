"""Read-only smart-breaker application service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Protocol

from apps.integrations.tuya.adapter import TuyaBreakerAdapter
from apps.integrations.tuya.client import TuyaDeviceConfig, TuyaIntegrationError
from apps.models import BreakerDevice, BreakerStatus, DeviceCapability, DeviceStatus
from apps.models.energy_reading import ElectricalMeasurement


class BreakerReader(Protocol):
    config: TuyaDeviceConfig

    def read_status(self) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class BreakerRegistration:
    """Runtime breaker registration; connection secrets stay inside its client."""

    client: BreakerReader
    capabilities: DeviceCapability


class BreakerNotFoundError(LookupError):
    """Raised when a breaker ID is not registered."""


class BreakerService:
    """Read normalized breaker state without exposing control operations."""

    def __init__(
        self,
        registrations: list[BreakerRegistration] | None = None,
        *,
        adapter: TuyaBreakerAdapter | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._registrations = {
            registration.client.config.device_id: registration
            for registration in (registrations or [])
            if registration.client.config.enabled
        }
        self._adapter = adapter or TuyaBreakerAdapter()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._last_seen: dict[str, datetime] = {}

    @property
    def registered_breaker_ids(self) -> tuple[str, ...]:
        """Return enabled breaker references without exposing client configuration."""

        return tuple(self._registrations)

    def list_breakers(self) -> list[BreakerDevice]:
        return [self.get_breaker(device_id) for device_id in self._registrations]

    def get_breaker(self, breaker_id: str) -> BreakerDevice:
        registration = self._registration(breaker_id)
        try:
            status = self._adapter.read(registration.client)
            self._last_seen[breaker_id] = self._clock()
            online = True
        except TuyaIntegrationError:
            status = BreakerStatus(
                device_id=breaker_id,
                name=registration.client.config.friendly_name,
                status=DeviceStatus.OFFLINE,
            )
            online = False
        return BreakerDevice(
            id=breaker_id,
            friendly_name=registration.client.config.friendly_name,
            area=registration.client.config.area,
            online=online,
            last_seen=self._last_seen.get(breaker_id),
            capabilities=registration.capabilities,
            status=status,
        )

    def get_breaker_status(self, breaker_id: str) -> BreakerStatus:
        return self.get_breaker(breaker_id).status

    def get_electrical_readings(self, breaker_id: str) -> ElectricalMeasurement:
        return self.get_breaker_status(breaker_id).electrical

    def get_configuration(self, breaker_id: str) -> dict[str, object] | None:
        return self.get_breaker_status(breaker_id).configuration

    def get_capabilities(self, breaker_id: str) -> DeviceCapability:
        return self._registration(breaker_id).capabilities

    def is_online(self, breaker_id: str) -> bool:
        return self.get_breaker(breaker_id).online

    def get_registration(self, breaker_id: str) -> BreakerRegistration:
        """Return an internal registration for other application services."""

        return self._registration(breaker_id)

    def _registration(self, breaker_id: str) -> BreakerRegistration:
        try:
            return self._registrations[breaker_id]
        except KeyError:
            raise BreakerNotFoundError(f"Breaker {breaker_id!r} is not registered") from None


_default_breaker_service = BreakerService()


def get_breaker_service() -> BreakerService:
    """FastAPI dependency for the configured breaker service."""

    return _default_breaker_service
