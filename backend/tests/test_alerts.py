"""Alert lifecycle, monitoring rules, thresholds, RBAC, and realtime tests."""

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.core.security import create_access_token, hash_password
from apps.db.base import Base
from apps.db.session import get_db
from apps.jobs.energy_collector import CollectorSnapshot, DeviceCollectionState
from apps.jobs.health_monitor import ElectricalThresholds, HealthMonitoringEngine
from apps.main import app
from apps.models import UserRole
from apps.models.persistence import AlertRecord, AreaRecord, DeviceRecord, UserRecord
from apps.realtime.manager import ConnectionManager, TelemetryEventPublisher
from apps.schemas.alert import AlertSeverity
from apps.services.alert_service import AlertService


NOW = datetime(2026, 9, 1, 15, 0, tzinfo=UTC)


@pytest.fixture
def alert_context():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    users = {}
    with factory() as session:
        area = AreaRecord(name="Library")
        device = DeviceRecord(external_reference="breaker-alert", friendly_name="Library breaker", device_type="breaker", area=area)
        inverter = DeviceRecord(external_reference="inverter-alert", friendly_name="Inverter", device_type="inverter")
        session.add_all([area, device, inverter])
        for role in UserRole:
            user = UserRecord(
                id=uuid.uuid4(), email=f"{role.value}.alerts@example.test",
                password_hash=hash_password("correct horse battery staple"), role=role.value, is_active=True,
            )
            session.add(user)
            users[role] = user
        session.commit()

    def override_db():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app, base_url="https://testserver") as client:
            yield client, factory, users
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def headers(user):
    token, _ = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def test_active_alert_is_deduplicated_updated_and_resolved(alert_context) -> None:
    _, factory, _ = alert_context
    clock = [NOW]
    with factory() as session:
        service = AlertService(session, clock=lambda: clock[0])
        first, created = service.raise_alert(
            dedup_key="breaker-alert:breaker.offline", category="breaker.offline",
            severity=AlertSeverity.WARNING, message="Breaker is offline", device_reference="breaker-alert",
        )
        clock[0] += timedelta(minutes=1)
        repeated, repeated_created = service.raise_alert(
            dedup_key="breaker-alert:breaker.offline", category="breaker.offline",
            severity=AlertSeverity.WARNING, message="Breaker remains offline", device_reference="breaker-alert",
        )
        resolved = service.resolve("breaker-alert:breaker.offline")
        session.commit()
        count = len(session.scalars(select(AlertRecord)).all())

    assert created is True and repeated_created is False
    assert first.id == repeated.id and count == 1
    assert repeated.last_seen == NOW + timedelta(minutes=1)
    assert resolved.resolved_at == NOW + timedelta(minutes=1) and resolved.active is False


def test_monitor_maps_supported_failures_without_tmp_fault_bitmap(alert_context) -> None:
    _, factory, _ = alert_context
    with factory() as session:
        engine = HealthMonitoringEngine(AlertService(session, clock=lambda: NOW), thresholds=ElectricalThresholds())
        engine.process_event("breaker.poll_failed", {"device_id": "breaker-alert", "failure_type": "malformed_response", "dps": {"21": 7}})
        engine.process_event("inverter.poll_failed", {"device_id": "inverter-alert", "failure_type": "authentication_failure"})
        engine.process_event("system.collector_failure", {})
        session.commit()
        alerts = session.scalars(select(AlertRecord).order_by(AlertRecord.category)).all()

    assert {alert.category for alert in alerts} == {
        "breaker.malformed_response", "inverter.authentication_failure", "system.collector_failure"
    }
    assert all("dps" not in (alert.alert_metadata or {}) for alert in alerts)


def test_thresholds_are_disabled_by_default_and_valid_beve_states_are_not_faults(alert_context) -> None:
    _, factory, _ = alert_context
    payload = {
        "device_id": "inverter-alert",
        "inverter": {"status": "Battery Mode", "output_voltage": 0, "output_power_w": 0},
        "battery": {"status": "No Charging"},
        "solar": {"connected": "PV Not Connected", "total_power_w": 0},
        "grid": {"voltage": 0, "frequency": 0, "power_w": 0},
    }
    with factory() as session:
        changes = HealthMonitoringEngine(
            AlertService(session, clock=lambda: NOW), thresholds=ElectricalThresholds()
        ).process_event("inverter.telemetry", payload)
        session.commit()
        assert changes == []
        assert session.scalar(select(AlertRecord)) is None


def test_explicit_electrical_thresholds_raise_and_resolve(alert_context) -> None:
    _, factory, _ = alert_context
    thresholds = ElectricalThresholds(low_voltage_v=200, high_voltage_v=250, high_current_a=10, high_power_w=2000)
    low = {"id": "breaker-alert", "status": {"electrical": {"voltage_volts": 195, "current_amperes": 0, "active_power_watts": 0}}}
    normal = {"id": "breaker-alert", "status": {"electrical": {"voltage_volts": 230, "current_amperes": 1, "active_power_watts": 100}}}
    with factory() as session:
        engine = HealthMonitoringEngine(AlertService(session, clock=lambda: NOW), thresholds=thresholds)
        created = engine.process_event("breaker.telemetry", low)
        resolved = engine.process_event("breaker.telemetry", normal)
        session.commit()
        alert = session.scalar(select(AlertRecord).where(AlertRecord.category == "electrical.low_voltage"))
    assert any(change == "alert.created" for change, _ in created)
    assert any(change == "alert.resolved" for change, _ in resolved)
    assert alert.resolved_at == NOW


def test_stale_snapshot_alert_deduplicates_and_recovers(alert_context) -> None:
    _, factory, _ = alert_context
    stale = CollectorSnapshot(
        devices={"breaker-alert": DeviceCollectionState(device_id="breaker-alert", online=True, stale=True, last_seen=NOW - timedelta(minutes=5))},
        breakers={},
    )
    # Include the breaker identity so the monitor uses the breaker category.
    from apps.models import BreakerDevice, BreakerStatus
    stale.breakers["breaker-alert"] = BreakerDevice(
        id="breaker-alert", friendly_name="Breaker", area="Library", online=True,
        status=BreakerStatus(device_id="breaker-alert"),
    )
    with factory() as session:
        engine = HealthMonitoringEngine(AlertService(session, clock=lambda: NOW), thresholds=ElectricalThresholds())
        engine.evaluate_snapshot(stale)
        engine.evaluate_snapshot(stale)
        stale.devices["breaker-alert"].stale = False
        changes = engine.evaluate_snapshot(stale)
        session.commit()
        records = session.scalars(select(AlertRecord).where(AlertRecord.category == "breaker.stale")).all()
    assert len(records) == 1 and records[0].resolved_at == NOW
    assert changes[0][0] == "alert.resolved"


def test_alert_endpoints_rbac_retrieve_and_acknowledge(alert_context) -> None:
    client, factory, users = alert_context
    with factory() as session:
        alert, _ = AlertService(session, clock=lambda: NOW).raise_alert(
            dedup_key="breaker-alert:breaker.offline", category="breaker.offline",
            severity=AlertSeverity.WARNING, message="Breaker is offline", device_reference="breaker-alert",
        )
        session.commit()
        alert_id = alert.id
    assert client.get("/api/v1/alerts", headers=headers(users[UserRole.STUDENT])).status_code == 403
    listing = client.get("/api/v1/alerts", headers=headers(users[UserRole.STAFF]))
    detail = client.get(f"/api/v1/alerts/{alert_id}", headers=headers(users[UserRole.STAFF]))
    acknowledged = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers(users[UserRole.STAFF]))
    assert listing.status_code == detail.status_code == acknowledged.status_code == 200
    assert listing.json()["items"][0]["area"] == "Library"
    assert acknowledged.json()["acknowledged_by"] == str(users[UserRole.STAFF].id)


def test_realtime_publisher_supports_all_alert_lifecycle_messages() -> None:
    publisher = TelemetryEventPublisher(ConnectionManager())
    for event_type in ("alert.created", "alert.updated", "alert.resolved", "alert.acknowledged"):
        messages = publisher.messages_for_event(event_type, {"device_id": "breaker-alert", "data": {"category": "breaker.offline"}})
        assert len(messages) == 1 and messages[0].type == event_type
