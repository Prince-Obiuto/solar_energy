"""Direct TinyTuya cloud and LAN discovery APIs used only during onboarding."""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import requests
import tinytuya
from tinytuya import scanner
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from apps.core.config import parse_tuya_discovery_networks


@contextmanager
def _quiet_scanner_logs():
    """Vendor DEBUG records include keys; suppress this scan thread's records."""

    thread_id = threading.get_ident()

    class ScanLogFilter(logging.Filter):
        def filter(self, record):
            return record.thread != thread_id

    scan_filter = ScanLogFilter()
    loggers = [logging.getLogger(name) for name in list(logging.Logger.manager.loggerDict)
               if name == "tinytuya" or name.startswith("tinytuya.")]
    for logger in loggers:
        logger.addFilter(scan_filter)
    try:
        yield
    finally:
        for logger in loggers:
            logger.removeFilter(scan_filter)


class TuyaOnboardingIntegrationError(Exception):
    """Base error whose message never includes vendor response data."""


class TuyaCloudAuthenticationError(TuyaOnboardingIntegrationError):
    pass


class TuyaCloudDeviceFetchError(TuyaOnboardingIntegrationError):
    pass


class TuyaCloudConfigurationError(TuyaOnboardingIntegrationError):
    pass


class TuyaCloudNetworkError(TuyaOnboardingIntegrationError):
    pass


class TuyaCloudTimeoutError(TuyaOnboardingIntegrationError):
    pass


class TuyaCloudMalformedResponseError(TuyaOnboardingIntegrationError):
    pass


class TuyaScanError(TuyaOnboardingIntegrationError):
    pass


class TuyaScanTimeoutError(TuyaScanError):
    pass


class TuyaCloudConfig(BaseModel):
    """The exact credential inputs supported by TinyTuya 1.20 Cloud."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region: str = Field(min_length=1, max_length=10)
    access_id: SecretStr = Field(min_length=1, max_length=255)
    access_secret: SecretStr = Field(min_length=1, max_length=1024)
    anchor_device_id: SecretStr | None = None

    @field_validator("region")
    @classmethod
    def normalize_region(cls, value: str) -> str:
        normalized = value.strip().lower()
        aliases = {"az": "us", "ue": "us-e", "we": "eu-w"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"cn", "us", "us-e", "eu", "eu-w", "in", "sg"}:
            raise ValueError("Unsupported Tuya cloud region")
        return normalized


@dataclass(frozen=True, slots=True, repr=False)
class TuyaCloudDevice:
    """Internal cloud result; local_key is never serialized to an API response."""

    device_id: str
    local_key: SecretStr | None
    name: str | None = None
    product_id: str | None = None
    category: str | None = None
    model: str | None = None
    online: bool | None = None
    protocol_version: str | None = None

    def __repr__(self) -> str:
        return "TuyaCloudDevice(<redacted>)"


@dataclass(frozen=True, slots=True)
class TuyaLanDevice:
    device_id: str
    ip_address: str
    protocol_version: str | None
    product_id: str | None = None


CloudFactory = Callable[..., Any]
ScanFunction = Callable[..., Any]
FindFunction = Callable[..., Any]


class TinyTuyaCloudGateway:
    """Fetch local keys via TinyTuya Cloud without retaining its credentials."""

    def __init__(self, cloud_factory: CloudFactory = tinytuya.Cloud) -> None:
        self.cloud_factory = cloud_factory

    def get_devices(self, config: TuyaCloudConfig) -> list[TuyaCloudDevice]:
        cloud = None
        try:
            cloud = self.cloud_factory(
                apiRegion=config.region,
                apiKey=config.access_id.get_secret_value(),
                apiSecret=config.access_secret.get_secret_value(),
                apiDeviceID=(
                    config.anchor_device_id.get_secret_value()
                    if config.anchor_device_id is not None
                    else None
                ),
            )
            response = cloud.getdevices()
            self._raise_cloud_error(response)
            if not isinstance(response, list):
                raise TuyaCloudMalformedResponseError(
                    "Tuya Cloud returned an invalid device list."
                )
            devices = [self._device(item) for item in response if isinstance(item, Mapping)]
            devices = [device for device in devices if device is not None]
            if not devices:
                raise TuyaCloudDeviceFetchError("No Tuya Cloud devices were returned.")
            return devices[:100]
        except TuyaOnboardingIntegrationError:
            raise
        except (requests.Timeout, socket.timeout, TimeoutError):
            raise TuyaCloudTimeoutError("Tuya Cloud request timed out.") from None
        except (requests.ConnectionError, OSError):
            raise TuyaCloudNetworkError("Tuya Cloud is unreachable.") from None
        except (TypeError, ValueError):
            raise TuyaCloudConfigurationError(
                "Tuya Cloud configuration is invalid."
            ) from None
        except Exception:
            raise TuyaCloudDeviceFetchError(
                "Tuya Cloud device retrieval failed."
            ) from None
        finally:
            # TinyTuya's Cloud object stores these values as attributes. Remove
            # them promptly even when the caller's injected test double survives.
            if cloud is not None:
                for attribute in ("apiKey", "apiSecret", "token", "apiDeviceID"):
                    try:
                        setattr(cloud, attribute, None)
                    except Exception:
                        pass

    @staticmethod
    def _raise_cloud_error(response: Any) -> None:
        if not isinstance(response, Mapping):
            return
        if "Error" not in response and "Err" not in response:
            return
        code = str(response.get("Err", ""))
        if code in {"909", "911"}:
            raise TuyaCloudAuthenticationError("Tuya Cloud authentication failed.")
        raise TuyaCloudDeviceFetchError("Tuya Cloud device retrieval failed.")

    @staticmethod
    def _device(item: Mapping[str, Any]) -> TuyaCloudDevice | None:
        device_id = item.get("id") or item.get("device_id") or item.get("dev_id")
        if not isinstance(device_id, str) or not device_id.strip():
            return None
        raw_key = item.get("key") or item.get("local_key")
        local_key = (
            SecretStr(raw_key.strip())
            if isinstance(raw_key, str) and raw_key.strip() and raw_key.strip().lower() != "none"
            else None
        )
        version = item.get("version") or item.get("ver")
        return TuyaCloudDevice(
            device_id=device_id.strip(),
            local_key=local_key,
            name=_optional_text(item.get("name") or item.get("product_name")),
            product_id=_optional_text(
                item.get("product_id") or item.get("productId") or item.get("productKey")
            ),
            category=_optional_text(item.get("category")),
            model=_optional_text(item.get("model")),
            online=item.get("online") if isinstance(item.get("online"), bool) else None,
            protocol_version=_optional_text(version),
        )


class TinyTuyaLanDiscovery:
    """Bounded direct-Python discovery with exact-device-ID fallback."""

    def __init__(
        self,
        *,
        scan: ScanFunction = tinytuya.deviceScan,
        find: FindFunction = tinytuya.find_device,
        force_scan: ScanFunction = scanner.devices,
    ) -> None:
        self.scan_function = scan
        self.find_function = find
        self.force_scan_function = force_scan

    def scan_routed(
        self, *, networks: str, devices: list[TuyaCloudDevice],
    ) -> dict[str, TuyaLanDevice]:
        """Scan only approved CIDRs using temporary cloud keys, without files."""

        temporary_devices = []
        try:
            approved = parse_tuya_discovery_networks(networks)
            if not approved:
                return {}
            temporary_devices = [
                {"id": device.device_id, "key": device.local_key.get_secret_value(), "name": ""}
                for device in devices[:100] if device.local_key is not None
            ]
            if not temporary_devices:
                return {}
            wanted_ids = {device["id"] for device in temporary_devices}
            with _quiet_scanner_logs():
                response = self.force_scan_function(
                    forcescan=[str(network) for network in approved],
                    verbose=False,
                    discover=False,
                    assume_yes=True,
                    tuyadevices=temporary_devices,
                    byID=True,
                    wantids=sorted(wanted_ids),
                    color=False,
                    poll=False,
                    show_timer=False,
                )
            if not isinstance(response, Mapping):
                raise TuyaScanError("Tuya LAN scan returned an invalid response.")
            return {
                device_id: device
                for device_id, device in self._normalize_many(response).items()
                if device_id in wanted_ids
                and isinstance(address := ipaddress.ip_address(device.ip_address), ipaddress.IPv4Address)
                and any(address in network for network in approved)
            }
        except (socket.timeout, TimeoutError):
            raise TuyaScanTimeoutError("Tuya LAN scan timed out.") from None
        except Exception:
            raise TuyaScanError("Tuya LAN scan failed.") from None
        finally:
            for device in temporary_devices:
                device.clear()
            temporary_devices.clear()

    def scan(self, *, maxretry: int) -> dict[str, TuyaLanDevice]:
        try:
            response = self.scan_function(
                verbose=False,
                maxretry=maxretry,
                color=False,
                poll=False,
                forcescan=False,
                byID=True,
            )
        except (socket.timeout, TimeoutError):
            raise TuyaScanTimeoutError("Tuya LAN scan timed out.") from None
        except Exception:
            raise TuyaScanError("Tuya LAN scan failed.") from None
        if not isinstance(response, Mapping):
            raise TuyaScanError("Tuya LAN scan returned an invalid response.")
        return self._normalize_many(response)

    def find_exact(self, device_id: str) -> TuyaLanDevice | None:
        try:
            response = self.find_function(dev_id=device_id)
        except (socket.timeout, TimeoutError):
            return None
        except Exception:
            return None
        if not isinstance(response, Mapping):
            return None
        normalized = self._normalize_one(device_id, response)
        return normalized if normalized and normalized.device_id == device_id else None

    @classmethod
    def _normalize_many(cls, response: Mapping[Any, Any]) -> dict[str, TuyaLanDevice]:
        devices: dict[str, TuyaLanDevice] = {}
        for key, item in response.items():
            if not isinstance(item, Mapping):
                continue
            normalized = cls._normalize_one(str(key), item)
            if normalized is not None:
                devices[normalized.device_id] = normalized
        return devices

    @staticmethod
    def _normalize_one(key: str, item: Mapping[str, Any]) -> TuyaLanDevice | None:
        key_is_ip = _is_ip(key)
        device_id = (
            item.get("id")
            or item.get("gwId")
            or item.get("device_id")
            or item.get("dev_id")
            or (None if key_is_ip else key)
        )
        address = item.get("ip") or item.get("address") or (key if key_is_ip else None)
        if not isinstance(device_id, str) or not device_id.strip() or not _is_ip(address):
            return None
        version = item.get("version") or item.get("ver")
        return TuyaLanDevice(
            device_id=device_id.strip(),
            ip_address=str(address),
            protocol_version=_optional_text(version),
            product_id=_optional_text(
                item.get("product_id") or item.get("productId") or item.get("productKey")
            ),
        )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _is_ip(value: Any) -> bool:
    try:
        ipaddress.ip_address(str(value))
        return True
    except ValueError:
        return False


__all__ = [
    "TinyTuyaCloudGateway",
    "TinyTuyaLanDiscovery",
    "TuyaCloudAuthenticationError",
    "TuyaCloudConfig",
    "TuyaCloudConfigurationError",
    "TuyaCloudDevice",
    "TuyaCloudDeviceFetchError",
    "TuyaCloudMalformedResponseError",
    "TuyaCloudNetworkError",
    "TuyaCloudTimeoutError",
    "TuyaLanDevice",
    "TuyaOnboardingIntegrationError",
    "TuyaScanError",
    "TuyaScanTimeoutError",
]
