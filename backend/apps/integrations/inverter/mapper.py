"""Map verified BEVE fields into normalized read-only telemetry categories."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from apps.models import InverterTelemetry
from apps.models.device import DeviceStatus


class BeveMappingError(ValueError):
    """Raised when a BEVE payload cannot form valid normalized telemetry."""


def map_beve_telemetry(raw: Mapping[str, Any]) -> InverterTelemetry:
    """Map an API envelope or verified normalized fixture into the domain model."""

    if all(category in raw for category in ("inverter", "battery", "solar", "grid")):
        normalized = dict(raw)
    else:
        data = raw.get("data")
        if not isinstance(data, Mapping):
            raise BeveMappingError("BEVE telemetry payload has no data object")
        fields = data.get("fields")
        if not isinstance(fields, Mapping):
            raise BeveMappingError("BEVE telemetry payload has no fields object")

        def value(key: str) -> Any:
            field = fields.get(key)
            return field.get("value") if isinstance(field, Mapping) else None

        def display(key: str) -> Any:
            field = fields.get(key)
            return field.get("valueDisplay") if isinstance(field, Mapping) else None

        def kilowatts_to_watts(key: str) -> float | None:
            raw_value = value(key)
            if raw_value is None:
                return None
            try:
                return round(float(raw_value) * 1000, 2)
            except (TypeError, ValueError):
                raise BeveMappingError(f"BEVE field {key} is not numeric") from None

        normalized = {
            "timestamp": data.get("time"),
            "inverter": {
                "status": display("workingStates"),
                "rated_power_w": value("ratedActivePower"),
                "output_voltage": value("outputVoltage"),
                "output_frequency": value("outputFrequency"),
                "output_power_w": kilowatts_to_watts("acOutputActivePower"),
                "load_percentage": value("loadPercentage"),
            },
            "battery": {
                "soc": value("batteryCapacity"),
                "voltage": value("batteryVoltage"),
                "charging_current": value("batteryChargingCurrent"),
                "discharge_current": value("batteryDischargeCurrent"),
                "power_w": kilowatts_to_watts("batteryPower"),
                "status": display("batteryStatus"),
                "charge_stage": display("batteryChargeStep"),
                "type": display("batteryType"),
            },
            "solar": {
                "connected": display("pvAccessSign"),
                "pv1_voltage": value("pvInputVoltage"),
                "pv1_power_w": kilowatts_to_watts("pvInputPower"),
                "pv2_voltage": value("pv2InputVoltage"),
                "pv2_power_w": kilowatts_to_watts("pv2InputPower"),
                "total_power_w": kilowatts_to_watts("generationPower"),
                "daily_energy_kwh": value("pvGeneratedEnergyOfDay"),
                "monthly_energy_kwh": value("pvGeneratedEnergyThisMonth"),
                "total_energy_kwh": value("totalPVGeneratedEnergy"),
            },
            "grid": {
                "voltage": value("acInputVoltage"),
                "frequency": value("acInputFrequency"),
                "power_w": kilowatts_to_watts("GridPower"),
            },
        }

    try:
        return InverterTelemetry.model_validate(normalized)
    except ValidationError as exc:
        raise BeveMappingError("BEVE telemetry values are invalid") from exc


def normalize_inverter_snapshot(raw_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Compatibility normalizer plus the verified BEVE normalized contract."""

    if "data" in raw_snapshot or "inverter" in raw_snapshot:
        return map_beve_telemetry(raw_snapshot).model_dump(mode="json")

    raw_status = str(raw_snapshot.get("status", "unknown")).lower()
    if raw_status in {"online", "ok", "normal", "running"}:
        status = DeviceStatus.ONLINE.value
    elif raw_status in {"offline", "error", "fault", "stopped"}:
        status = DeviceStatus.OFFLINE.value
    else:
        status = DeviceStatus.UNKNOWN.value

    def first_present(*keys: str) -> Any:
        return next((raw_snapshot[key] for key in keys if key in raw_snapshot), None)

    return {
        "status": status,
        "grid_power_watts": first_present("grid_power_w", "grid_power_watts"),
        "pv_power_watts": first_present("pv_power_w", "pv_power_watts"),
        "output_power_watts": first_present("output_power_w", "output_power_watts"),
        "battery_state_of_charge": first_present("battery_soc", "state_of_charge"),
    }


normalize_inverter_status = normalize_inverter_snapshot
