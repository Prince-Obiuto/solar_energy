"""Validation and serialization tests for normalized energy domain models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from apps.models import (
    BatteryChargingState,
    BatteryStatus,
    BreakerStatus,
    CommandResult,
    CommandStatus,
    ConnectivityType,
    DataFreshness,
    DataSource,
    DataStatus,
    Device,
    DeviceCapability,
    DeviceCommand,
    DeviceFault,
    DeviceStatus,
    DeviceType,
    ElectricalMeasurement,
    EnergyMeasurement,
    FaultSeverity,
    GridState,
    GridStatus,
    InverterStatus,
    PVStatus,
    SourceStatus,
)


def test_cloud_data_status_does_not_claim_physical_inverter_is_offline() -> None:
    status = DataStatus(
        connectivity_type=ConnectivityType.CLOUD,
        data_source=DataSource.BEVE_CLOUD,
        available=False,
        stale=True,
        source_status=SourceStatus.UNREACHABLE,
        data_freshness=DataFreshness.STALE,
        last_successful_update=datetime(2026, 9, 1, tzinfo=UTC),
    )
    payload = status.model_dump(mode="json")
    assert payload["connectivity_type"] == "cloud"
    assert payload["data_source"] == "beve_cloud"
    assert payload["source_status"] == "unreachable"
    assert "offline" not in payload.values()


def test_device_capabilities_and_faults_serialize_for_transport() -> None:
    device = Device(
        device_id="breaker-test-1",
        name="Test breaker",
        device_type=DeviceType.BREAKER,
        status=DeviceStatus.ONLINE,
        capabilities=DeviceCapability(
            switching=True,
            instantaneous_power=True,
            voltage=True,
            current=True,
            energy_total=True,
            fault_monitoring=True,
            countdown=False,
            remote_configuration=True,
        ),
        faults=[
            DeviceFault(
                code="test_fault",
                message="Test fault",
                severity=FaultSeverity.WARNING,
            )
        ],
    )

    payload = device.model_dump(mode="json")

    assert payload["device_type"] == "breaker"
    assert payload["status"] == "online"
    assert payload["capabilities"] == {
        "switching": True,
        "instantaneous_power": True,
        "voltage": True,
        "current": True,
        "energy_total": True,
        "fault_monitoring": True,
        "countdown": False,
        "remote_configuration": True,
    }
    assert payload["faults"][0]["severity"] == "warning"


def test_unsupported_breaker_measurements_remain_none() -> None:
    breaker = BreakerStatus(
        device_id="breaker-test-2",
        status=DeviceStatus.ONLINE,
        switch_on=True,
        electrical=ElectricalMeasurement(active_power_watts=725.5),
    )

    payload = breaker.model_dump(mode="json")

    assert payload["electrical"]["active_power_watts"] == 725.5
    assert payload["electrical"]["voltage_volts"] is None
    assert payload["electrical"]["current_amperes"] is None
    assert payload["energy"]["total_kwh"] is None
    assert payload["countdown_seconds"] is None
    assert payload["configuration"] is None


def test_inverter_status_contains_normalized_subsystems() -> None:
    status = InverterStatus(
        status=DeviceStatus.ONLINE,
        operating_mode="self_consumption",
        pv=PVStatus(
            electrical=ElectricalMeasurement(
                voltage_volts=365.2,
                current_amperes=5.4,
                active_power_watts=1972.0,
            )
        ),
        output=ElectricalMeasurement(
            voltage_volts=230.1,
            frequency_hz=50.0,
            active_power_watts=1380.0,
            apparent_power_va=None,
        ),
        grid=GridStatus(
            state=GridState.AVAILABLE,
            electrical=ElectricalMeasurement(voltage_volts=229.8, frequency_hz=50.0),
        ),
        battery=BatteryStatus(
            voltage_volts=51.4,
            state_of_charge_percent=78.0,
            current_amperes=None,
            charging_state=BatteryChargingState.CHARGING,
        ),
        load_percent=42.5,
        temperature_celsius=None,
    )

    payload = status.model_dump(mode="json")

    assert payload["grid"]["state"] == "available"
    assert payload["battery"]["charging_state"] == "charging"
    assert payload["output"]["apparent_power_va"] is None
    assert payload["temperature_celsius"] is None


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (BatteryStatus, {"state_of_charge_percent": 101}),
        (InverterStatus, {"load_percent": -1}),
        (BreakerStatus, {"countdown_seconds": -1}),
        (EnergyMeasurement, {"total_kwh": -0.1}),
        (ElectricalMeasurement, {"voltage_volts": float("nan")}),
    ],
)
def test_measurement_ranges_are_validated(model, data) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_device_commands_and_results_round_trip_as_json() -> None:
    timestamp = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    command = DeviceCommand(
        command_id="command-test-1",
        device_id="device-test-1",
        command="set_switch_state",
        parameters={"enabled": True},
        requested_at=timestamp,
    )
    result = CommandResult(
        command_id=command.command_id,
        device_id=command.device_id,
        status=CommandStatus.SUCCEEDED,
        completed_at=timestamp,
    )

    restored_command = DeviceCommand.model_validate_json(command.model_dump_json())
    restored_result = CommandResult.model_validate_json(result.model_dump_json())

    assert restored_command == command
    assert restored_result.status is CommandStatus.SUCCEEDED
