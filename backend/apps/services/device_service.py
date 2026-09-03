"""Unified device catalogue application service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from apps.models import (
    ConnectivityType, DataFreshness, DataSource, DataStatus, DeviceCapability,
    DeviceType, RegisteredDevice, SourceStatus,
)

from .breaker_service import BreakerNotFoundError, BreakerService, get_breaker_service
from .inverter_service import InverterService, ServiceUnavailableError, get_inverter_service

if TYPE_CHECKING:
    from apps.jobs.energy_collector import CollectorSnapshot
    from apps.models import BreakerDevice


class DeviceNotFoundError(LookupError):
    """Raised when a device is absent from the unified registry."""


class DeviceService:
    """Combine registered inverter and breaker identities without vendor details."""

    def __init__(
        self,
        inverter_service: InverterService,
        breaker_service: BreakerService,
        *,
        inverter_id: str | None = None,
        inverter_name: str = "Smart hybrid inverter",
        inverter_area: str = "Department of Information Technology",
    ) -> None:
        self._inverter = inverter_service
        self._breakers = breaker_service
        self._inverter_id = inverter_id
        self._inverter_name = inverter_name
        self._inverter_area = inverter_area
        self._inverter_last_seen: datetime | None = None

    @property
    def breaker_service(self) -> BreakerService:
        return self._breakers

    def get_cached_devices(
        self, snapshot: CollectorSnapshot, breakers: list[BreakerDevice]
    ) -> list[RegisteredDevice]:
        """Build the registry from collector/cache state without hardware I/O."""

        devices: list[RegisteredDevice] = []
        if self._inverter_id:
            state = snapshot.devices.get(self._inverter_id)
            data_status = DataStatus(
                connectivity_type=ConnectivityType.CLOUD,
                data_source=DataSource.BEVE_CLOUD,
                available=bool(state and state.source_status is SourceStatus.CONNECTED),
                stale=state.stale if state else True,
                source_status=state.source_status if state else SourceStatus.UNKNOWN,
                data_freshness=state.data_freshness if state else DataFreshness.UNAVAILABLE,
                last_successful_update=state.last_successful_update if state else None,
                last_attempt_at=state.last_attempt_at if state else None,
                last_successful_poll_at=state.last_successful_poll_at if state else None,
                source_timestamp=state.source_timestamp if state else None,
                source_changed=state.source_changed if state else None,
                source_age_seconds=state.source_age_seconds if state else None,
                last_failure_category=state.last_failure_category if state else None,
            )
            devices.append(RegisteredDevice(
                id=self._inverter_id, friendly_name=self._inverter_name,
                type=DeviceType.INVERTER, area=self._inverter_area, online=None,
                last_seen=data_status.source_timestamp,
                connectivity_type=ConnectivityType.CLOUD, data_source=DataSource.BEVE_CLOUD,
                data_status=data_status,
                capabilities=DeviceCapability(
                    instantaneous_power=True, voltage=True, current=True,
                    energy_total=True, fault_monitoring=True,
                ),
            ))
        devices.extend(RegisteredDevice(
            id=breaker.id, friendly_name=breaker.friendly_name, type=DeviceType.BREAKER,
            area=breaker.area, online=breaker.online, last_seen=breaker.last_seen,
            connectivity_type=ConnectivityType.LOCAL, data_source=DataSource.TINYTUYA,
            data_status=breaker.data_status, relay_on=breaker.status.switch_on,
            capabilities=breaker.capabilities,
        ) for breaker in breakers)
        return devices

    def get_devices(self) -> list[RegisteredDevice]:
        devices: list[RegisteredDevice] = []
        if self._inverter_id:
            source_status = SourceStatus.UNKNOWN
            try:
                self._inverter.get_current_state()
                source_status = SourceStatus.CONNECTED
                self._inverter_last_seen = datetime.now(UTC)
            except ServiceUnavailableError as exc:
                source_status = {
                    "authentication_failed": SourceStatus.AUTHENTICATION_FAILED,
                    "timeout": SourceStatus.TIMEOUT,
                    "unreachable": SourceStatus.UNREACHABLE,
                    "cloud_error": SourceStatus.CLOUD_ERROR,
                }.get(exc.category, SourceStatus.UNKNOWN)
            available = source_status is SourceStatus.CONNECTED
            devices.append(
                RegisteredDevice(
                    id=self._inverter_id,
                    friendly_name=self._inverter_name,
                    type=DeviceType.INVERTER,
                    area=self._inverter_area,
                    online=None,
                    last_seen=self._inverter_last_seen,
                    connectivity_type=ConnectivityType.CLOUD,
                    data_source=DataSource.BEVE_CLOUD,
                    data_status=DataStatus(
                        connectivity_type=ConnectivityType.CLOUD,
                        data_source=DataSource.BEVE_CLOUD,
                        available=available,
                        stale=not available and self._inverter_last_seen is not None,
                        source_status=source_status,
                        data_freshness=DataFreshness.LIVE if available else DataFreshness.STALE if self._inverter_last_seen else DataFreshness.UNAVAILABLE,
                        last_successful_update=self._inverter_last_seen,
                    ),
                    capabilities=DeviceCapability(
                        instantaneous_power=True,
                        voltage=True,
                        current=True,
                        energy_total=True,
                        fault_monitoring=True,
                    ),
                )
            )
        for breaker in self._breakers.list_breakers():
            devices.append(
                RegisteredDevice(
                    id=breaker.id,
                    friendly_name=breaker.friendly_name,
                    type=DeviceType.BREAKER,
                    area=breaker.area,
                    online=breaker.online,
                    last_seen=breaker.last_seen,
                    connectivity_type=ConnectivityType.LOCAL,
                    data_source=DataSource.TINYTUYA,
                    data_status=breaker.data_status,
                    relay_on=breaker.status.switch_on,
                    capabilities=breaker.capabilities,
                )
            )
        return devices

    def get_device(self, device_id: str) -> RegisteredDevice:
        for device in self.get_devices():
            if device.id == device_id:
                return device
        raise DeviceNotFoundError(f"Device {device_id!r} is not registered")


_default_device_service = DeviceService(get_inverter_service(), get_breaker_service())


def get_device_service() -> DeviceService:
    """FastAPI dependency for the unified device catalogue."""

    from apps.core.runtime import get_application_runtime
    runtime = get_application_runtime()
    if runtime is not None:
        return runtime.device_service
    return _default_device_service


def get_devices() -> list[RegisteredDevice]:
    """Compatibility wrapper for the existing API/service contract."""

    return get_device_service().get_devices()


def get_device(device_id: str) -> RegisteredDevice | None:
    """Compatibility wrapper returning None for an unknown device."""

    try:
        return get_device_service().get_device(device_id)
    except DeviceNotFoundError:
        return None
