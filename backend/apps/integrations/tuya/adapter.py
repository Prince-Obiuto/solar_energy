"""Vendor-neutral adapter for Tuya breaker data."""

from __future__ import annotations

from typing import Any, Mapping

from apps.models.breaker import BreakerState
from apps.models.device import DeviceStatus, DeviceType
from apps.models.energy_reading import ElectricalMeasurement

from .mapper import normalize_tuya_breaker_state


class TuyaBreakerAdapter:
    """Translate a Tuya payload into the normalized breaker domain model."""

    def from_raw(self, raw_state: Mapping[str, Any]) -> BreakerState:
        normalized = normalize_tuya_breaker_state(raw_state)
        raw_status = str(raw_state.get("switch", raw_state.get("status", "unknown"))).lower()

        status = DeviceStatus.UNKNOWN
        if raw_status in {"on", "true", "1", "open"}:
            status = DeviceStatus.ONLINE
        elif raw_status in {"off", "false", "0", "closed"}:
            status = DeviceStatus.OFFLINE

        breaker = BreakerState(
            device_id=str(raw_state.get("device_id", "unknown-breaker")),
            name=str(raw_state.get("name", "breaker")),
            device_type=DeviceType.BREAKER,
            status=status,
            electrical=ElectricalMeasurement(
                current_amperes=normalized.get("current_amps"),
                voltage_volts=normalized.get("voltage"),
                active_power_watts=normalized.get("power_watts"),
            ),
        )
        return breaker

    def normalize(self, raw_state: Mapping[str, Any]) -> BreakerState:
        """Compatibility wrapper for service-layer usage."""

        return self.from_raw(raw_state)
