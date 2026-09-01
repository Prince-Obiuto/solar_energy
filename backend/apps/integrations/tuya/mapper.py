"""Tuya datapoint normalization helpers.

Actual hardware datapoint names are vendor-specific and must be mapped via
configuration or device metadata. This module intentionally uses a narrow,
normalized representation so the rest of the application never depends on raw
Tuya datapoint names.
"""

from __future__ import annotations

from typing import Any, Mapping

from apps.models.device import DeviceStatus


def normalize_tuya_breaker_state(raw_state: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a raw Tuya breaker payload into application-domain fields."""

    raw_status = str(raw_state.get("switch", raw_state.get("status", "unknown"))).lower()
    if raw_status in {"on", "true", "1", "open"}:
        status = DeviceStatus.ONLINE.value
    elif raw_status in {"off", "false", "0", "closed"}:
        status = DeviceStatus.OFFLINE.value
    else:
        status = DeviceStatus.UNKNOWN.value

    current_ma = raw_state.get("current_ma")
    voltage = raw_state.get("voltage_v") if "voltage_v" in raw_state else raw_state.get("voltage")
    power_watts = (
        raw_state.get("power_w") if "power_w" in raw_state else raw_state.get("power_watts")
    )

    normalized = {
        "status": status,
        "current_amps": round((float(current_ma) / 1000), 3) if current_ma is not None else None,
        "voltage": float(voltage) if voltage is not None else None,
        "power_watts": float(power_watts) if power_watts is not None else None,
    }
    return normalized


normalize_tuya_breaker_status = normalize_tuya_breaker_state
