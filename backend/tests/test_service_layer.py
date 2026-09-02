"""Service and read-API tests using network-free hardware client mocks."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from apps.integrations.inverter import MockBeveClient
from apps.integrations.tuya.client import TuyaDeviceConfig, TuyaOfflineError
from apps.main import app
from apps.core.permissions import require_staff, require_student
from apps.models import DeviceCapability, DeviceType
from apps.services.breaker_service import (
    BreakerRegistration,
    BreakerService,
    get_breaker_service,
)
from apps.services.device_service import DeviceService, get_device_service
from apps.services.energy_service import EnergyService, get_energy_service
from apps.services.inverter_service import InverterService, get_inverter_service


FIXED_TIME = datetime(2026, 9, 1, 13, 0, tzinfo=UTC)


class MockTuyaClient:
    """Normalized-input Tuya client mock with no TinyTuya or LAN calls."""

    def __init__(self, *, offline: bool = False) -> None:
        self.config = TuyaDeviceConfig(
            device_id="breaker-library-test",
            friendly_name="Library breaker",
            area="Library",
            local_key="test-key-not-a-real-secret",
            ip_address="192.0.2.20",
            protocol_version="3.5",
            enabled=True,
        )
        self.offline = offline
        self.read_count = 0

    def read_status(self) -> dict[str, object]:
        self.read_count += 1
        if self.offline:
            raise TuyaOfflineError("offline")
        return {"dps": {
            "1": True, "9": 0, "17": 1, "18": 0, "19": 0, "20": 0,
            "38": "memory", "40": "relay", "41": False,
        }}


@pytest.fixture
def services():
    inverter = InverterService(MockBeveClient())
    tuya = MockTuyaClient()
    capabilities = DeviceCapability(
        switching=True,
        instantaneous_power=True,
        voltage=True,
        current=True,
        energy_total=True,
        fault_monitoring=True,
        countdown=False,
        remote_configuration=True,
    )
    breakers = BreakerService(
        [BreakerRegistration(client=tuya, capabilities=capabilities)],
        clock=lambda: FIXED_TIME,
    )
    devices = DeviceService(
        inverter,
        breakers,
        inverter_id="inverter-test",
        inverter_name="FiveStar inverter",
        inverter_area="IT Department",
    )
    energy = EnergyService(inverter, breakers)
    return inverter, breakers, devices, energy, tuya


def test_inverter_service_exposes_read_only_categories(services) -> None:
    inverter, *_ = services

    assert inverter.get_inverter_state().status == "Battery Mode"
    assert inverter.get_battery_state().soc == 100
    assert inverter.get_solar_state().total_energy_kwh == 8
    assert inverter.get_grid_state().voltage == 0

    public_methods = [name for name in dir(inverter) if not name.startswith("_")]
    assert not any(word in name for name in public_methods for word in ("set", "write", "control"))


def test_breaker_service_exposes_read_only_status_and_metadata(services) -> None:
    _, breakers, _, _, _ = services

    breaker = breakers.get_breaker("breaker-library-test")

    assert breaker.online is True
    assert breaker.last_seen == FIXED_TIME
    assert breaker.status.switch_on is True
    assert breaker.status.electrical.voltage_volts == 0
    assert breaker.status.electrical.current_amperes == 0
    assert breaker.status.electrical.active_power_watts == 0
    assert breaker.status.energy.accumulated_energy == 0.001
    assert breakers.get_configuration(breaker.id) == {
        "relay_restore_mode": "memory", "indicator_mode": "relay", "child_lock": False,
    }
    assert breakers.get_capabilities(breaker.id).switching is True
    assert breakers.is_online(breaker.id) is True


def test_breaker_service_normalizes_offline_client() -> None:
    client = MockTuyaClient(offline=True)
    service = BreakerService(
        [BreakerRegistration(client=client, capabilities=DeviceCapability())]
    )

    breaker = service.get_breaker(client.config.device_id)

    assert breaker.online is False
    assert breaker.last_seen is None
    assert breaker.status.status.value == "offline"


def test_device_service_returns_unified_secret_free_registry(services) -> None:
    _, _, devices, _, _ = services

    registry = devices.get_devices()

    assert [device.type for device in registry] == [DeviceType.INVERTER, DeviceType.BREAKER]
    assert registry[0].area == "IT Department"
    assert registry[0].online is None
    assert registry[0].connectivity_type.value == "cloud"
    assert registry[0].data_source.value == "beve_cloud"
    assert registry[1].friendly_name == "Library breaker"
    assert registry[1].online is True
    assert registry[1].connectivity_type.value == "local"
    serialized = "".join(device.model_dump_json() for device in registry)
    assert "test-key-not-a-real-secret" not in serialized
    assert "192.0.2.20" not in serialized


def test_energy_service_combines_beve_and_area_breaker_telemetry(services) -> None:
    _, _, _, energy, _ = services

    snapshot = energy.get_latest_snapshot()

    assert snapshot.inverter.status == "Battery Mode"
    assert snapshot.battery.soc == 100
    assert snapshot.solar.pv1_power_w == 0
    assert snapshot.grid.power_w == 0
    assert snapshot.breakers[0].area == "Library"
    assert snapshot.breakers[0].status.energy.accumulated_energy == 0.001


def test_read_api_routes_use_injected_services(client: TestClient, services) -> None:
    inverter, breakers, devices, energy, _ = services
    app.dependency_overrides[get_inverter_service] = lambda: inverter
    app.dependency_overrides[get_breaker_service] = lambda: breakers
    app.dependency_overrides[get_device_service] = lambda: devices
    app.dependency_overrides[get_energy_service] = lambda: energy
    app.dependency_overrides[require_staff] = lambda: None
    app.dependency_overrides[require_student] = lambda: None
    try:
        responses = {
            "devices": client.get("/api/v1/devices"),
            "device": client.get("/api/v1/devices/inverter-test"),
            "inverter": client.get("/api/v1/inverter"),
            "battery": client.get("/api/v1/inverter/battery"),
            "solar": client.get("/api/v1/inverter/solar"),
            "grid": client.get("/api/v1/inverter/grid"),
            "breakers": client.get("/api/v1/breakers"),
            "breaker": client.get("/api/v1/breakers/breaker-library-test"),
            "energy": client.get("/api/v1/energy/latest"),
        }
    finally:
        app.dependency_overrides.clear()

    assert all(response.status_code == 200 for response in responses.values())
    assert responses["devices"].json()["total"] == 2
    assert responses["device"].json()["type"] == "inverter"
    assert responses["battery"].json()["soc"] == 100
    assert responses["grid"].json()["voltage"] == 0
    assert responses["breakers"].json()["items"][0]["area"] == "Library"
    assert responses["energy"].json()["solar"]["pv1_power_w"] == 0


def test_unknown_device_and_breaker_routes_return_404(client: TestClient, services) -> None:
    _, breakers, devices, _, _ = services
    app.dependency_overrides[get_breaker_service] = lambda: breakers
    app.dependency_overrides[get_device_service] = lambda: devices
    app.dependency_overrides[require_staff] = lambda: None
    try:
        device = client.get("/api/v1/devices/missing")
        breaker = client.get("/api/v1/breakers/missing")
    finally:
        app.dependency_overrides.clear()

    assert device.status_code == 404
    assert breaker.status_code == 404
