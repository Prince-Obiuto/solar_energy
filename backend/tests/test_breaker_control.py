"""Safe Tuya breaker control, verification, RBAC, and audit tests."""

import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.core.security import create_access_token, hash_password
from apps.db.base import Base
from apps.db.session import get_db
from apps.integrations.tuya.adapter import TuyaBreakerAdapter
from apps.integrations.tuya.client import (
    TuyaCommunicationError, TuyaConfigurationError, TuyaDeviceConfig,
    TuyaOfflineError, TuyaTimeoutError,
)
from apps.integrations.tuya.constants import CALIBRATION_DATAPOINTS, CONTROL_DATAPOINTS
from apps.main import app
from apps.models import DeviceCapability, UserRole
from apps.models.persistence import AreaRecord, ControlEventRecord, DeviceRecord, UserRecord
from apps.services.breaker_service import BreakerRegistration, BreakerService, get_breaker_service


class FakeControlClient:
    def __init__(self) -> None:
        self.config = TuyaDeviceConfig(
            device_id="breaker-control-test", friendly_name="Library breaker", area="Library",
            local_key=SecretStr("test-only-key"), ip_address="192.0.2.10", protocol_version="3.5",
        )
        self.read_values = [False, True]
        self.read_error = None
        self.write_error = None
        self.writes = []

    def read_status(self):
        if self.read_error:
            raise self.read_error
        value = self.read_values.pop(0)
        return {"dps": {"1": value, "9": value, "38": value, "40": value, "41": value}}

    def write_datapoint(self, datapoint, value):
        if self.write_error:
            raise self.write_error
        self.writes.append((datapoint, value))
        return {"dps": {str(datapoint): value}}


@pytest.fixture
def control_context():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    users = {}
    with factory() as session:
        area = AreaRecord(name="Library")
        device = DeviceRecord(
            external_reference="breaker-control-test", friendly_name="Library breaker",
            device_type="breaker", area=area,
        )
        session.add_all([area, device])
        for role in UserRole:
            user = UserRecord(
                id=uuid.uuid4(), email=f"{role.value}.control@example.test",
                password_hash=hash_password("correct horse battery staple"),
                role=role.value, is_active=True,
            )
            session.add(user)
            users[role] = user
        session.commit()

    fake = FakeControlClient()
    service = BreakerService([BreakerRegistration(
        client=fake,
        capabilities=DeviceCapability(switching=True, countdown=True, remote_configuration=True),
    )])

    def override_db():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_breaker_service] = lambda: service
    try:
        with TestClient(app) as client:
            yield client, factory, fake, users
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def headers(user):
    token, _ = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def switch_payload(request_id=None, state=True):
    return {"request_id": str(request_id or uuid.uuid4()), "state": state, "confirmed": True, "reason": "Authorized maintenance operation"}


@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.STAFF])
def test_non_admin_roles_are_denied(control_context, role) -> None:
    client, _, fake, users = control_context
    response = client.post("/api/v1/breakers/breaker-control-test/switch", headers=headers(users[role]), json=switch_payload())
    assert response.status_code == 403
    assert fake.writes == []


def test_admin_success_requires_readback_and_creates_audit(control_context) -> None:
    client, factory, fake, users = control_context
    request_id = uuid.uuid4()
    response = client.post("/api/v1/breakers/breaker-control-test/switch", headers=headers(users[UserRole.ADMIN]), json=switch_payload(request_id))
    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["data"]["verified_value"] is True
    assert fake.writes == [(1, True)]
    with factory() as session:
        event = session.scalar(select(ControlEventRecord).where(ControlEventRecord.request_id == str(request_id)))
        assert event.user_id == users[UserRole.ADMIN].id
        assert event.role == "admin" and event.reason
        assert event.previous_value is False and event.requested_value is True
        assert event.hardware_acknowledgement is True and event.verified_value is True
        assert event.client_ip and event.completed_at and event.status == "succeeded"


@pytest.mark.parametrize(
    ("path", "payload_field", "previous", "requested", "datapoint"),
    [
        ("countdown", "seconds", 0, 60, 9),
        ("relay-restore-mode", "mode", "off", "memory", 38),
        ("indicator-mode", "mode", "relay", "none", 40),
        ("child-lock", "enabled", False, True, 41),
    ],
)
def test_verified_configuration_commands_use_only_documented_datapoints(
    control_context, path, payload_field, previous, requested, datapoint
) -> None:
    client, _, fake, users = control_context
    fake.read_values = [previous, requested]
    payload = {"request_id": str(uuid.uuid4()), payload_field: requested, "reason": "Approved configuration"}
    response = client.put(
        f"/api/v1/breakers/breaker-control-test/{path}",
        headers=headers(users[UserRole.ADMIN]), json=payload,
    )
    assert response.json()["status"] == "succeeded"
    assert fake.writes == [(datapoint, requested)]


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("countdown", {"request_id": str(uuid.uuid4()), "seconds": 86401}),
        ("relay-restore-mode", {"request_id": str(uuid.uuid4()), "mode": "invalid"}),
        ("indicator-mode", {"request_id": str(uuid.uuid4()), "mode": "invalid"}),
    ],
)
def test_invalid_values_are_rejected_before_hardware(control_context, path, payload) -> None:
    client, _, fake, users = control_context
    response = client.put(f"/api/v1/breakers/breaker-control-test/{path}", headers=headers(users[UserRole.ADMIN]), json=payload)
    assert response.status_code == 422
    assert fake.writes == []


@pytest.mark.parametrize(
    ("error", "expected"),
    [(TuyaOfflineError("offline"), "failed"), (TuyaTimeoutError("timeout"), "timed_out")],
)
def test_offline_and_timeout_are_audited(control_context, error, expected) -> None:
    client, factory, fake, users = control_context
    fake.read_error = error
    request_id = uuid.uuid4()
    response = client.post("/api/v1/breakers/breaker-control-test/switch", headers=headers(users[UserRole.ADMIN]), json=switch_payload(request_id))
    assert response.json()["status"] == expected
    with factory() as session:
        assert session.scalar(select(ControlEventRecord).where(ControlEventRecord.request_id == str(request_id))).status == expected


def test_failed_command_is_not_marked_successful(control_context) -> None:
    client, _, fake, users = control_context
    fake.write_error = TuyaCommunicationError("vendor details must not escape")
    response = client.post("/api/v1/breakers/breaker-control-test/switch", headers=headers(users[UserRole.ADMIN]), json=switch_payload())
    assert response.json()["status"] == "failed"
    assert response.json()["data"]["hardware_acknowledgement"] is False
    assert "vendor details" not in response.text


def test_readback_mismatch_fails(control_context) -> None:
    client, _, fake, users = control_context
    fake.read_values = [False, False]
    response = client.post("/api/v1/breakers/breaker-control-test/switch", headers=headers(users[UserRole.ADMIN]), json=switch_payload())
    assert response.json()["status"] == "failed"
    assert response.json()["data"]["verified_value"] is False


def test_duplicate_request_returns_original_without_second_write(control_context) -> None:
    client, _, fake, users = control_context
    payload = switch_payload()
    first = client.post("/api/v1/breakers/breaker-control-test/switch", headers=headers(users[UserRole.ADMIN]), json=payload)
    second = client.post("/api/v1/breakers/breaker-control-test/switch", headers=headers(users[UserRole.ADMIN]), json=payload)
    assert first.json()["status"] == second.json()["status"] == "succeeded"
    assert second.json()["data"]["duplicate"] is True
    assert fake.writes == [(1, True)]


def test_calibration_and_unknown_datapoints_have_no_write_surface() -> None:
    assert CALIBRATION_DATAPOINTS.isdisjoint(CONTROL_DATAPOINTS)
    adapter_methods = set(dir(TuyaBreakerAdapter))
    assert not any("calibr" in name or "datapoint" in name for name in adapter_methods)
    with pytest.raises(TuyaConfigurationError):
        FakeControlClientWithRealGuard().write_datapoint(22, 1)


class FakeControlClientWithRealGuard:
    """Invoke the real allowlist guard without constructing LAN hardware."""

    write_datapoint = __import__("apps.integrations.tuya.client", fromlist=["TuyaClient"]).TuyaClient.write_datapoint
    config = type("Config", (), {"enabled": True})()
