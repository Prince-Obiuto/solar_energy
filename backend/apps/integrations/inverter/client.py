"""Strictly read-only client for the verified BEVE/Solar-of-Things API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from copy import deepcopy
from typing import Any, Protocol

import requests
from Crypto.Cipher import AES
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from apps.core.config import BACKEND_DIR

from .constants import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    DEVICE_LIST_PATH,
    LATEST_STATE_PATH,
    LOGIN_PATH,
    REFRESH_TOKEN_PATH,
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
    app_id: SecretStr
    app_secret_encrypted: SecretStr
    station_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    time_zone: str = "Africa/Lagos"
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0, le=120)


class ResponseLike(Protocol):
    status_code: int

    def raise_for_status(self) -> None: ...

    def json(self) -> Any: ...


class SessionLike(Protocol):
    headers: dict[str, str]

    def post(self, url: str, **kwargs: Any) -> ResponseLike: ...

    def get(self, url: str, **kwargs: Any) -> ResponseLike: ...


class BeveClient:
    """Authenticate and read device telemetry; no mutation methods are exposed."""

    def __init__(self, config: BeveConfig, *, session: SessionLike | None = None) -> None:
        self.config = config
        self._session = session or requests.Session()
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._apply_session_headers()

    def login(self) -> None:
        """Perform the portal's verified signed login flow."""

        password_digest = hashlib.md5(  # noqa: S324 - required by upstream protocol
            self.config.password.get_secret_value().encode("utf-8")
        ).hexdigest()
        payload = {
            "account": self.config.username.get_secret_value(),
            "password": password_digest,
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        response = self._request(
            "post",
            LOGIN_PATH,
            data=body,
            headers=self._signed_headers(body),
            authentication_request=True,
        )
        if response.status_code in (401, 403):
            raise BeveAuthenticationError("BEVE login failed")
        data = self._json_mapping(response)
        if data.get("code") not in (0, "0", None):
            raise BeveAuthenticationError("BEVE login failed")
        self._store_tokens(data.get("data") or data)

    def fetch_device(self) -> dict[str, Any]:
        """Fetch and return the configured inverter from the verified device list."""

        data = self._authenticated_json_request(
            "post",
            DEVICE_LIST_PATH,
            json={"page": 1, "count": 50, "stationId": self.config.station_id},
        )
        payload = data.get("data")
        if not isinstance(payload, dict) or not isinstance(payload.get("list"), list):
            raise BeveIncompleteResponseError("BEVE device response is incomplete")
        for device in payload["list"]:
            if isinstance(device, dict) and str(device.get("id")) == self.config.device_id:
                return device
        raise BeveIncompleteResponseError("Configured BEVE device was not returned")

    def fetch_current_telemetry(self) -> dict[str, Any]:
        """Fetch the latest read-only state envelope for the configured inverter."""

        data = self._authenticated_json_request(
            "get",
            LATEST_STATE_PATH,
            params={"deviceId": self.config.device_id, "dataSource": 1},
        )
        payload = data.get("data")
        if not isinstance(payload, dict) or not isinstance(payload.get("fields"), dict):
            raise BeveIncompleteResponseError("BEVE telemetry response is incomplete")
        return data

    def fetch_snapshot(self) -> dict[str, Any]:
        """Compatibility alias for current telemetry reads."""

        return self.fetch_current_telemetry()

    def _authenticated_json_request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if not self._access_token:
            self.login()
        response = self._request(method, path, **kwargs)
        if response.status_code in (401, 403):
            self._reauthenticate()
            response = self._request(method, path, **kwargs)
            if response.status_code in (401, 403):
                raise BeveAuthenticationError("BEVE session reauthentication failed")
        data = self._json_mapping(response)
        if data.get("code") not in (0, "0", None):
            raise BeveMalformedResponseError("BEVE returned an unsuccessful response")
        return data

    def _reauthenticate(self) -> None:
        if self._refresh_token:
            try:
                response = self._request(
                    "post",
                    REFRESH_TOKEN_PATH,
                    json={"refreshToken": self._refresh_token},
                    authentication_request=True,
                )
                data = self._json_mapping(response)
                if response.status_code not in (401, 403) and data.get("code") in (0, "0", None):
                    self._store_tokens(data.get("data") or data)
                    return
            except BeveIntegrationError:
                pass
        self.login()

    def _store_tokens(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            raise BeveMalformedResponseError("BEVE authentication response is malformed")
        access_token = payload.get("accessToken") or payload.get("iotToken") or payload.get("token")
        if not isinstance(access_token, str) or not access_token:
            raise BeveAuthenticationError("BEVE authentication did not return a session token")
        refresh_token = payload.get("refreshToken")
        self._access_token = access_token
        self._refresh_token = refresh_token if isinstance(refresh_token, str) else None
        self._apply_session_headers()

    def _apply_session_headers(self) -> None:
        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "IOT-Time-Zone": self.config.time_zone,
                "Origin": self.config.base_url,
                "Referer": f"{self.config.base_url}/",
            }
        )
        if self._access_token:
            self._session.headers["IOT-Token"] = self._access_token

    def _request(
        self,
        method: str,
        path: str,
        *,
        authentication_request: bool = False,
        **kwargs: Any,
    ) -> ResponseLike:
        request = getattr(self._session, method)
        try:
            response = request(
                f"{self.config.base_url.rstrip('/')}{path}",
                timeout=self.config.timeout_seconds,
                **kwargs,
            )
            if response.status_code not in (401, 403):
                response.raise_for_status()
            return response
        except requests.Timeout:
            raise BeveTimeoutError("BEVE request timed out") from None
        except requests.ConnectionError:
            raise BeveConnectionError("BEVE service is unreachable") from None
        except requests.HTTPError:
            if authentication_request:
                raise BeveAuthenticationError("BEVE authentication request failed") from None
            raise BeveCloudError("BEVE cloud returned an error") from None
        except requests.RequestException:
            if authentication_request:
                raise BeveAuthenticationError("BEVE authentication request failed") from None
            raise BeveConnectionError("BEVE request failed") from None

    @staticmethod
    def _json_mapping(response: ResponseLike) -> dict[str, Any]:
        try:
            data = response.json()
        except (TypeError, ValueError):
            raise BeveMalformedResponseError("BEVE returned malformed JSON") from None
        if not isinstance(data, dict):
            raise BeveMalformedResponseError("BEVE response must be a JSON object")
        return data

    def _signed_headers(self, body: bytes) -> dict[str, str]:
        app_id = self.config.app_id.get_secret_value()
        encrypted_secret = self.config.app_secret_encrypted.get_secret_value()
        secret = self._decrypt_app_secret(app_id, encrypted_secret)
        nonce = os.urandom(16).hex()
        body_hash = hashlib.sha256(body).hexdigest()
        sign_values = {
            "IOT-Open-AppID": app_id,
            "IOT-Open-Body-Hash": body_hash,
            "IOT-Open-Nonce": nonce,
        }
        query = "&".join(f"{key}={sign_values[key]}" for key in sorted(sign_values))
        encoded = base64.b64encode(query.encode("utf-8"))
        digest = hmac.new(secret.encode("utf-8"), encoded, hashlib.sha256).digest()
        return {
            **sign_values,
            "IOT-Open-Sign": hashlib.md5(digest).hexdigest(),  # noqa: S324 - vendor protocol
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Origin": self.config.base_url,
            "Referer": f"{self.config.base_url}/",
        }

    @staticmethod
    def _decrypt_app_secret(app_id: str, encrypted_secret: str) -> str:
        digest = hashlib.md5(app_id.encode("utf-8")).hexdigest()  # noqa: S324
        cipher = AES.new(digest[:16].encode("ascii"), AES.MODE_CBC, digest[16:].encode("ascii"))
        decrypted = cipher.decrypt(base64.b64decode(encrypted_secret)).rstrip(b"\x00")
        return decrypted.decode("utf-8")


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
