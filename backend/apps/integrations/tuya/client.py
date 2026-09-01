"""Local-LAN TinyTuya client with normalized failures and bounded retries."""

from __future__ import annotations

import socket
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol

import tinytuya
from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, SecretStr

from .constants import (
    DEFAULT_PROTOCOL_VERSION,
    TINYTUYA_MALFORMED_ERROR_CODES,
    TINYTUYA_OFFLINE_ERROR_CODES,
    TINYTUYA_TIMEOUT_ERROR_CODES,
)


class TuyaIntegrationError(Exception):
    """Base exception for sanitized local Tuya integration failures."""


class TuyaConfigurationError(TuyaIntegrationError):
    """Raised when local device configuration cannot be used safely."""


class TuyaTimeoutError(TuyaIntegrationError):
    """Raised when all attempts to contact a breaker time out."""


class TuyaOfflineError(TuyaIntegrationError):
    """Raised when a breaker cannot be reached on the local network."""


class TuyaMalformedResponseError(TuyaIntegrationError):
    """Raised when TinyTuya returns an invalid status payload."""


class TuyaCommunicationError(TuyaIntegrationError):
    """Raised for other normalized TinyTuya communication failures."""


class TuyaDeviceConfig(BaseModel):
    """Validated configuration for one deployed local breaker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    device_id: str = Field(min_length=1)
    friendly_name: str = Field(min_length=1)
    area: str = Field(min_length=1)
    local_key: SecretStr = Field(min_length=1)
    ip_address: IPvAnyAddress
    protocol_version: str = Field(default=DEFAULT_PROTOCOL_VERSION, pattern=r"^\d+\.\d+$")
    enabled: bool = True


class TinyTuyaDevice(Protocol):
    """Narrow protocol used to make the hardware client testable."""

    def set_version(self, version: float) -> None: ...

    def status(self, nowait: bool = False) -> Any: ...

    def set_value(self, index: int, value: Any, nowait: bool = False) -> Any: ...

    def close(self) -> None: ...


DeviceFactory = Callable[..., TinyTuyaDevice]


class TuyaClient:
    """Read breaker status over LAN without leaking TinyTuya exceptions or secrets."""

    def __init__(
        self,
        config: TuyaDeviceConfig,
        *,
        max_attempts: int = 3,
        socket_timeout_seconds: float = 5.0,
        retry_delay_seconds: float = 0.0,
        device_factory: DeviceFactory | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 1 <= max_attempts <= 5:
            raise TuyaConfigurationError("Tuya max_attempts must be between 1 and 5")
        if socket_timeout_seconds <= 0:
            raise TuyaConfigurationError("Tuya socket timeout must be positive")
        if retry_delay_seconds < 0:
            raise TuyaConfigurationError("Tuya retry delay cannot be negative")

        self.config = config
        self.max_attempts = max_attempts
        self.socket_timeout_seconds = socket_timeout_seconds
        self.retry_delay_seconds = retry_delay_seconds
        self._device_factory = device_factory or tinytuya.Device
        self._sleep = sleep

    def read_status(self) -> dict[str, Any]:
        """Return one raw TinyTuya status payload or a normalized integration error."""

        if not self.config.enabled:
            raise TuyaConfigurationError("Tuya device is disabled")

        last_error: TuyaIntegrationError | None = None
        for attempt in range(self.max_attempts):
            try:
                return self._read_once()
            except (TuyaTimeoutError, TuyaOfflineError, TuyaCommunicationError) as exc:
                last_error = exc
                if attempt + 1 < self.max_attempts and self.retry_delay_seconds:
                    self._sleep(self.retry_delay_seconds)

        if last_error is None:  # pragma: no cover - defensive invariant
            raise TuyaCommunicationError("Tuya status read failed")
        raise last_error

    def fetch_device_state(self, device_id: str | None = None) -> dict[str, Any]:
        """Compatibility wrapper for existing integration callers."""

        if device_id is not None and device_id != self.config.device_id:
            raise TuyaConfigurationError("Requested Tuya device does not match client configuration")
        return self.read_status()

    def write_datapoint(self, datapoint: int, value: Any) -> dict[str, Any]:
        """Write one adapter-allowlisted datapoint with normalized failures."""

        from .constants import CONTROL_DATAPOINTS

        if datapoint not in CONTROL_DATAPOINTS:
            raise TuyaConfigurationError("Tuya datapoint is not permitted for control")
        if not self.config.enabled:
            raise TuyaConfigurationError("Tuya device is disabled")
        device: TinyTuyaDevice | None = None
        try:
            device = self._device_factory(
                self.config.device_id,
                address=str(self.config.ip_address),
                local_key=self.config.local_key.get_secret_value(),
                connection_timeout=self.socket_timeout_seconds,
                connection_retry_limit=0,
                version=float(self.config.protocol_version),
            )
            device.set_version(float(self.config.protocol_version))
            response = device.set_value(datapoint, value)
        except (socket.timeout, TimeoutError):
            raise TuyaTimeoutError("Tuya command timed out") from None
        except OSError:
            raise TuyaOfflineError("Tuya device is offline or unreachable") from None
        except tinytuya.DecodeError:
            raise TuyaMalformedResponseError("Tuya returned a malformed command response") from None
        except TuyaIntegrationError:
            raise
        except Exception:
            raise TuyaCommunicationError("Tuya command failed") from None
        finally:
            if device is not None:
                try:
                    device.close()
                except Exception:
                    pass
        if not isinstance(response, Mapping):
            raise TuyaCommunicationError("Tuya command was not acknowledged")
        if "Error" in response or "Err" in response:
            code = str(response.get("Err", ""))
            if code in TINYTUYA_TIMEOUT_ERROR_CODES:
                raise TuyaTimeoutError("Tuya command timed out")
            if code in TINYTUYA_OFFLINE_ERROR_CODES:
                raise TuyaOfflineError("Tuya device is offline or unreachable")
            if code in TINYTUYA_MALFORMED_ERROR_CODES:
                raise TuyaMalformedResponseError("Tuya returned a malformed command response")
            raise TuyaCommunicationError("Tuya command was not acknowledged")
        return dict(response)

    def _read_once(self) -> dict[str, Any]:
        device: TinyTuyaDevice | None = None
        try:
            device = self._device_factory(
                self.config.device_id,
                address=str(self.config.ip_address),
                local_key=self.config.local_key.get_secret_value(),
                connection_timeout=self.socket_timeout_seconds,
                connection_retry_limit=0,
                version=float(self.config.protocol_version),
            )
            device.set_version(float(self.config.protocol_version))
            response = device.status()
        except (socket.timeout, TimeoutError):
            raise TuyaTimeoutError("Tuya status request timed out") from None
        except OSError:
            raise TuyaOfflineError("Tuya device is offline or unreachable") from None
        except tinytuya.DecodeError:
            raise TuyaMalformedResponseError("Tuya returned a malformed status response") from None
        except TuyaIntegrationError:
            raise
        except Exception:
            raise TuyaCommunicationError("Tuya status request failed") from None
        finally:
            if device is not None:
                try:
                    device.close()
                except Exception:
                    pass

        return self._validate_response(response)

    @staticmethod
    def _validate_response(response: Any) -> dict[str, Any]:
        if not isinstance(response, Mapping):
            raise TuyaMalformedResponseError("Tuya returned a malformed status response")

        if "Error" in response or "Err" in response:
            code = str(response.get("Err", ""))
            if code in TINYTUYA_TIMEOUT_ERROR_CODES:
                raise TuyaTimeoutError("Tuya status request timed out")
            if code in TINYTUYA_OFFLINE_ERROR_CODES:
                raise TuyaOfflineError("Tuya device is offline or unreachable")
            if code in TINYTUYA_MALFORMED_ERROR_CODES:
                raise TuyaMalformedResponseError("Tuya returned a malformed status response")
            raise TuyaCommunicationError("Tuya status request failed")

        dps = response.get("dps")
        if not isinstance(dps, Mapping):
            raise TuyaMalformedResponseError("Tuya status response does not contain datapoints")
        return dict(response)
