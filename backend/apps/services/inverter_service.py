"""Read-only inverter application service."""

from __future__ import annotations

from typing import Protocol

from apps.integrations.inverter import (
    BeveAuthenticationError, BeveCloudError, BeveConnectionError, BeveIncompleteResponseError,
    BeveIntegrationError, BeveMalformedResponseError, BeveMappingError, BeveTimeoutError,
)
from apps.integrations.inverter.adapter import InverterAdapter
from apps.models import (
    BatteryTelemetryStatus,
    GridTelemetryStatus,
    InverterTelemetry,
    InverterTelemetryStatus,
    SolarTelemetryStatus,
)


class InverterReader(Protocol):
    def fetch_current_telemetry(self) -> dict[str, object]: ...


class ServiceUnavailableError(RuntimeError):
    """Raised when a service has no configured telemetry source."""

    def __init__(self, message: str, *, category: str = "unreachable") -> None:
        super().__init__(message)
        self.category = category


class InverterService:
    """Expose normalized inverter monitoring with no mutation operations."""

    def __init__(
        self,
        client: InverterReader | None = None,
        *,
        adapter: InverterAdapter | None = None,
    ) -> None:
        self._client = client
        self._adapter = adapter or InverterAdapter()

    @property
    def configured(self) -> bool:
        return self._client is not None

    def get_current_state(self) -> InverterTelemetry:
        if self._client is None:
            raise ServiceUnavailableError("Inverter monitoring is not configured")
        try:
            return self._adapter.read(self._client)
        except BeveAuthenticationError:
            raise ServiceUnavailableError("BEVE cloud authentication failed", category="authentication_failed") from None
        except BeveTimeoutError:
            raise ServiceUnavailableError("BEVE cloud request timed out", category="timeout") from None
        except (BeveMalformedResponseError, BeveIncompleteResponseError, BeveMappingError):
            raise ServiceUnavailableError("BEVE cloud returned invalid telemetry", category="cloud_error") from None
        except BeveConnectionError:
            raise ServiceUnavailableError("BEVE cloud is unreachable", category="unreachable") from None
        except BeveCloudError:
            raise ServiceUnavailableError("BEVE cloud returned an error", category="cloud_error") from None
        except BeveIntegrationError:
            raise ServiceUnavailableError("BEVE cloud request failed", category="cloud_error") from None

    def get_battery_state(self) -> BatteryTelemetryStatus:
        return self.get_current_state().battery

    def get_solar_state(self) -> SolarTelemetryStatus:
        return self.get_current_state().solar

    def get_grid_state(self) -> GridTelemetryStatus:
        return self.get_current_state().grid

    def get_inverter_state(self) -> InverterTelemetryStatus:
        return self.get_current_state().inverter


_default_inverter_service = InverterService()


def get_inverter_service() -> InverterService:
    """FastAPI dependency for the configured inverter service."""

    from apps.core.runtime import get_application_runtime
    runtime = get_application_runtime()
    if runtime is not None:
        return runtime.inverter_service
    return _default_inverter_service
