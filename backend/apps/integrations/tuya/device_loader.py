"""Secure loader for TinyTuya wizard-generated ``devices.json`` files."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from apps.core.config import BACKEND_DIR
from apps.models import DeviceCapability
from apps.services.breaker_service import BreakerRegistration

from .client import TuyaClient, TuyaConfigurationError, TuyaDeviceConfig
from .constants import DEFAULT_PROTOCOL_VERSION, TUYA_MODEL, TUYA_PRODUCT_ID

logger = logging.getLogger(__name__)


def resolve_device_file(path: Path | str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else BACKEND_DIR / candidate


def load_breaker_registrations(
    path: Path | str,
    *,
    client_factory: Callable[[TuyaDeviceConfig], Any] = TuyaClient,
) -> list[BreakerRegistration]:
    """Load every valid supported TMPH entry without exposing its secret."""

    device_file = resolve_device_file(path)
    if not device_file.exists():
        logger.info("Tuya device file is not present; no local breakers configured")
        return []
    try:
        document = json.loads(device_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TuyaConfigurationError("Tuya device file cannot be loaded") from None
    return load_breaker_registrations_from_document(
        document,
        client_factory=client_factory,
        require_supported_metadata=True,
        strict=False,
    )


def load_breaker_registrations_from_document(
    document: Any,
    *,
    client_factory: Callable[[TuyaDeviceConfig], Any] = TuyaClient,
    require_supported_metadata: bool = False,
    strict: bool = True,
) -> list[BreakerRegistration]:
    """Build registrations from an internal document without touching a file."""

    configs = parse_breaker_configs(
        _entries(document),
        require_supported_metadata=require_supported_metadata,
        strict=strict,
    )
    return [
        BreakerRegistration(client=client_factory(config), capabilities=_capabilities())
        for config in configs
    ]


def parse_breaker_configs(
    entries: list[Any],
    *,
    require_supported_metadata: bool,
    strict: bool,
) -> list[TuyaDeviceConfig]:
    """Validate file/onboarding entries while preserving the existing shape."""

    configs: list[TuyaDeviceConfig] = []
    seen: set[str] = set()
    skipped = 0
    for entry in entries:
        if not isinstance(entry, Mapping) or (
            require_supported_metadata and not _supported(entry)
        ):
            if strict:
                raise TuyaConfigurationError("Tuya device configuration is invalid")
            skipped += 1
            continue
        try:
            config = TuyaDeviceConfig(
                device_id=entry.get("id"),
                friendly_name=entry.get("name"),
                area=entry.get("area") or entry.get("name"),
                local_key=entry.get("key"),
                ip_address=entry.get("ip"),
                protocol_version=str(entry.get("version") or entry.get("ver") or DEFAULT_PROTOCOL_VERSION),
                enabled=entry.get("enabled", True),
            )
        except ValidationError:
            if strict:
                raise TuyaConfigurationError("Tuya device configuration is invalid") from None
            skipped += 1
            continue
        if config.device_id in seen:
            if strict:
                raise TuyaConfigurationError("Tuya device configuration contains duplicates")
            skipped += 1
            continue
        seen.add(config.device_id)
        configs.append(config)
    logger.info("Loaded %d supported Tuya breakers", len(configs))
    if skipped:
        logger.warning("Skipped %d unsupported or incomplete Tuya entries", skipped)
    return configs


def _capabilities() -> DeviceCapability:
    return DeviceCapability(
        switching=True,
        instantaneous_power=True,
        voltage=True,
        current=True,
        energy_total=True,
        countdown=True,
        remote_configuration=True,
    )


def _entries(document: Any) -> list[Any]:
    if isinstance(document, list):
        return document
    if isinstance(document, Mapping):
        for key in ("devices", "result", "data"):
            value = document.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, Mapping) and isinstance(value.get("devices"), list):
                return value["devices"]
    raise TuyaConfigurationError("Tuya device file has an unsupported structure")


def _supported(entry: Mapping[str, Any]) -> bool:
    model = str(entry.get("model") or "").strip().upper()
    product_id = str(entry.get("product_id") or entry.get("productId") or "").strip()
    # Wizard versions do not always retain product metadata. When it exists,
    # require a verified match; otherwise accept a complete local device entry.
    if model or product_id:
        return model == TUYA_MODEL or product_id == TUYA_PRODUCT_ID
    return True
