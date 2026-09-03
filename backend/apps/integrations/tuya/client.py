"""Persistent local-LAN TinyTuya client with bounded self-recovery."""
from __future__ import annotations
import logging, socket, time
from collections.abc import Callable, Mapping
from typing import Any, Protocol
import tinytuya
from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, SecretStr
from .constants import (CONTROL_DATAPOINTS, DEFAULT_PROTOCOL_VERSION,
    TINYTUYA_MALFORMED_ERROR_CODES, TINYTUYA_OFFLINE_ERROR_CODES, TINYTUYA_TIMEOUT_ERROR_CODES)
logger = logging.getLogger(__name__)

class TuyaIntegrationError(Exception): pass
class TuyaConfigurationError(TuyaIntegrationError): pass
class TuyaTimeoutError(TuyaIntegrationError): pass
class TuyaOfflineError(TuyaIntegrationError): pass
class TuyaMalformedResponseError(TuyaIntegrationError): pass
class TuyaCommunicationError(TuyaIntegrationError): pass

class TuyaDeviceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    device_id: str = Field(min_length=1)
    friendly_name: str = Field(min_length=1)
    area: str = Field(min_length=1)
    local_key: SecretStr = Field(min_length=1)
    ip_address: IPvAnyAddress
    protocol_version: str = Field(default=DEFAULT_PROTOCOL_VERSION, pattern=r"^\d+\.\d+$")
    enabled: bool = True

class TinyTuyaDevice(Protocol):
    def set_version(self, version: float) -> None: ...
    def set_socketPersistent(self, persist: bool) -> None: ...
    def status(self, nowait: bool = False) -> Any: ...
    def set_value(self, index: int, value: Any, nowait: bool = False) -> Any: ...
    def set_status(self, on: bool, switch: int = 1, nowait: bool = False) -> Any: ...
    def close(self) -> None: ...

DeviceFactory = Callable[..., TinyTuyaDevice]
Discovery = Callable[..., Any]

class TuyaClient:
    """Own one persistent breaker connection and rebuild it after failure."""
    def __init__(self, config: TuyaDeviceConfig, *, max_attempts: int = 3,
                 socket_timeout_seconds: float = 5.0, retry_delay_seconds: float = 0.0,
                 device_factory: DeviceFactory | None = None, discovery: Discovery | None = None,
                 discovery_cooldown_seconds: float = 300.0,
                 sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        if not 1 <= max_attempts <= 5:
            raise TuyaConfigurationError("Tuya max_attempts must be between 1 and 5")
        if socket_timeout_seconds <= 0:
            raise TuyaConfigurationError("Tuya socket timeout must be positive")
        if retry_delay_seconds < 0 or discovery_cooldown_seconds < 0:
            raise TuyaConfigurationError("Tuya retry and discovery intervals cannot be negative")
        self.config, self.max_attempts = config, max_attempts
        self.socket_timeout_seconds, self.retry_delay_seconds = socket_timeout_seconds, retry_delay_seconds
        self._device_factory = device_factory or tinytuya.OutletDevice
        self._discovery = discovery or tinytuya.find_device
        self._discovery_cooldown_seconds = discovery_cooldown_seconds
        self._sleep, self._monotonic = sleep, monotonic
        self._runtime_address = str(config.ip_address)
        self._device: TinyTuyaDevice | None = None
        self._last_discovery_at: float | None = None
        self._rediscovery_used = False

    @property
    def persistent_connection_created(self) -> bool: return self._device is not None
    @property
    def rediscovery_used(self) -> bool: return self._rediscovery_used

    def read_status(self) -> dict[str, Any]:
        if not self.config.enabled: raise TuyaConfigurationError("Tuya device is disabled")
        return dict(self._execute(lambda device: device.status(), "status"))

    def fetch_device_state(self, device_id: str | None = None) -> dict[str, Any]:
        if device_id is not None and device_id != self.config.device_id:
            raise TuyaConfigurationError("Requested Tuya device does not match client configuration")
        return self.read_status()

    def write_datapoint(self, datapoint: int, value: Any) -> dict[str, Any]:
        if datapoint not in CONTROL_DATAPOINTS:
            raise TuyaConfigurationError("Tuya datapoint is not permitted for control")
        if not self.config.enabled: raise TuyaConfigurationError("Tuya device is disabled")
        response = self._execute(lambda device: device.set_value(datapoint, value), "command")
        if not isinstance(response, Mapping):
            self._reset_connection(); raise TuyaCommunicationError("Tuya command was not acknowledged")
        self._raise_response_error(response, "command")
        return dict(response)

    def set_switch_state(self, state: bool) -> dict[str, Any]:
        """Operate the primary relay through OutletDevice's native command."""
        if type(state) is not bool:
            raise TuyaConfigurationError("Tuya switch state must be boolean")
        if not self.config.enabled:
            raise TuyaConfigurationError("Tuya device is disabled")
        response = self._execute(
            lambda device: device.set_status(state, switch=1), "command"
        )
        if not isinstance(response, Mapping):
            self._reset_connection()
            raise TuyaCommunicationError("Tuya command was not acknowledged")
        return dict(response)

    def close(self) -> None: self._reset_connection()

    def _execute(self, operation: Callable[[TinyTuyaDevice], Any], label: str) -> Any:
        last_error: TuyaIntegrationError | None = None
        for attempt in range(self.max_attempts):
            try:
                response = operation(self._get_or_create_device())
                self._raise_response_error(response, label)
                if label == "status" and (not isinstance(response, Mapping) or
                                          not isinstance(response.get("dps"), Mapping)):
                    raise TuyaMalformedResponseError("Tuya status response does not contain datapoints")
                logger.debug("Breaker %s poll succeeded", label)
                return response
            except Exception as exc:
                last_error = self._normalize_exception(exc, label)
                self._reset_connection()
                logger.warning("Breaker communication failed category=%s", self._category(last_error))
                if attempt == 0 and attempt + 1 < self.max_attempts: self._try_rediscovery()
                if attempt + 1 < self.max_attempts and self.retry_delay_seconds:
                    self._sleep(self.retry_delay_seconds)
        assert last_error is not None
        raise last_error

    def _build_device(self) -> TinyTuyaDevice:
        device = self._device_factory(self.config.device_id, address=self._runtime_address,
            local_key=self.config.local_key.get_secret_value(),
            connection_timeout=self.socket_timeout_seconds, connection_retry_limit=1,
            connection_retry_delay=max(self.retry_delay_seconds, 0.1),
            version=float(self.config.protocol_version), persist=True)
        device.set_version(float(self.config.protocol_version))
        device.set_socketPersistent(True)
        logger.debug("TinyTuya persistent connection created")
        return device

    def _get_or_create_device(self) -> TinyTuyaDevice:
        if self._device is None: self._device = self._build_device()
        return self._device

    def _reset_connection(self) -> None:
        device, self._device = self._device, None
        if device is not None:
            try: device.close()
            except Exception: pass
            logger.debug("Breaker connection reset")

    def _try_rediscovery(self) -> bool:
        now = self._monotonic()
        if self._last_discovery_at is not None and now - self._last_discovery_at < self._discovery_cooldown_seconds:
            return False
        self._last_discovery_at = now
        try: found = self._discovery(dev_id=self.config.device_id)
        except Exception: return False
        if not isinstance(found, Mapping): return False
        found_id = found.get("id") or found.get("gwId") or found.get("device_id") or found.get("dev_id")
        address = found.get("ip") or found.get("address")
        version = found.get("version") or found.get("ver")
        if str(found_id) != self.config.device_id or not address: return False
        if version is not None:
            try:
                if float(version) != float(self.config.protocol_version): return False
            except (TypeError, ValueError): return False
        self._runtime_address, self._rediscovery_used = str(address), True
        logger.info("Breaker address rediscovered")
        logger.debug("Breaker rediscovered")
        return True

    @staticmethod
    def _normalize_exception(exc: Exception, operation: str) -> TuyaIntegrationError:
        if isinstance(exc, TuyaIntegrationError): return exc
        if isinstance(exc, (socket.timeout, TimeoutError)): return TuyaTimeoutError(f"Tuya {operation} request timed out")
        if isinstance(exc, OSError): return TuyaOfflineError("Tuya device is offline or unreachable")
        if isinstance(exc, tinytuya.DecodeError): return TuyaMalformedResponseError(f"Tuya returned a malformed {operation} response")
        return TuyaCommunicationError(f"Tuya {operation} request failed")

    @staticmethod
    def _raise_response_error(response: Any, operation: str) -> None:
        if not isinstance(response, Mapping) or not ("Error" in response or "Err" in response): return
        code = str(response.get("Err", ""))
        if code in TINYTUYA_TIMEOUT_ERROR_CODES: raise TuyaTimeoutError(f"Tuya {operation} request timed out")
        if code in TINYTUYA_OFFLINE_ERROR_CODES: raise TuyaOfflineError("Tuya device is offline or unreachable")
        if code in TINYTUYA_MALFORMED_ERROR_CODES: raise TuyaMalformedResponseError(f"Tuya returned a malformed {operation} response")
        if operation == "command":
            raise TuyaCommunicationError("Tuya command was not acknowledged")
        raise TuyaCommunicationError("Tuya status request failed")

    @staticmethod
    def _category(error: TuyaIntegrationError) -> str:
        if isinstance(error, TuyaTimeoutError): return "polling_timeout"
        if isinstance(error, TuyaOfflineError): return "offline"
        if isinstance(error, TuyaMalformedResponseError): return "malformed_response"
        if isinstance(error, TuyaConfigurationError): return "configuration_error"
        return "polling_failure"
