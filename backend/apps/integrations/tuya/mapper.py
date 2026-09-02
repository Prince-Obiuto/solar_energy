"""Verified TMPH datapoint normalization helpers."""

from __future__ import annotations

from typing import Any, Mapping

from .constants import (
    DIAGNOSTIC_DATAPOINTS, DP_ACCUMULATED_ENERGY, DP_ACTIVE_POWER,
    DP_CHILD_LOCK, DP_COUNTDOWN, DP_CURRENT, DP_INDICATOR_MODE,
    DP_RELAY_RESTORE_MODE, DP_SWITCH, DP_VOLTAGE,
)


def _get(dps: Mapping[Any, Any], key: int) -> Any:
    """Read TinyTuya DPS dictionaries with integer or string keys."""

    return dps[key] if key in dps else dps.get(str(key))


def _scaled(value: Any, divisor: float) -> float | None:
    return float(value) / divisor if value is not None else None


def normalize_tuya_breaker_state(raw_state: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a raw Tuya breaker payload into application-domain fields."""

    dps = raw_state.get("dps")
    if not isinstance(dps, Mapping):
        raise ValueError("Tuya status response does not contain datapoints")
    switch = _get(dps, DP_SWITCH)
    if switch is not None and not isinstance(switch, bool):
        raise ValueError("Tuya switch datapoint is malformed")
    return {
        "switch_on": switch,
        "countdown_seconds": _get(dps, DP_COUNTDOWN),
        "accumulated_energy": _scaled(_get(dps, DP_ACCUMULATED_ENERGY), 1000),
        "current_amperes": _scaled(_get(dps, DP_CURRENT), 1000),
        "active_power_watts": _scaled(_get(dps, DP_ACTIVE_POWER), 10),
        "voltage_volts": _scaled(_get(dps, DP_VOLTAGE), 10),
        "relay_restore_mode": _get(dps, DP_RELAY_RESTORE_MODE),
        "indicator_mode": _get(dps, DP_INDICATOR_MODE),
        "child_lock": _get(dps, DP_CHILD_LOCK),
        "raw_datapoints": {
            str(key): _get(dps, key) for key in DIAGNOSTIC_DATAPOINTS
            if _get(dps, key) is not None
        },
    }


normalize_tuya_breaker_status = normalize_tuya_breaker_state
