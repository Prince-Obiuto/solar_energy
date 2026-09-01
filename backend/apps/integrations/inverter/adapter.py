"""Vendor-neutral adapter for inverter telemetry."""

from __future__ import annotations

from typing import Any, Mapping

from apps.models.device import DeviceSnapshot, DeviceStatus, DeviceType

from .mapper import normalize_inverter_snapshot


class InverterAdapter:
    """Translate a raw inverter payload into the application domain model."""

    def from_raw(self, raw_snapshot: Mapping[str, Any]) -> DeviceSnapshot:
        normalized = normalize_inverter_snapshot(raw_snapshot)
        raw_status = str(raw_snapshot.get("status", "unknown")).lower()

        status = DeviceStatus.UNKNOWN
        if raw_status in {"online", "ok", "normal", "running"}:
            status = DeviceStatus.ONLINE
        elif raw_status in {"offline", "error", "fault", "stopped"}:
            status = DeviceStatus.OFFLINE

        snapshot = DeviceSnapshot(
            device_id=str(raw_snapshot.get("device_id", "unknown-inverter")),
            name=str(raw_snapshot.get("name", "inverter")),
            device_type=DeviceType.INVERTER,
            status=status,
            manufacturer=str(raw_snapshot.get("manufacturer", "unknown")),
            metadata={"vendor": "inverter", "normalized": normalized, "raw": dict(raw_snapshot)},
        )
        return snapshot

    def normalize(self, raw_snapshot: Mapping[str, Any]) -> DeviceSnapshot:
        """Compatibility wrapper for service-layer usage."""

        return self.from_raw(raw_snapshot)

