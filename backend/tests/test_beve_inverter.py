"""Tests for the verified read-only BEVE inverter integration."""

from __future__ import annotations

import base64
import hashlib
from collections import deque
from typing import Any

import pytest
import requests
from Crypto.Cipher import AES

from apps.integrations.inverter import (
    BeveAuthenticationError,
    BeveClient,
    BeveConfig,
    BeveConnectionError,
    BeveIncompleteResponseError,
    BeveMalformedResponseError,
    BeveTimeoutError,
    InverterAdapter,
    MockBeveClient,
)


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError("fake HTTP failure")

    def json(self) -> Any:
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


class FakeSession:
    """Queue-backed requests.Session fake with no network access."""

    def __init__(self, *, posts: list[Any] | None = None, gets: list[Any] | None = None) -> None:
        self.headers: dict[str, str] = {}
        self.posts = deque(posts or [])
        self.gets = deque(gets or [])
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("post", url, kwargs))
        return self._next(self.posts)

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("get", url, kwargs))
        return self._next(self.gets)

    @staticmethod
    def _next(queue: deque[Any]) -> FakeResponse:
        outcome = queue.popleft()
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def encrypted_test_app_secret(app_id: str, secret: str) -> str:
    digest = hashlib.md5(app_id.encode()).hexdigest()
    plaintext = secret.encode()
    plaintext += b"\x00" * ((16 - len(plaintext) % 16) % 16)
    cipher = AES.new(digest[:16].encode(), AES.MODE_CBC, digest[16:].encode())
    return base64.b64encode(cipher.encrypt(plaintext)).decode()


@pytest.fixture
def beve_config() -> BeveConfig:
    app_id = "test-app-id"
    return BeveConfig(
        base_url="https://beve.invalid",
        username="test-user",
        password="test-password",
        app_id=app_id,
        app_secret_encrypted=encrypted_test_app_secret(app_id, "test-app-secret"),
        station_id="test-station",
        device_id="test-device",
        timeout_seconds=2,
    )


def login_response(*, refresh: bool = True) -> FakeResponse:
    tokens = {"accessToken": "test-session-token"}
    if refresh:
        tokens["refreshToken"] = "test-refresh-token"
    return FakeResponse({"code": 0, "data": tokens})


def raw_telemetry_response() -> dict[str, Any]:
    def field(value: Any = None, display: Any = None) -> dict[str, Any]:
        return {"value": value, "valueDisplay": display}

    return {
        "code": 0,
        "data": {
            "time": "2026-09-01T12:19:06Z",
            "fields": {
                "workingStates": field(display="Battery Mode"),
                "ratedActivePower": field(6000),
                "outputVoltage": field(219.9),
                "outputFrequency": field(50),
                "acOutputActivePower": field(0.012),
                "loadPercentage": field(0),
                "batteryCapacity": field(100),
                "batteryVoltage": field(53.4),
                "batteryChargingCurrent": field(0),
                "batteryDischargeCurrent": field(1),
                "batteryPower": field(0.061),
                "batteryStatus": field(display="Discharging Status"),
                "batteryChargeStep": field(display="No Charging"),
                "batteryType": field(display="PYLON_485"),
                "pvAccessSign": field(display="PV Not Connected"),
                "pvInputVoltage": field(0),
                "pvInputPower": field(0),
                "pv2InputVoltage": field(0),
                "pv2InputPower": field(0),
                "generationPower": field(0),
                "pvGeneratedEnergyOfDay": field(0),
                "pvGeneratedEnergyThisMonth": field(0),
                "totalPVGeneratedEnergy": field(8),
                "acInputVoltage": field(0.0),
                "acInputFrequency": field(0),
                "GridPower": field(0.0),
            },
        },
    }


def test_successful_login_stores_session_without_exposing_token(beve_config) -> None:
    session = FakeSession(posts=[login_response()])
    client = BeveClient(beve_config, session=session)

    client.login()

    assert session.headers["IOT-Token"] == "test-session-token"
    assert "test-session-token" not in repr(client)
    assert session.calls[0][0] == "post"
    assert session.calls[0][1].endswith("/apis/login/account")


def test_successful_telemetry_read_and_mapping(beve_config) -> None:
    session = FakeSession(posts=[login_response()], gets=[FakeResponse(raw_telemetry_response())])
    client = BeveClient(beve_config, session=session)

    telemetry = InverterAdapter().read(client)

    assert telemetry.inverter.status == "Battery Mode"
    assert telemetry.inverter.output_power_w == 12.0
    assert telemetry.battery.power_w == 61.0
    assert session.calls[-1][2]["params"] == {"deviceId": "test-device", "dataSource": 1}


def test_fetch_device_selects_configured_device(beve_config) -> None:
    device_response = FakeResponse(
        {
            "code": 0,
            "data": {
                "total": 2,
                "list": [{"id": "another-device"}, {"id": "test-device", "name": "Inverter"}],
            },
        }
    )
    session = FakeSession(posts=[login_response(), device_response])

    device = BeveClient(beve_config, session=session).fetch_device()

    assert device == {"id": "test-device", "name": "Inverter"}
    assert session.calls[-1][2]["json"]["stationId"] == "test-station"


def test_expired_session_reauthenticates_and_retries(beve_config) -> None:
    session = FakeSession(
        posts=[login_response(refresh=False), login_response(refresh=False)],
        gets=[FakeResponse({"code": 401}, 401), FakeResponse(raw_telemetry_response())],
    )
    client = BeveClient(beve_config, session=session)

    assert InverterAdapter().read(client).battery.soc == 100
    login_calls = [call for call in session.calls if call[1].endswith("/apis/login/account")]
    assert len(login_calls) == 2


def test_expired_session_uses_refresh_token_before_relogin(beve_config) -> None:
    refreshed = FakeResponse({"code": 0, "data": {"accessToken": "refreshed-token"}})
    session = FakeSession(
        posts=[login_response(), refreshed],
        gets=[FakeResponse({"code": 401}, 401), FakeResponse(raw_telemetry_response())],
    )

    telemetry = InverterAdapter().read(BeveClient(beve_config, session=session))

    assert telemetry.inverter.rated_power_w == 6000
    assert any(call[1].endswith("/apis/login/refresh/access/token") for call in session.calls)
    assert session.headers["IOT-Token"] == "refreshed-token"


def test_login_failure_is_normalized(beve_config) -> None:
    session = FakeSession(posts=[FakeResponse({"code": 7, "message": "rejected"})])

    with pytest.raises(BeveAuthenticationError, match="login failed"):
        BeveClient(beve_config, session=session).login()


def test_timeout_is_normalized(beve_config) -> None:
    session = FakeSession(posts=[requests.Timeout("transport detail")])

    with pytest.raises(BeveTimeoutError, match="timed out"):
        BeveClient(beve_config, session=session).login()


def test_connection_error_is_normalized(beve_config) -> None:
    session = FakeSession(posts=[requests.ConnectionError("transport detail")])

    with pytest.raises(BeveConnectionError, match="unreachable"):
        BeveClient(beve_config, session=session).login()


def test_incomplete_telemetry_response_is_rejected(beve_config) -> None:
    session = FakeSession(posts=[login_response()], gets=[FakeResponse({"code": 0, "data": {}})])

    with pytest.raises(BeveIncompleteResponseError):
        BeveClient(beve_config, session=session).fetch_current_telemetry()


@pytest.mark.parametrize("payload", [[], "not-json-object", ValueError("invalid JSON")])
def test_malformed_response_is_rejected(beve_config, payload) -> None:
    session = FakeSession(posts=[FakeResponse(payload)])

    with pytest.raises(BeveMalformedResponseError):
        BeveClient(beve_config, session=session).login()


def test_verified_zero_values_are_retained() -> None:
    telemetry = InverterAdapter().read(MockBeveClient())

    assert telemetry.inverter.load_percentage == 0
    assert telemetry.battery.charging_current == 0
    assert telemetry.solar.pv1_voltage == 0
    assert telemetry.solar.pv1_power_w == 0
    assert telemetry.grid.voltage == 0
    assert telemetry.grid.frequency == 0
    assert telemetry.grid.power_w == 0


def test_missing_supported_fields_become_none() -> None:
    response = raw_telemetry_response()
    fields = response["data"]["fields"]
    fields.pop("pv2InputVoltage")
    fields.pop("batteryChargingCurrent")
    fields.pop("GridPower")

    telemetry = InverterAdapter().to_telemetry(response)

    assert telemetry.solar.pv2_voltage is None
    assert telemetry.battery.charging_current is None
    assert telemetry.grid.power_w is None


def test_timestamp_is_parsed_as_aware_datetime() -> None:
    telemetry = InverterAdapter().read(MockBeveClient())

    assert telemetry.timestamp.isoformat() == "2026-09-01T12:19:06+00:00"


def test_client_exposes_no_device_mutation_operations(beve_config) -> None:
    client = BeveClient(beve_config, session=FakeSession())
    prohibited = ("set", "write", "restart", "control", "priority", "update")

    public_methods = [name for name in dir(client) if not name.startswith("_")]
    assert not any(any(word in name.lower() for word in prohibited) for name in public_methods)
