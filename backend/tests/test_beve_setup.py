"""BEVE first-run verification, persistence, authorization, and API tests."""

from __future__ import annotations

from collections import deque

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.setup import (
    get_beve_setup_client_factory,
    get_runtime_configuration_service,
    setup_limiter,
)
from apps.core.config import Settings
from apps.db.base import Base
from apps.db.session import get_db
from apps.integrations.inverter import (
    BeveAuthenticationError,
    BeveConnectionError,
    BeveDeviceNotFoundError,
    BeveTimeoutError,
    VERIFIED_BEVE_RESPONSE,
)
from apps.main import app
from apps.models.persistence import (
    InstallationStateRecord,
    RuntimeConfigurationRecord,
    SystemEventRecord,
)
from apps.schemas.setup import BeveSetupRequest
from apps.security.runtime_secrets import initialize_runtime_master_key
from apps.services.beve_setup_service import BeveSetupService
from apps.services.runtime_configuration_service import (
    ConfigurationSource,
    RuntimeConfigurationService,
)
from apps.services.setup_service import SetupService


class FakeBeveReader:
    def __init__(self, config, outcome) -> None:
        self.config = config
        self.outcome = outcome
        self.closed = False

    def fetch_current_telemetry(self):
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    def close(self) -> None:
        self.closed = True


class FakeBeveFactory:
    def __init__(self, *outcomes) -> None:
        self.outcomes = deque(outcomes)
        self.configs = []
        self.clients = []

    def __call__(self, config):
        self.configs.append(config)
        outcome = self.outcomes.popleft() if len(self.outcomes) > 1 else self.outcomes[0]
        client = FakeBeveReader(config, outcome)
        self.clients.append(client)
        return client


@pytest.fixture(autouse=True)
def isolate_beve_setup_rate_limits():
    for operation in ("beve-test", "beve-configure"):
        setup_limiter.reset(f"{operation}:testclient")
    yield
    for operation in ("beve-test", "beve-configure"):
        setup_limiter.reset(f"{operation}:testclient")


@pytest.fixture
def beve_setup_context(tmp_path):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    key_file = tmp_path / "master.key"
    initialize_runtime_master_key(key_file)
    environment = Settings(
        _env_file=None,
        app_env="test",
        runtime_master_key_file=key_file,
        beve_username=None,
        beve_password=None,
        beve_station_id=None,
        beve_device_id=None,
        tuya_device_file=tmp_path / "no-devices.json",
    )
    try:
        yield factory, key_file, environment
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def authorized_setup(factory) -> str:
    with factory() as session:
        service = SetupService(session)
        code = service.initialize()
        service.get_state().admin_configured = True
        session.commit()
        return code


def setup_payload(code: str, **updates) -> BeveSetupRequest:
    values = {
        "setup_code": code,
        "username": "candidate-user",
        "password": "candidate-password",
        "station_id": "candidate-station",
        "device_id": "candidate-device",
    }
    values.update(updates)
    return BeveSetupRequest(**values)


def configured_service(session, key_file, environment, client_factory) -> BeveSetupService:
    runtime = RuntimeConfigurationService(
        session,
        environment=environment,
        master_key_file=str(key_file),
    )
    return BeveSetupService(
        session,
        runtime,
        client_factory=client_factory,
        environment=environment,
    )


def test_valid_zero_and_pv_disconnected_telemetry_is_success(beve_setup_context) -> None:
    factory, key_file, environment = beve_setup_context
    code = authorized_setup(factory)
    fake = FakeBeveFactory(VERIFIED_BEVE_RESPONSE)
    with factory() as session:
        result = configured_service(session, key_file, environment, fake).test_configuration(
            setup_payload(code)
        )
        session.commit()

        assert result.success is True and result.device_verified is True
        assert result.summary.output_power_w == 12.0
        assert result.summary.pv_status == "PV Not Connected"
        assert result.summary.battery_soc == 100
        assert result.summary.source_timestamp.isoformat() == "2026-09-01T12:19:06+00:00"
        assert fake.clients[0].closed is True


@pytest.mark.parametrize(
    ("outcome", "category"),
    [
        (BeveAuthenticationError("unsafe vendor detail"), "authentication_failed"),
        (BeveDeviceNotFoundError("unsafe vendor detail"), "device_not_found"),
        (BeveTimeoutError("unsafe vendor detail"), "timeout"),
        (BeveConnectionError("unsafe vendor detail"), "network_error"),
        ({"code": 0, "data": {"time": None, "fields": {}}}, "malformed_response"),
    ],
)
def test_failed_test_does_not_persist_or_advance(
    beve_setup_context, outcome, category
) -> None:
    factory, key_file, environment = beve_setup_context
    code = authorized_setup(factory)
    with factory() as session:
        result = configured_service(
            session, key_file, environment, FakeBeveFactory(outcome)
        ).test_configuration(setup_payload(code))
        session.commit()

        assert result.success is False and result.category == category
        assert "unsafe" not in result.message
        assert session.scalar(select(RuntimeConfigurationRecord)) is None
        assert session.get(InstallationStateRecord, 1).beve_configured is False


def test_verified_configuration_is_encrypted_and_advances_to_tuya(
    beve_setup_context,
) -> None:
    factory, key_file, environment = beve_setup_context
    code = authorized_setup(factory)
    fake = FakeBeveFactory(VERIFIED_BEVE_RESPONSE, VERIFIED_BEVE_RESPONSE)
    with factory() as session:
        runtime = RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        )
        result = BeveSetupService(
            session, runtime, client_factory=fake, environment=environment
        ).configure(setup_payload(code))
        session.commit()

        assert result.verification.success is True
        assert result.setup.beve_configured is True
        assert result.setup.next_step == "tuya"
        assert result.runtime_activation == "restart_required"
        records = {
            record.key: record
            for record in session.scalars(
                select(RuntimeConfigurationRecord).where(
                    RuntimeConfigurationRecord.namespace == "beve"
                )
            )
        }
        assert set(records) == {"username", "password", "station_id", "device_id"}
        assert records["username"].is_secret is True
        assert records["password"].is_secret is True
        assert "candidate-user" not in records["username"].value
        assert "candidate-password" not in records["password"].value
        resolved = runtime.get_beve_configuration()
        assert resolved.username.get_secret_value() == "candidate-user"
        assert resolved.password.get_secret_value() == "candidate-password"
        assert all(
            resolved.sources[key] == ConfigurationSource.PERSISTED
            for key in ("username", "password", "station_id", "device_id")
        )


def test_failed_candidate_configure_does_not_write_or_advance(
    beve_setup_context,
) -> None:
    factory, key_file, environment = beve_setup_context
    code = authorized_setup(factory)
    with factory() as session:
        result = configured_service(
            session,
            key_file,
            environment,
            FakeBeveFactory(BeveAuthenticationError("unsafe")),
        ).configure(setup_payload(code))
        session.commit()

        assert result.verification.category == "authentication_failed"
        assert result.setup.next_step == "beve"
        assert session.scalar(select(RuntimeConfigurationRecord)) is None
        assert session.get(InstallationStateRecord, 1).beve_configured is False


@pytest.mark.parametrize("initially_configured", [False, True])
def test_failed_persisted_reverification_restores_known_good_values(
    beve_setup_context, initially_configured
) -> None:
    factory, key_file, environment = beve_setup_context
    code = authorized_setup(factory)
    with factory() as session:
        runtime = RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        )
        runtime.set_secret("beve", "username", "known-good-user")
        runtime.set_secret("beve", "password", "known-good-password")
        runtime.set_non_secret("beve", "station_id", "known-good-station")
        runtime.set_non_secret("beve", "device_id", "known-good-device")
        session.get(InstallationStateRecord, 1).beve_configured = initially_configured
        session.commit()

        result = BeveSetupService(
            session,
            runtime,
            client_factory=FakeBeveFactory(
                VERIFIED_BEVE_RESPONSE,
                BeveTimeoutError("unsafe timeout detail"),
            ),
            environment=environment,
        ).configure(setup_payload(code))
        session.commit()

        assert result.verification.success is False
        assert result.verification.category == "timeout"
        assert session.get(InstallationStateRecord, 1).beve_configured is initially_configured
        restored = runtime.get_beve_configuration()
        assert restored.username.get_secret_value() == "known-good-user"
        assert restored.password.get_secret_value() == "known-good-password"
        assert restored.station_id == "known-good-station"
        assert restored.device_id == "known-good-device"


def test_verification_events_contain_only_safe_result_metadata(beve_setup_context) -> None:
    factory, key_file, environment = beve_setup_context
    code = authorized_setup(factory)
    with factory() as session:
        configured_service(
            session,
            key_file,
            environment,
            FakeBeveFactory(BeveAuthenticationError("candidate-password")),
        ).test_configuration(setup_payload(code))
        session.commit()
        event = session.scalar(
            select(SystemEventRecord).where(
                SystemEventRecord.category == "installation.beve"
            )
        )
        assert event.details == {
            "operation": "test",
            "result": "authentication_failed",
        }
        assert "candidate-password" not in str(event.details)
        assert "candidate-user" not in str(event.details)


def test_beve_setup_api_is_secret_safe_and_advances_status(beve_setup_context) -> None:
    factory, key_file, environment = beve_setup_context
    code = authorized_setup(factory)
    fake = FakeBeveFactory(
        VERIFIED_BEVE_RESPONSE,
        VERIFIED_BEVE_RESPONSE,
        VERIFIED_BEVE_RESPONSE,
    )

    def override_db():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def override_runtime(
        session=Depends(get_db),
    ) -> RuntimeConfigurationService:
        return RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_runtime_configuration_service] = override_runtime
    app.dependency_overrides[get_beve_setup_client_factory] = lambda: fake
    client = TestClient(app, base_url="https://testserver")
    request = {
        "setup_code": code,
        "username": "candidate-user",
        "password": "candidate-password",
        "station_id": "candidate-station",
        "device_id": "candidate-device",
    }
    try:
        tested = client.post("/api/v1/setup/beve/test", json=request)
        assert tested.status_code == 200
        assert tested.json()["success"] is True
        assert "candidate-password" not in tested.text
        assert "candidate-user" not in tested.text

        configured = client.post("/api/v1/setup/beve", json=request)
        assert configured.status_code == 200
        assert configured.json()["verification"]["success"] is True
        assert configured.json()["setup"]["next_step"] == "tuya"
        assert configured.json()["runtime_activation"] == "restart_required"
        assert "candidate-password" not in configured.text
        assert "candidate-user" not in configured.text

        status_response = client.get("/api/v1/setup/status")
        assert status_response.json()["beve_configured"] is True
        assert status_response.json()["next_step"] == "tuya"
    finally:
        app.dependency_overrides.clear()


def test_beve_setup_mutation_requires_valid_stage_and_code(beve_setup_context) -> None:
    factory, key_file, environment = beve_setup_context
    fake = FakeBeveFactory(VERIFIED_BEVE_RESPONSE)

    def override_db():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def override_runtime(session=Depends(get_db)):
        return RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_runtime_configuration_service] = override_runtime
    app.dependency_overrides[get_beve_setup_client_factory] = lambda: fake
    client = TestClient(app, base_url="https://testserver")
    try:
        uninitialized = client.post(
            "/api/v1/setup/beve", json=setup_payload("invalid").model_dump(mode="json")
        )
        assert uninitialized.status_code == 400

        with factory() as session:
            code = SetupService(session).initialize()
            session.commit()
        admin_missing = client.post(
            "/api/v1/setup/beve", json=setup_payload(code).model_dump(mode="json")
        )
        assert admin_missing.status_code == 400

        with factory() as session:
            session.get(InstallationStateRecord, 1).admin_configured = True
            session.commit()
        wrong_code = client.post(
            "/api/v1/setup/beve", json=setup_payload("wrong-code").model_dump(mode="json")
        )
        assert wrong_code.status_code == 400

        with factory() as session:
            state = session.get(InstallationStateRecord, 1)
            state.setup_completed = True
            session.commit()
        completed = client.post(
            "/api/v1/setup/beve", json=setup_payload(code).model_dump(mode="json")
        )
        assert completed.status_code == 410
        assert session_count(factory, RuntimeConfigurationRecord) == 0
    finally:
        app.dependency_overrides.clear()


def test_repeated_failed_beve_tests_are_rate_limited(beve_setup_context) -> None:
    factory, key_file, environment = beve_setup_context
    code = authorized_setup(factory)
    fake = FakeBeveFactory(BeveAuthenticationError("unsafe"))

    def override_db():
        with factory() as session:
            yield session
            session.commit()

    def override_runtime(session=Depends(get_db)):
        return RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_runtime_configuration_service] = override_runtime
    app.dependency_overrides[get_beve_setup_client_factory] = lambda: fake
    client = TestClient(app, base_url="https://testserver")
    request = setup_payload(code).model_dump(mode="json")
    try:
        for _ in range(setup_limiter.attempts):
            response = client.post("/api/v1/setup/beve/test", json=request)
            assert response.status_code == 200
            assert response.json()["category"] == "authentication_failed"
        limited = client.post("/api/v1/setup/beve/test", json=request)
        assert limited.status_code == 429
        assert "candidate-password" not in limited.text
    finally:
        app.dependency_overrides.clear()


def session_count(factory, record_type) -> int:
    with factory() as session:
        return session.scalar(select(func.count()).select_from(record_type))
