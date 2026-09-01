"""Inverter telemetry normalization helpers.

The application should consume normalized domain fields such as power in watts and
battery percent, not vendor-specific register names. This module keeps any
hardware-specific mapping behind a narrow adapter boundary.
"""

from __future__ import annotations

from typing import Any, Mapping

from apps.models.device import DeviceStatus


def normalize_inverter_snapshot(raw_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a raw inverter payload into the domain model contract."""

    raw_status = str(raw_snapshot.get("status", "unknown")).lower()
    if raw_status in {"online", "ok", "normal", "running"}:
        status = DeviceStatus.ONLINE.value
    elif raw_status in {"offline", "error", "fault", "stopped"}:
        status = DeviceStatus.OFFLINE.value
    else:
        status = DeviceStatus.UNKNOWN.value

    grid_power = raw_snapshot.get("grid_power_w") or raw_snapshot.get("grid_power_watts")
    pv_power = raw_snapshot.get("pv_power_w") or raw_snapshot.get("pv_power_watts")
    battery_soc = raw_snapshot.get("battery_soc") or raw_snapshot.get("state_of_charge")
    output_power = raw_snapshot.get("output_power_w") or raw_snapshot.get("output_power_watts")

    return {
        "status": status,
        "grid_power_watts": float(grid_power) if grid_power is not None else None,
        "pv_power_watts": float(pv_power) if pv_power is not None else None,
        "output_power_watts": float(output_power) if output_power is not None else None,
        "battery_state_of_charge": float(battery_soc) if battery_soc is not None else None,
    }


normalize_inverter_status = normalize_inverter_snapshot

