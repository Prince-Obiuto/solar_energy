"""Read-only adapter from the BEVE client to normalized inverter telemetry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.models import InverterTelemetry
from apps.models.device import DeviceSnapshot, DeviceStatus, DeviceType

from .client import BeveClient, MockBeveClient
from .mapper import map_beve_telemetry, normalize_inverter_snapshot


class InverterAdapter:
    """Expose BEVE monitoring data without any control surface."""

    def read(self, client: BeveClient | MockBeveClient) -> InverterTelemetry:
        return map_beve_telemetry(client.fetch_current_telemetry())

    def to_telemetry(self, raw_snapshot: Mapping[str, Any]) -> InverterTelemetry:
        return map_beve_telemetry(raw_snapshot)

    def from_raw(self, raw_snapshot: Mapping[str, Any]) -> DeviceSnapshot | InverterTelemetry:
        """Preserve the earlier generic adapter contract for non-BEVE fixtures."""

        if "data" in raw_snapshot or "inverter" in raw_snapshot:
            return self.to_telemetry(raw_snapshot)
        normalized = normalize_inverter_snapshot(raw_snapshot)
        raw_status = str(raw_snapshot.get("status", "unknown")).lower()
        status = DeviceStatus.UNKNOWN
        if raw_status in {"online", "ok", "normal", "running"}:
            status = DeviceStatus.ONLINE
        elif raw_status in {"offline", "error", "fault", "stopped"}:
            status = DeviceStatus.OFFLINE
        return DeviceSnapshot(
            device_id=str(raw_snapshot.get("device_id", "unknown-inverter")),
            name=str(raw_snapshot.get("name", "inverter")),
            device_type=DeviceType.INVERTER,
            status=status,
            manufacturer=str(raw_snapshot.get("manufacturer", "unknown")),
            metadata={"normalized": normalized},
        )

    def normalize(self, raw_snapshot: Mapping[str, Any]) -> DeviceSnapshot | InverterTelemetry:
        return self.from_raw(raw_snapshot)
