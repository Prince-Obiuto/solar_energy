"""Hardware-free safety and ownership tests for smart load management."""

from __future__ import annotations

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.core.config import Settings
from apps.db.base import Base
from apps.integrations.tuya.client import TuyaDeviceConfig
from apps.integrations.inverter import BeveTimeoutError, VERIFIED_BEVE_RESPONSE
from apps.jobs.energy_collector import CollectorConfig, EnergyCollector, NullEventPublisher
from apps.models import DeviceCapability
from apps.models.persistence import ControlEventRecord, DeviceRecord, LoadSheddingStateRecord
from apps.services.breaker_service import BreakerRegistration, BreakerService
from apps.services.control_service import BreakerControlService
from apps.services.load_shedding_service import LoadSheddingService
from apps.services.inverter_service import InverterService


class RelayClient:
    def __init__(self, device_id: str, area: str, *, relay_on: bool = True, mismatch: bool = False):
        self.config = TuyaDeviceConfig(
            device_id=device_id, friendly_name=f"{area} breaker", area=area,
            local_key=SecretStr("test-only-key"), ip_address="192.0.2.40", protocol_version="3.5",
        )
        self.relay_on = relay_on
        self.mismatch = mismatch
        self.writes: list[tuple[int, object]] = []

    def read_status(self):
        return {"dps": {"1": self.relay_on, "9": 0, "17": 0, "18": 0, "19": 0,
                         "20": 2300, "38": "memory", "40": "relay", "41": False}}

    def write_datapoint(self, datapoint, value):
        self.writes.append((datapoint, value))
        if not self.mismatch:
            self.relay_on = value
        return {"dps": {str(datapoint): value}}


def build_system(*, enabled=True, lecturer_on=True, admin_on=True, mismatch=False):
    engine = create_engine("sqlite+pysqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    lecturer = RelayClient("lecturer-test", "Lecturer Offices", relay_on=lecturer_on, mismatch=mismatch)
    admin = RelayClient("admin-test", "Admin Office", relay_on=admin_on)
    with factory.begin() as session:
        session.add_all([
            DeviceRecord(external_reference="lecturer-test", friendly_name="Lecturer breaker", device_type="breaker"),
            DeviceRecord(external_reference="admin-test", friendly_name="Admin breaker", device_type="breaker"),
        ])
    capability = DeviceCapability(switching=True)
    breakers = BreakerService([
        BreakerRegistration(lecturer, capability), BreakerRegistration(admin, capability),
    ])
    config = Settings(
        _env_file=None, load_shedding_enabled=enabled,
        load_shedding_lecturer_breaker_id="lecturer-test",
        load_shedding_admin_breaker_id="admin-test",
        load_shedding_confirm_readings=2,
    )
    control_factory = lambda session, service: BreakerControlService(
        session, service, verify_delay_seconds=0
    )
    return LoadSheddingService(config, breakers, factory, control_factory=control_factory), factory, lecturer, admin


def test_normal_soc_does_nothing_and_zero_is_valid() -> None:
    service, _, lecturer, admin = build_system()
    assert service.evaluate(50) == []
    service.evaluate(0)
    events = service.evaluate(0)
    assert lecturer.writes == [(1, False)] and admin.writes == [(1, False)]
    assert {event[0] for event in events} == {"load_management.shed"}


def test_two_readings_shed_lecturer_without_spam() -> None:
    service, _, lecturer, admin = build_system()
    assert service.evaluate(20) == []
    events = service.evaluate(19)
    assert lecturer.writes == [(1, False)] and admin.writes == []
    assert events[0][0] == "load_management.shed"
    service.evaluate(18)
    service.evaluate(18)
    assert lecturer.writes == [(1, False)]


def test_admin_boundaries_and_hysteresis() -> None:
    service, _, _, admin = build_system()
    service.evaluate(16)
    service.evaluate(16)
    assert admin.writes == []
    service.evaluate(15)
    service.evaluate(14)
    assert admin.writes == [(1, False)]
    service.evaluate(16)
    service.evaluate(16)
    assert admin.relay_on is False
    service.evaluate(17)
    service.evaluate(18)
    assert admin.writes == [(1, False), (1, True)]


def test_lecturer_restore_requires_confirmed_22_and_preserves_21() -> None:
    service, _, lecturer, _ = build_system()
    service.evaluate(20); service.evaluate(19)
    service.evaluate(21); service.evaluate(21)
    assert lecturer.relay_on is False
    service.evaluate(22)
    assert lecturer.relay_on is False
    service.evaluate(23)
    assert lecturer.relay_on is True


def test_missing_soc_invalidates_confirmation() -> None:
    service, _, lecturer, _ = build_system()
    service.evaluate(20)
    service.mark_unavailable()
    service.evaluate(19)
    assert lecturer.writes == []
    service.evaluate(19)
    assert lecturer.writes == [(1, False)]


def test_manual_off_is_not_owned_or_restored() -> None:
    service, factory, lecturer, _ = build_system(lecturer_on=False)
    service.evaluate(20); service.evaluate(19)
    service.evaluate(22); service.evaluate(23)
    assert lecturer.writes == [] and lecturer.relay_on is False
    with factory() as session:
        state = session.scalar(select(LoadSheddingStateRecord).where(LoadSheddingStateRecord.policy_name == "lecturer_offices"))
        assert state is not None and state.automatically_shed is False


def test_ownership_survives_service_reconstruction() -> None:
    service, factory, lecturer, admin = build_system()
    service.evaluate(20); service.evaluate(19)
    rebuilt = LoadSheddingService(
        service_config(), service.breakers, factory,
        control_factory=lambda session, breakers: BreakerControlService(session, breakers, verify_delay_seconds=0),
    )
    rebuilt.evaluate(22); rebuilt.evaluate(23)
    assert lecturer.writes == [(1, False), (1, True)] and admin.writes == []


def service_config(**changes):
    values = dict(
        _env_file=None, load_shedding_enabled=True, load_shedding_confirm_readings=2,
        load_shedding_lecturer_breaker_id="lecturer-test",
        load_shedding_admin_breaker_id="admin-test",
    )
    values.update(changes)
    return Settings(**values)


def test_readback_mismatch_never_claims_ownership_and_is_audited() -> None:
    service, factory, lecturer, _ = build_system(mismatch=True)
    service.evaluate(20)
    events = service.evaluate(19)
    assert events[0][0] == "load_management.action_failed"
    assert service.get_status().policies[0].automatically_shed is False
    with factory() as session:
        event = session.scalar(select(ControlEventRecord).where(ControlEventRecord.requested_by == "battery_load_shedding"))
        assert event.status == "failed" and event.user_id is None and event.role == "system"
        assert event.details["soc"] == 19 and "local_key" not in str(event.details)


def test_disabled_feature_and_missing_breaker_are_safe() -> None:
    service, _, lecturer, admin = build_system(enabled=False)
    service.evaluate(0); service.evaluate(0)
    assert lecturer.writes == admin.writes == []
    assert service.get_status().current_stage.value == "disabled"
    missing = LoadSheddingService(
        service_config(load_shedding_lecturer_breaker_id=None, load_shedding_admin_breaker_id=None),
        service.breakers, service.session_factory,
    )
    assert missing.evaluate(0) == []
    assert all(not item.enabled for item in missing.get_status().policies)


def test_manual_on_during_low_soc_is_shed_again_after_confirmation() -> None:
    service, _, lecturer, _ = build_system()
    service.evaluate(20); service.evaluate(19)
    lecturer.relay_on = True  # authenticated administrator action outside this service
    service.evaluate(19)
    service.evaluate(19)
    assert lecturer.writes == [(1, False), (1, False)]


def test_one_policy_failure_does_not_prevent_other_policy() -> None:
    service, _, lecturer, admin = build_system(mismatch=True)
    service.evaluate(0)
    events = service.evaluate(0)
    assert lecturer.writes == [(1, False)]
    assert admin.writes == [(1, False)]
    assert {event[0] for event in events} == {
        "load_management.action_failed", "load_management.shed"
    }


def test_configuration_rejects_invalid_thresholds() -> None:
    try:
        service_config(load_shedding_lecturer_shed_soc=22, load_shedding_lecturer_restore_soc=22)
    except ValueError as exc:
        assert "threshold" in str(exc).lower()
    else:
        raise AssertionError("Invalid hysteresis was accepted")


class SequenceInverter:
    def __init__(self):
        self.outcomes = [VERIFIED_BEVE_RESPONSE, BeveTimeoutError("timeout")]

    def fetch_current_telemetry(self):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class DecisionSpy:
    def __init__(self):
        self.values = []
        self.unavailable = 0

    def evaluate(self, soc):
        self.values.append(soc)
        return []

    def mark_unavailable(self):
        self.unavailable += 1

    def get_status(self):
        return type("Status", (), {"model_dump": lambda self, mode: {"current_soc": 100}})()


@pytest.mark.asyncio
async def test_collector_evaluates_only_successful_current_beve_reads() -> None:
    spy = DecisionSpy()
    collector = EnergyCollector(
        InverterService(SequenceInverter()), BreakerService([]),
        inverter_device_reference="inverter-test", load_shedding_service=spy,
        publisher=NullEventPublisher(),
        config=CollectorConfig(
            beve_poll_interval_seconds=30, tuya_poll_interval_seconds=10,
            telemetry_persist_interval_seconds=60, device_stale_after_seconds=90,
            retry_attempts=1, retry_delay_seconds=0,
        ),
    )
    async def run_inline(operation, *args):
        return operation(*args)
    collector._run_sync = run_inline
    assert await collector.collect_inverter_once() is True
    assert spy.values == [100]
    assert await collector.collect_inverter_once() is False
    assert spy.values == [100] and spy.unavailable == 1
