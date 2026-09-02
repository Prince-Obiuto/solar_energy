"""Unit tests for the local TinyTuya breaker client foundation."""

from __future__ import annotations

import logging
import socket
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from apps.integrations.tuya.adapter import TuyaBreakerAdapter
from apps.integrations.tuya.client import (
    TuyaClient,
    TuyaCommunicationError,
    TuyaConfigurationError,
    TuyaDeviceConfig,
    TuyaMalformedResponseError,
    TuyaOfflineError,
    TuyaTimeoutError,
)
from apps.models import DeviceStatus


TEST_LOCAL_KEY = "test-local-key-not-a-real-secret"


class FakeTinyTuyaDevice:
    """Small TinyTuya device fake used without network or hardware."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.versions: list[float] = []
        self.closed = False

    def set_version(self, version: float) -> None:
        self.versions.append(version)

    def status(self, nowait: bool = False) -> Any:
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    def set_value(self, index: int, value: Any, nowait: bool = False) -> Any:
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    def close(self) -> None:
        self.closed = True


class FakeDeviceFactory:
    """Factory fake that supplies one result or exception per connection."""

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []
        self.devices: list[FakeTinyTuyaDevice] = []

    def __call__(self, device_id: str, **kwargs: Any) -> FakeTinyTuyaDevice:
        self.calls.append({"device_id": device_id, **kwargs})
        device = FakeTinyTuyaDevice(self.outcomes.pop(0))
        self.devices.append(device)
        return device


@pytest.fixture
def device_config() -> TuyaDeviceConfig:
    return TuyaDeviceConfig(
        device_id="test-device-id",
        friendly_name="Test area breaker",
        area="Test area",
        local_key=TEST_LOCAL_KEY,
        ip_address="192.0.2.10",
        protocol_version="3.5",
        enabled=True,
    )


def build_client(
    config: TuyaDeviceConfig,
    factory: Callable[..., FakeTinyTuyaDevice],
    *,
    max_attempts: int = 1,
) -> TuyaClient:
    return TuyaClient(
        config,
        device_factory=factory,
        max_attempts=max_attempts,
        socket_timeout_seconds=1,
    )


def test_successful_status_read_configures_protocol_and_closes_socket(device_config) -> None:
    response = {"dps": {"1": True, "6": 0}}
    factory = FakeDeviceFactory(response)

    result = build_client(device_config, factory).read_status()

    assert result == response
    assert factory.calls[0]["version"] == 3.5
    assert factory.calls[0]["connection_retry_limit"] == 0
    assert factory.devices[0].versions == [3.5]
    assert factory.devices[0].closed is True


def test_timeout_is_normalized(device_config) -> None:
    client = build_client(device_config, FakeDeviceFactory(socket.timeout("raw timeout")))

    with pytest.raises(TuyaTimeoutError, match="timed out"):
        client.read_status()


def test_offline_response_is_normalized(device_config) -> None:
    response = {"Error": "Device Unreachable", "Err": "905", "Payload": None}
    client = build_client(device_config, FakeDeviceFactory(response))

    with pytest.raises(TuyaOfflineError, match="offline or unreachable"):
        client.read_status()


@pytest.mark.parametrize("response", [None, [], {}, {"unexpected": True}, {"dps": []}])
def test_malformed_status_response_is_rejected(device_config, response) -> None:
    client = build_client(device_config, FakeDeviceFactory(response))

    with pytest.raises(TuyaMalformedResponseError):
        client.read_status()


def test_invalid_device_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TuyaDeviceConfig(
            device_id="",
            friendly_name="Breaker",
            area="Library",
            local_key="",
            ip_address="not-an-ip-address",
            protocol_version="version-three",
        )

    valid_config = TuyaDeviceConfig(
        device_id="test-device-id",
        friendly_name="Breaker",
        area="Library",
        local_key=TEST_LOCAL_KEY,
        ip_address="192.0.2.11",
    )
    with pytest.raises(TuyaConfigurationError):
        TuyaClient(valid_config, max_attempts=0)


def test_retry_reconnects_and_is_bounded(device_config) -> None:
    response = {"dps": {"1": False}}
    factory = FakeDeviceFactory(socket.timeout(), OSError(), response)
    client = build_client(device_config, factory, max_attempts=3)

    assert client.read_status() == response
    assert len(factory.calls) == 3
    assert all(device.closed for device in factory.devices)


def test_arbitrary_client_exception_is_normalized(device_config) -> None:
    client = build_client(device_config, FakeDeviceFactory(RuntimeError("vendor detail")))

    with pytest.raises(TuyaCommunicationError, match="status request failed") as captured:
        client.read_status()

    assert not isinstance(captured.value, RuntimeError)
    assert "vendor detail" not in str(captured.value)


def test_secrets_are_absent_from_errors_repr_and_logs(device_config, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    factory = FakeDeviceFactory(RuntimeError(TEST_LOCAL_KEY))

    with pytest.raises(TuyaCommunicationError) as captured:
        build_client(device_config, factory).read_status()

    exposed_text = " ".join(
        [str(captured.value), repr(device_config), caplog.text]
    )
    assert TEST_LOCAL_KEY not in exposed_text
    assert "**********" in repr(device_config)


def test_adapter_returns_domain_identity_without_exposing_configuration(device_config) -> None:
    client = build_client(device_config, FakeDeviceFactory({"dps": {"1": True}}))

    breaker = TuyaBreakerAdapter().read(client)

    assert breaker.device_id == device_config.device_id
    assert breaker.name == device_config.friendly_name
    assert breaker.status is DeviceStatus.ONLINE
    assert TEST_LOCAL_KEY not in breaker.model_dump_json()


def test_control_write_configures_protocol_and_normalizes_failures(device_config) -> None:
    factory = FakeDeviceFactory({"dps": {"1": True}})
    result = build_client(device_config, factory).write_datapoint(1, True)
    assert result == {"dps": {"1": True}}
    assert factory.devices[0].versions == [3.5]
    assert factory.devices[0].closed is True

    with pytest.raises(TuyaTimeoutError):
        build_client(device_config, FakeDeviceFactory(socket.timeout("secret detail"))).write_datapoint(1, True)
    with pytest.raises(TuyaCommunicationError, match="not acknowledged"):
        build_client(device_config, FakeDeviceFactory({"Error": "failure", "Err": "999"})).write_datapoint(1, True)


def test_control_write_rejects_non_allowlisted_datapoints_before_connection(device_config) -> None:
    factory = FakeDeviceFactory({"dps": {"22": 1}})
    with pytest.raises(TuyaConfigurationError, match="not permitted"):
        build_client(device_config, factory).write_datapoint(22, 1)
    assert factory.calls == []
