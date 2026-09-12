"""Smart hybrid inverter integration package."""

from .adapter import InverterAdapter
from .client import (
    BeveAuthenticationError,
    BeveClient,
    BeveCloudError,
    BeveConfig,
    BeveConfigurationError,
    BeveConnectionError,
    BeveDeviceNotFoundError,
    BeveIncompleteResponseError,
    BeveIntegrationError,
    BeveMalformedResponseError,
    BeveTimeoutError,
    MockBeveClient,
    VERIFIED_BEVE_RESPONSE,
)
from .mapper import BeveMappingError, map_beve_telemetry, normalize_inverter_snapshot

InverterClient = BeveClient

__all__ = [
    "BeveAuthenticationError", "BeveClient", "BeveCloudError", "BeveConfig", "BeveConfigurationError", "BeveConnectionError",
    "BeveDeviceNotFoundError", "BeveIncompleteResponseError", "BeveIntegrationError", "BeveMalformedResponseError",
    "BeveMappingError", "BeveTimeoutError", "InverterAdapter", "InverterClient",
    "MockBeveClient", "VERIFIED_BEVE_RESPONSE", "map_beve_telemetry",
    "normalize_inverter_snapshot",
]
