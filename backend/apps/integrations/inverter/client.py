"""Strictly read-only client for the verified BEVE/Solar-of-Things API."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path
import sys
from typing import Any, Protocol

import requests
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from apps.core.config import BACKEND_DIR

from .constants import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    LATEST_STATE_PATH,
)


class BeveIntegrationError(Exception):
    """Base class for sanitized BEVE integration errors."""


class BeveConfigurationError(BeveIntegrationError):
    """Raised when required environment configuration is invalid."""


class BeveAuthenticationError(BeveIntegrationError):
    """Raised when BEVE authentication or reauthentication fails."""


class BeveTimeoutError(BeveIntegrationError):
    """Raised when a BEVE request times out."""


class BeveConnectionError(BeveIntegrationError):
    """Raised when the BEVE service cannot be reached."""


class BeveCloudError(BeveIntegrationError):
    """Raised when the remote BEVE/Siseli service returns an HTTP error."""


class BeveMalformedResponseError(BeveIntegrationError):
    """Raised when a BEVE response is not structurally valid JSON data."""


class BeveIncompleteResponseError(BeveIntegrationError):
    """Raised when a response lacks the minimum envelope required for mapping."""


class BeveConfig(BaseSettings):
    """Environment-backed BEVE connection and device configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BEVE_",
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    base_url: str = DEFAULT_BASE_URL
    username: SecretStr
    password: SecretStr
    station_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    time_zone: str = "Africa/Lagos"
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0, le=120)


class ResponseLike(Protocol):
    status_code: int

    def raise_for_status(self) -> None: ...

    def json(self) -> Any: ...


class SessionLike(Protocol):
    def get(self, url: str, **kwargs: Any) -> ResponseLike: ...


class SolarOfThingsAPILike(Protocol):
    session: SessionLike

    def login(self) -> Any: ...

    def list_devices(self, station_id: str) -> Any: ...


APIFactory = Callable[..., SolarOfThingsAPILike]


def _solar_api_factory(**kwargs: Any) -> SolarOfThingsAPILike:
    """Load the proven Siseli package without duplicating its auth protocol."""

    try:
        module = import_module("siseli.api")
    except ImportError:
        source_root = Path(__file__).resolve().parents[4] / "energy"
        if not (source_root / "siseli" / "api.py").is_file():
            raise BeveConfigurationError("The proven Siseli integration package is unavailable") from None
        sys.path.insert(0, str(source_root))
        try:
            module = import_module("siseli.api")
        except ImportError:
            raise BeveConfigurationError("The proven Siseli integration package cannot be loaded") from None
        finally:
            try:
                sys.path.remove(str(source_root))
            except ValueError:  # pragma: no cover - defensive
                pass
    return module.SolarOfThingsAPI(**kwargs)


class BeveClient:
    """Authenticate and read device telemetry; no mutation methods are exposed."""

    def __init__(
        self,
        config: BeveConfig,
        *,
        api: SolarOfThingsAPILike | None = None,
        api_factory: APIFactory = _solar_api_factory,
    ) -> None:
        self.config = config
        self._api = api or api_factory(
            user_id=config.username.get_secret_value(),
            password=config.password.get_secret_value(),
            time_zone=config.time_zone,
        )
        self._authenticated = False
        self._device_verified = False

    def login(self) -> None:
        """Delegate proven authentication/signing to the Siseli package."""

        try:
            result = self._api.login()
        except requests.Timeout:
            raise BeveTimeoutError("BEVE login timed out") from None
        except requests.ConnectionError:
            raise BeveConnectionError("BEVE service is unreachable") from None
        except Exception:
            raise BeveAuthenticationError("BEVE login failed") from None
        if result is False:
            raise BeveAuthenticationError("BEVE login failed")
        self._authenticated = True

    def fetch_device(self) -> dict[str, Any]:
        """Fetch and return the configured inverter from the verified device list."""

        self._ensure_login()
        try:
            response = self._api.list_devices(self.config.station_id)
        except requests.Timeout:
            raise BeveTimeoutError("BEVE device request timed out") from None
        except requests.ConnectionError:
            raise BeveConnectionError("BEVE service is unreachable") from None
        except Exception:
            raise BeveCloudError("BEVE cloud device request failed") from None
        devices = self._device_list(response)
        if devices is None:
            raise BeveIncompleteResponseError("BEVE device response is incomplete")
        for device in devices:
            if isinstance(device, Mapping) and str(
                device.get("id") or device.get("deviceId") or device.get("device_id")
            ) == self.config.device_id:
                self._device_verified = True
                return dict(device)
        raise BeveIncompleteResponseError("Configured BEVE device was not returned")

    def fetch_current_telemetry(self) -> dict[str, Any]:
        """Fetch the latest read-only state envelope for the configured inverter."""

        self._ensure_login()
        if not self._device_verified:
            self.fetch_device()
        response = self._telemetry_request()
        if response.status_code in (401, 403):
            self._authenticated = False
            self.login()
            response = self._telemetry_request()
            if response.status_code in (401, 403):
                raise BeveAuthenticationError("BEVE session reauthentication failed")
        data = self._json_mapping(response)
        if data.get("code") not in (0, "0", None):
            raise BeveCloudError("BEVE cloud returned an unsuccessful response")
        payload = data.get("data")
        if not isinstance(payload, dict) or not isinstance(payload.get("fields"), dict):
            raise BeveIncompleteResponseError("BEVE telemetry response is incomplete")
        return data

    def fetch_snapshot(self) -> dict[str, Any]:
        """Compatibility alias for current telemetry reads."""

        return self.fetch_current_telemetry()

    def _ensure_login(self) -> None:
        if not self._authenticated:
            self.login()

    def _telemetry_request(self) -> ResponseLike:
        try:
            response = self._api.session.get(
                f"{self.config.base_url.rstrip('/')}{LATEST_STATE_PATH}",
                params={"deviceId": self.config.device_id, "dataSource": 1},
                timeout=self.config.timeout_seconds,
            )
            if response.status_code not in (401, 403):
                response.raise_for_status()
            return response
        except requests.Timeout:
            raise BeveTimeoutError("BEVE request timed out") from None
        except requests.ConnectionError:
            raise BeveConnectionError("BEVE service is unreachable") from None
        except requests.HTTPError:
            raise BeveCloudError("BEVE cloud returned an error") from None
        except requests.RequestException:
            raise BeveConnectionError("BEVE request failed") from None
        except Exception:
            raise BeveCloudError("BEVE cloud request failed") from None

    @staticmethod
    def _json_mapping(response: ResponseLike) -> dict[str, Any]:
        try:
            data = response.json()
        except (TypeError, ValueError):
            raise BeveMalformedResponseError("BEVE returned malformed JSON") from None
        if not isinstance(data, dict):
            raise BeveMalformedResponseError("BEVE response must be a JSON object")
        return data

    @staticmethod
    def _device_list(response: Any) -> list[Any] | None:
        if isinstance(response, list):
            return response
        if isinstance(response, Mapping):
            payload = response.get("data", response)
            if isinstance(payload, list):
                return payload
            if isinstance(payload, Mapping):
                for key in ("list", "devices"):
                    devices = payload.get(key)
                    if isinstance(devices, list):
                        return devices
        return None


VERIFIED_BEVE_RESPONSE: dict[str, Any] = {
    "timestamp": "2026-09-01T12:19:06Z",
    "inverter": {"status": "Battery Mode", "rated_power_w": 6000, "output_voltage": 219.9,
                 "output_frequency": 50, "output_power_w": 12.0, "load_percentage": 0},
    "battery": {"soc": 100, "voltage": 53.4, "charging_current": 0,
                "discharge_current": 1, "power_w": 61.0, "status": "Discharging Status",
                "charge_stage": "No Charging", "type": "PYLON_485"},
    "solar": {"connected": "PV Not Connected", "pv1_voltage": 0, "pv1_power_w": 0.0,
              "pv2_voltage": 0, "pv2_power_w": 0.0, "total_power_w": 0.0,
              "daily_energy_kwh": 0, "monthly_energy_kwh": 0, "total_energy_kwh": 8},
    "grid": {"voltage": 0.0, "frequency": 0, "power_w": 0.0},
}


class MockBeveClient:
    """Network-free client returning the verified deployed response for tests."""

    def fetch_current_telemetry(self) -> dict[str, Any]:
        return deepcopy(VERIFIED_BEVE_RESPONSE)

    def fetch_snapshot(self) -> dict[str, Any]:
        return self.fetch_current_telemetry()
