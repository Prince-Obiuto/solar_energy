"""Tests for normalized device/inverter integration contracts and API routes."""

from apps.integrations.inverter.adapter import InverterAdapter
from apps.integrations.inverter.mapper import normalize_inverter_snapshot
from apps.integrations.tuya.adapter import TuyaBreakerAdapter
from apps.integrations.tuya.mapper import normalize_tuya_breaker_state
from apps.models.device import DeviceStatus, DeviceType
from apps.core.permissions import require_staff, require_student
from apps.main import app


def test_tuya_breaker_normalizer_maps_state_to_domain_model() -> None:
    normalized = normalize_tuya_breaker_state(
        {
            "switch": "on",
            "current_ma": 8500,
            "voltage_v": 230.0,
            "power_w": 1500,
        }
    )

    assert normalized["status"] == DeviceStatus.ONLINE.value
    assert normalized["current_amps"] == 8.5
    assert normalized["power_watts"] == 1500


def test_inverter_snapshot_normalizer_uses_domain_fields() -> None:
    normalized = normalize_inverter_snapshot(
        {
            "status": "online",
            "grid_power_w": 800,
            "pv_power_w": 2000,
            "battery_soc": 82,
        }
    )

    assert normalized["status"] == DeviceStatus.ONLINE.value
    assert normalized["grid_power_watts"] == 800
    assert normalized["pv_power_watts"] == 2000
    assert normalized["battery_state_of_charge"] == 82


def test_vendor_adapters_build_domain_objects() -> None:
    breaker = TuyaBreakerAdapter().from_raw({"switch": "off"})
    assert breaker.device_type == DeviceType.BREAKER
    assert breaker.status == DeviceStatus.OFFLINE

    inverter = InverterAdapter().from_raw({"status": "online"})
    assert inverter.device_type == DeviceType.INVERTER
    assert inverter.status == DeviceStatus.ONLINE


def test_device_and_energy_routes_are_available(client) -> None:
    app.dependency_overrides[require_staff] = lambda: None
    app.dependency_overrides[require_student] = lambda: None
    try:
        devices = client.get("/api/v1/devices")
        energy = client.get("/api/v1/energy")
    finally:
        app.dependency_overrides.clear()

    assert devices.status_code == 200
    assert devices.json()["items"] == []
    assert energy.status_code == 200
    assert energy.json()["items"] == []
