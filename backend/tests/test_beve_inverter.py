"""Tests for the verified read-only Siseli inverter integration."""
from __future__ import annotations

from collections import deque
from typing import Any
import pytest
import requests

from apps.integrations.inverter import (
    BeveAuthenticationError, BeveClient, BeveCloudError, BeveConfig,
    BeveConnectionError, BeveIncompleteResponseError, BeveMalformedResponseError,
    BeveTimeoutError, InverterAdapter, MockBeveClient,
)
from apps.integrations.inverter.client import _solar_api_factory


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self.payload, self.status_code = payload, status_code
    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError("fake HTTP failure")
    def json(self) -> Any:
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


class FakeSession:
    def __init__(self, *outcomes: Any) -> None:
        self.outcomes, self.calls = deque(outcomes), []
    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        outcome = self.outcomes.popleft()
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeSolarOfThingsAPI:
    def __init__(self, *, session=None, devices=None, login_outcomes=None) -> None:
        self.session = session or FakeSession()
        self.devices = [{"id": "test-device"}] if devices is None else devices
        self.login_outcomes = deque(login_outcomes or [None])
        self.login_calls, self.station_calls = 0, []
    def login(self) -> None:
        self.login_calls += 1
        outcome = self.login_outcomes.popleft() if self.login_outcomes else None
        if isinstance(outcome, BaseException):
            raise outcome
    def list_devices(self, station_id: str) -> Any:
        self.station_calls.append(station_id)
        if isinstance(self.devices, BaseException):
            raise self.devices
        return self.devices


@pytest.fixture
def beve_config() -> BeveConfig:
    return BeveConfig(base_url="https://solar.siseli.com", username="test-user",
                      password="test-password", station_id="test-station",
                      device_id="test-device", timeout_seconds=2)


def raw_telemetry_response() -> dict[str, Any]:
    def field(value=None, display=None):
        return {"value": value, "valueDisplay": display}
    return {"code": 0, "data": {"time": "2026-09-01T12:19:06Z", "fields": {
        "workingStates": field(display="Battery Mode"), "ratedActivePower": field(6000),
        "outputVoltage": field(219.9), "outputFrequency": field(50),
        "acOutputActivePower": field(0.012), "loadPercentage": field(0),
        "batteryCapacity": field(100), "batteryVoltage": field(53.4),
        "batteryChargingCurrent": field(0), "batteryDischargeCurrent": field(1),
        "batteryPower": field(0.061), "batteryStatus": field(display="Discharging Status"),
        "batteryChargeStep": field(display="No Charging"), "batteryType": field(display="PYLON_485"),
        "pvAccessSign": field(display="PV Not Connected"), "pvInputVoltage": field(0),
        "pvInputPower": field(0), "pv2InputVoltage": field(0), "pv2InputPower": field(0),
        "generationPower": field(0), "pvGeneratedEnergyOfDay": field(0),
        "pvGeneratedEnergyThisMonth": field(0), "totalPVGeneratedEnergy": field(8),
        "acInputVoltage": field(0.0), "acInputFrequency": field(0), "GridPower": field(0.0),
    }}}


def test_factory_receives_only_proven_siseli_credentials(beve_config) -> None:
    captured, api = {}, FakeSolarOfThingsAPI()
    def factory(**kwargs):
        captured.update(kwargs)
        return api
    BeveClient(beve_config, api_factory=factory).login()
    assert captured == {"user_id": "test-user", "password": "test-password", "time_zone": "Africa/Lagos"}
    assert api.login_calls == 1


def test_repository_local_proven_siseli_package_loads_without_network() -> None:
    api = _solar_api_factory(
        user_id="test-user", password="test-password", time_zone="Africa/Lagos"
    )
    assert api.__class__.__name__ == "SolarOfThingsAPI"
    assert callable(api.login)
    assert callable(api.list_devices)


def test_successful_telemetry_read_uses_verified_endpoint(beve_config) -> None:
    session = FakeSession(FakeResponse(raw_telemetry_response()))
    telemetry = InverterAdapter().read(BeveClient(beve_config, api=FakeSolarOfThingsAPI(session=session)))
    assert telemetry.inverter.status == "Battery Mode"
    assert telemetry.inverter.output_power_w == 12.0
    assert telemetry.battery.power_w == 61.0
    assert session.calls[0][0].endswith("/apis/deviceState/simple/state/latest/v1")
    assert session.calls[0][1]["params"] == {"deviceId": "test-device", "dataSource": 1}
    assert session.calls[0][1]["timeout"] == 2
    assert telemetry.timestamp.isoformat() == "2026-09-01T12:19:06+00:00"


def test_fetch_device_uses_siseli_list_devices(beve_config) -> None:
    api = FakeSolarOfThingsAPI(devices=[{"id": "other"}, {"id": "test-device", "name": "Inverter"}])
    assert BeveClient(beve_config, api=api).fetch_device()["name"] == "Inverter"
    assert api.station_calls == ["test-station"]


def test_expired_session_reauthenticates_and_retries(beve_config) -> None:
    session = FakeSession(FakeResponse({}, 401), FakeResponse(raw_telemetry_response()))
    api = FakeSolarOfThingsAPI(session=session, login_outcomes=[None, None])
    assert InverterAdapter().read(BeveClient(beve_config, api=api)).battery.soc == 100
    assert api.login_calls == 2


def test_login_failure_is_normalized_without_credentials(beve_config) -> None:
    api = FakeSolarOfThingsAPI(login_outcomes=[RuntimeError("vendor detail")])
    with pytest.raises(BeveAuthenticationError) as caught:
        BeveClient(beve_config, api=api).login()
    assert "test-user" not in str(caught.value) and "test-password" not in str(caught.value)


@pytest.mark.parametrize(("error", "expected"), [
    (requests.Timeout("detail"), BeveTimeoutError),
    (requests.ConnectionError("detail"), BeveConnectionError),
])
def test_login_transport_errors_are_normalized(beve_config, error, expected) -> None:
    with pytest.raises(expected):
        BeveClient(beve_config, api=FakeSolarOfThingsAPI(login_outcomes=[error])).login()


def test_telemetry_timeout_is_normalized(beve_config) -> None:
    api = FakeSolarOfThingsAPI(session=FakeSession(requests.Timeout()))
    with pytest.raises(BeveTimeoutError):
        BeveClient(beve_config, api=api).fetch_current_telemetry()


def test_remote_service_error_is_cloud_error(beve_config) -> None:
    api = FakeSolarOfThingsAPI(session=FakeSession(FakeResponse({}, 503)))
    with pytest.raises(BeveCloudError):
        BeveClient(beve_config, api=api).fetch_current_telemetry()


def test_incomplete_and_malformed_telemetry_are_rejected(beve_config) -> None:
    incomplete = FakeSolarOfThingsAPI(session=FakeSession(FakeResponse({"code": 0, "data": {}})))
    with pytest.raises(BeveIncompleteResponseError):
        BeveClient(beve_config, api=incomplete).fetch_current_telemetry()
    malformed = FakeSolarOfThingsAPI(session=FakeSession(FakeResponse(ValueError("bad"))))
    with pytest.raises(BeveMalformedResponseError):
        BeveClient(beve_config, api=malformed).fetch_current_telemetry()


def test_verified_zero_values_are_retained() -> None:
    telemetry = InverterAdapter().read(MockBeveClient())
    assert telemetry.inverter.load_percentage == 0
    assert telemetry.battery.charging_current == 0
    assert telemetry.solar.pv1_power_w == 0
    assert telemetry.grid.voltage == telemetry.grid.frequency == telemetry.grid.power_w == 0


def test_missing_supported_fields_become_none() -> None:
    response = raw_telemetry_response()
    fields = response["data"]["fields"]
    fields.pop("pv2InputVoltage"); fields.pop("batteryChargingCurrent"); fields.pop("GridPower")
    telemetry = InverterAdapter().to_telemetry(response)
    assert telemetry.solar.pv2_voltage is None
    assert telemetry.battery.charging_current is None
    assert telemetry.grid.power_w is None


def test_timestamp_is_parsed_as_aware_datetime() -> None:
    assert InverterAdapter().read(MockBeveClient()).timestamp.isoformat() == "2026-09-01T12:19:06+00:00"


def test_client_exposes_no_device_mutation_operations(beve_config) -> None:
    client = BeveClient(beve_config, api=FakeSolarOfThingsAPI())
    prohibited = ("set", "write", "restart", "control", "priority", "update")
    public_methods = [name for name in dir(client) if not name.startswith("_")]
    assert not any(any(word in name.lower() for word in prohibited) for name in public_methods)
