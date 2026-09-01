"""Vendor-neutral adapter for Tuya breaker data."""

from __future__ import annotations

from typing import Any, Mapping

from apps.models.breaker import BreakerState
from apps.models.device import DeviceStatus, DeviceType
from apps.models.energy_reading import ElectricalMeasurement, EnergyMeasurement

from .mapper import normalize_tuya_breaker_state
from .client import TuyaClient, TuyaDeviceConfig, TuyaMalformedResponseError
from .constants import (
    DP_CHILD_LOCK, DP_COUNTDOWN, DP_INDICATOR_MODE, DP_RELAY_RESTORE_MODE, DP_SWITCH,
    INDICATOR_MODES, RELAY_RESTORE_MODES,
)


class TuyaBreakerAdapter:
    """Translate a Tuya payload into the normalized breaker domain model."""

    def read(self, client: TuyaClient) -> BreakerState:
        """Read through the client and return only a normalized domain object."""

        return self.from_raw(client.read_status(), config=client.config)

    def from_raw(
        self,
        raw_state: Mapping[str, Any],
        *,
        config: TuyaDeviceConfig | None = None,
    ) -> BreakerState:
        normalized = normalize_tuya_breaker_state(raw_state)
        raw_status = str(raw_state.get("switch", raw_state.get("status", "unknown"))).lower()
        switch_on: bool | None = None

        status = DeviceStatus.UNKNOWN
        if raw_status in {"on", "true", "1", "open"}:
            status = DeviceStatus.ONLINE
            switch_on = True
        elif raw_status in {"off", "false", "0", "closed"}:
            status = DeviceStatus.OFFLINE
            switch_on = False

        breaker = BreakerState(
            device_id=config.device_id if config else str(raw_state.get("device_id", "unknown-breaker")),
            name=config.friendly_name if config else str(raw_state.get("name", "breaker")),
            device_type=DeviceType.BREAKER,
            status=status,
            switch_on=switch_on,
            electrical=ElectricalMeasurement(
                current_amperes=normalized.get("current_amps"),
                voltage_volts=normalized.get("voltage"),
                active_power_watts=normalized.get("power_watts"),
            ),
            energy=EnergyMeasurement(total_kwh=raw_state.get("energy_total_kwh")),
            countdown_seconds=raw_state.get("countdown_seconds"),
            configuration=raw_state.get("configuration"),
        )
        return breaker

    def normalize(self, raw_state: Mapping[str, Any]) -> BreakerState:
        """Compatibility wrapper for service-layer usage."""

        return self.from_raw(raw_state)

    def set_switch(self, client: TuyaClient, value: bool) -> dict[str, Any]:
        return client.write_datapoint(DP_SWITCH, value)

    def set_countdown(self, client: TuyaClient, seconds: int) -> dict[str, Any]:
        if not 0 <= seconds <= 86400:
            raise ValueError("Countdown must be between 0 and 86400 seconds")
        return client.write_datapoint(DP_COUNTDOWN, seconds)

    def set_relay_restore_mode(self, client: TuyaClient, mode: str) -> dict[str, Any]:
        if mode not in RELAY_RESTORE_MODES:
            raise ValueError("Invalid relay restore mode")
        return client.write_datapoint(DP_RELAY_RESTORE_MODE, mode)

    def set_indicator_mode(self, client: TuyaClient, mode: str) -> dict[str, Any]:
        if mode not in INDICATOR_MODES:
            raise ValueError("Invalid indicator mode")
        return client.write_datapoint(DP_INDICATOR_MODE, mode)

    def set_child_lock(self, client: TuyaClient, value: bool) -> dict[str, Any]:
        return client.write_datapoint(DP_CHILD_LOCK, value)

    def read_control_value(self, client: TuyaClient, datapoint: int) -> Any:
        response = client.read_status()
        dps = response.get("dps")
        if not isinstance(dps, Mapping):
            raise TuyaMalformedResponseError("Tuya status response does not contain datapoints")
        if str(datapoint) in dps:
            return dps[str(datapoint)]
        if datapoint in dps:
            return dps[datapoint]
        raise TuyaMalformedResponseError("Tuya verification datapoint is unavailable")
