"""Device management application service."""

from __future__ import annotations

from apps.models.device import DeviceSnapshot


def get_devices() -> list[DeviceSnapshot]:
    """Return the current device catalogue in normalized domain form."""

    return []


def get_device(device_id: str) -> DeviceSnapshot | None:
    """Return a single device snapshot by identifier or None if it does not exist."""

    return None

