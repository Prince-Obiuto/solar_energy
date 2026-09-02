"""Regression coverage for real TMPH payloads and production composition."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from apps.core.config import Settings
from apps.core.runtime import (
    build_application_runtime, configure_application_runtime, provision_hardware_devices,
)
from apps.db.base import Base
from apps.integrations.tuya.adapter import TuyaBreakerAdapter
from apps.integrations.tuya.device_loader import load_breaker_registrations
from apps.jobs.energy_collector import SQLAlchemyTelemetryPersistence
from apps.models.persistence import AreaRecord, BreakerReadingRecord, DeviceRecord
from apps.services.breaker_service import BreakerService


REAL_TUYA_STATUS = {"dps": {
    "1": True, "9": 0, "17": 1, "18": 0, "19": 0, "20": 1950,
    "21": 1, "22": 15932, "23": 12829, "24": 3182, "25": 2731,
    "26": 0, "38": "memory", "40": "relay", "41": False, "42": "",
}}


class FakeTuyaClient:
    def __init__(self, config):
        self.config = config

    def read_status(self):
        return REAL_TUYA_STATUS


class FakeBeveClient:
    def __init__(self, config):
        self.config = config


def device_entries(count=3):
    return [
        {"name": f"Area {index}", "id": f"device-{index}", "key": f"fake-key-{index}",
         "ip": f"192.0.2.{index + 1}", "version": 3.5, "model": "TMPH",
         "product_id": "ruqchkg5f9loztw2"}
        for index in range(count)
    ]


def write_devices(tmp_path, entries):
    path = tmp_path / "devices.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_real_tmph_payload_normalization_and_diagnostic_exclusion():
    status = TuyaBreakerAdapter().from_raw(REAL_TUYA_STATUS)
    assert status.switch_on is True
    assert status.countdown_seconds == 0
    assert status.energy.accumulated_energy == 0.001
    assert status.energy.total_kwh is None
    assert status.electrical.current_amperes == 0.0
    assert status.electrical.active_power_watts == 0.0
    assert status.electrical.voltage_volts == 195.0
    assert status.configuration == {
        "relay_restore_mode": "memory", "indicator_mode": "relay", "child_lock": False,
    }
    assert status.raw_datapoints["21"] == 1
    payload = status.model_dump(mode="json")
    assert "raw_datapoints" not in payload
    assert "22" not in json.dumps(payload)


def test_relay_off_is_online_when_status_read_succeeds(tmp_path):
    payload = {"dps": {**REAL_TUYA_STATUS["dps"], "1": False, "20": 2300}}
    registration = load_breaker_registrations(
        write_devices(tmp_path, device_entries(1)),
        client_factory=lambda config: type("Client", (), {"config": config, "read_status": lambda self: payload})(),
    )[0]
    breaker = BreakerService([registration]).get_breaker("device-0")
    assert breaker.online is True
    assert breaker.status.switch_on is False
    assert breaker.status.electrical.voltage_volts == 230.0


def test_loader_supports_multiple_devices_and_skips_bad_entries(tmp_path, caplog):
    entries = device_entries() + [
        {"name": "Unsupported", "id": "other", "key": "not-a-real-key", "ip": "192.0.2.50", "model": "OTHER"},
        {"name": "Incomplete", "id": "bad", "key": "secret-that-must-not-leak", "model": "TMPH"},
    ]
    registrations = load_breaker_registrations(
        write_devices(tmp_path, {"devices": entries}), client_factory=FakeTuyaClient
    )
    assert [item.client.config.device_id for item in registrations] == ["device-0", "device-1", "device-2"]
    assert [item.client.config.friendly_name for item in registrations] == ["Area 0", "Area 1", "Area 2"]
    assert str(registrations[0].client.config.ip_address) == "192.0.2.1"
    assert registrations[0].client.config.protocol_version == "3.5"
    assert isinstance(registrations[0].client.config.local_key, SecretStr)
    serialized = str(registrations[0].client.config)
    assert "fake-key-0" not in serialized
    assert "secret-that-must-not-leak" not in caplog.text


def test_loader_file_not_found_is_clear(tmp_path):
    assert load_breaker_registrations(tmp_path / "missing.json") == []


@pytest.mark.parametrize("count", [1, 3, 5])
def test_loader_is_variable_length(tmp_path, count):
    registrations = load_breaker_registrations(
        write_devices(tmp_path, device_entries(count)), client_factory=FakeTuyaClient
    )
    assert len(registrations) == count


def test_runtime_composes_beve_three_breakers_and_collector(tmp_path):
    config = Settings(
        _env_file=None, tuya_device_file=write_devices(tmp_path, device_entries()),
        beve_username="fake-user", beve_password="fake-password", beve_app_id="fake-app",
        beve_app_secret_encrypted="fake-secret", beve_station_id="station", beve_device_id="inverter",
    )
    try:
        runtime = build_application_runtime(
            config, beve_client_factory=FakeBeveClient,
            tuya_client_factory=FakeTuyaClient, provision=False,
        )
        assert runtime.inverter_service.configured is True
        assert runtime.breaker_service.registered_breaker_ids == ("device-0", "device-1", "device-2")
        assert runtime.collector is not None
        assert runtime.inverter_device_reference == "inverter"
    finally:
        configure_application_runtime(None)


def test_provisioning_is_idempotent_preserves_custom_metadata_and_enables_persistence(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    registrations = load_breaker_registrations(
        write_devices(tmp_path, device_entries()), client_factory=FakeTuyaClient
    )
    provision_hardware_devices(sessions, registrations, inverter_reference="inverter")
    with sessions() as session:
        customized = session.scalar(select(DeviceRecord).where(DeviceRecord.external_reference == "device-0"))
        customized.friendly_name = "Customized name"
        session.commit()
    provision_hardware_devices(sessions, registrations, inverter_reference="inverter")
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(DeviceRecord)) == 4
        assert session.scalar(select(func.count()).select_from(AreaRecord)) == 4
        assert session.scalar(select(DeviceRecord).where(DeviceRecord.external_reference == "device-0")).friendly_name == "Customized name"
    breaker = BreakerService(registrations).get_breaker("device-0")
    SQLAlchemyTelemetryPersistence(sessions).persist_breaker("device-0", breaker, datetime.now(UTC))
    with sessions() as session:
        reading = session.scalar(select(BreakerReadingRecord))
        assert reading.accumulated_energy == 0.001
        assert reading.switch_state is True
