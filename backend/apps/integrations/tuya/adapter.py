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
        try:
            normalized = normalize_tuya_breaker_state(raw_state)
        except (TypeError, ValueError):
            raise TuyaMalformedResponseError("Tuya returned malformed TMPH datapoints") from None

        breaker = BreakerState(
            device_id=config.device_id if config else str(raw_state.get("device_id", "unknown-breaker")),
            name=config.friendly_name if config else str(raw_state.get("name", "breaker")),
            device_type=DeviceType.BREAKER,
            # A successfully received status envelope proves LAN reachability.
            # Relay state is represented independently by switch_on.
            status=DeviceStatus.ONLINE,
            switch_on=normalized["switch_on"],
            electrical=ElectricalMeasurement(
                current_amperes=normalized["current_amperes"],
                voltage_volts=normalized["voltage_volts"],
                active_power_watts=normalized["active_power_watts"],
            ),
            energy=EnergyMeasurement(accumulated_energy=normalized["accumulated_energy"]),
            countdown_seconds=normalized["countdown_seconds"],
            configuration={
                "relay_restore_mode": normalized["relay_restore_mode"],
                "indicator_mode": normalized["indicator_mode"],
                "child_lock": normalized["child_lock"],
            },
            raw_datapoints=normalized["raw_datapoints"],
        )
        return breaker

    def normalize(self, raw_state: Mapping[str, Any]) -> BreakerState:
        """Compatibility wrapper for service-layer usage."""

        return self.from_raw(raw_state)

    def set_switch(self, client: TuyaClient, value: bool) -> dict[str, Any]:
        return client.set_switch_state(value)

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
