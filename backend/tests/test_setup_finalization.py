"""Final setup preflight, permanent token lock, and activation tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.setup import (
    get_runtime_configuration_service,
    setup_limiter,
)
from apps.core.config import Settings
from apps.core.runtime import RuntimeConfigurationError, build_application_runtime, configure_application_runtime
from apps.db.base import Base
from apps.db.session import get_db
from apps.main import app
from apps.models.persistence import InstallationStateRecord, RuntimeConfigurationRecord, SystemEventRecord
from apps.security.runtime_secrets import initialize_runtime_master_key
from apps.services.runtime_configuration_service import RuntimeConfigurationService
from apps.services.setup_finalization_service import SetupFinalizationService, SetupPreflightError
from apps.services.setup_service import SetupLockedError, SetupService, SetupStateError


BEVE_VALUES = {
    "username": "test-user-not-real",
    "password": "test-password-not-real",
    "station_id": "test-station",
    "device_id": "test-inverter",
}
TUYA_DEVICE = {
    "id": "test-breaker",
    "name": "Library breaker",
    "area": "Library",
    "key": "test-local-key-not-real",
    "ip": "192.0.2.42",
    "version": "3.5",
    "enabled": True,
}


class NoNetworkBeveClient:
    def __init__(self, config) -> None:
        self.config = config


class NoNetworkTuyaClient:
    def __init__(self, config) -> None:
        self.config = config


@pytest.fixture(autouse=True)
def isolate_rate_limits():
    operations = (
        "verify", "administrator", "beve-test", "beve-configure",
        "tuya-cloud", "tuya-scan", "tuya-devices", "tuya-status", "complete",
    )
    for operation in operations:
        setup_limiter.reset(f"{operation}:testclient")
    yield
    for operation in operations:
        setup_limiter.reset(f"{operation}:testclient")


@pytest.fixture
def finalization_context(tmp_path):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    key_file = tmp_path / "master.key"
    initialize_runtime_master_key(key_file)
    environment = Settings(
        _env_file=None,
        app_env="test",
        runtime_master_key_file=key_file,
        tuya_device_file=tmp_path / "unused-devices.json",
        beve_username="environment-must-not-satisfy-finalization",
        beve_password="environment-must-not-satisfy-finalization",
        beve_station_id="environment-station",
        beve_device_id="environment-device",
    )
    try:
        yield sessions, key_file, environment
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def prepare_ready_installation(sessions, key_file, environment) -> str:
    with sessions() as session:
        setup = SetupService(session)
        code = setup.initialize()
        state = setup.get_state()
        state.admin_configured = True
        state.beve_configured = True
        state.tuya_configured = True
        state.devices_verified = True
        runtime = RuntimeConfigurationService(
            session,
            environment=environment,
            master_key_file=str(key_file),
        )
        runtime.set_secret("beve", "username", BEVE_VALUES["username"])
        runtime.set_secret("beve", "password", BEVE_VALUES["password"])
        runtime.set_non_secret("beve", "station_id", BEVE_VALUES["station_id"])
        runtime.set_non_secret("beve", "device_id", BEVE_VALUES["device_id"])
        runtime.set_tuya_device_configuration([TUYA_DEVICE])
        session.commit()
        return code


def finalizer(session, key_file, environment) -> SetupFinalizationService:
    return SetupFinalizationService(
        session,
        RuntimeConfigurationService(
            session,
            environment=environment,
            master_key_file=str(key_file),
        ),
    )


def test_successful_finalization_destroys_token_and_marks_activation_pending(
    finalization_context,
) -> None:
    sessions, key_file, environment = finalization_context
    code = prepare_ready_installation(sessions, key_file, environment)
    with sessions() as session:
        state = finalizer(session, key_file, environment).complete(code)

        assert state.setup_completed is True
        assert state.completed_at is not None
        assert state.runtime_activation_pending is True
        assert state.runtime_activated_at is None
        assert state.setup_token_hash is None
        assert SetupService(session).verify(code) is False
        assert SetupService(session).progress() == {
            "setup_required": False,
            "setup_completed": True,
            "activation_required": True,
        }
        assert session.scalar(select(SystemEventRecord).where(
            SystemEventRecord.message == "Setup finalized"
        )) is not None


@pytest.mark.parametrize(
    "missing_flag",
    ["admin_configured", "beve_configured", "tuya_configured", "devices_verified"],
)
def test_incomplete_setup_flags_cannot_finalize(
    finalization_context, missing_flag
) -> None:
    sessions, key_file, environment = finalization_context
    code = prepare_ready_installation(sessions, key_file, environment)
    with sessions() as session:
        state = session.get(InstallationStateRecord, 1)
        setattr(state, missing_flag, False)
        session.commit()
        with pytest.raises(SetupStateError):
            finalizer(session, key_file, environment).complete(code)
        state = session.get(InstallationStateRecord, 1)
        assert state.setup_completed is False
        assert state.setup_token_hash is not None


def test_missing_or_corrupt_persisted_beve_configuration_is_rejected(
    finalization_context,
) -> None:
    sessions, key_file, environment = finalization_context
    code = prepare_ready_installation(sessions, key_file, environment)
    with sessions() as session:
        record = session.scalar(select(RuntimeConfigurationRecord).where(
            RuntimeConfigurationRecord.namespace == "beve",
            RuntimeConfigurationRecord.key == "password",
        ))
        session.delete(record)
        session.commit()
        with pytest.raises(SetupPreflightError) as captured:
            finalizer(session, key_file, environment).complete(code)
        assert captured.value.category == "beve_configuration_invalid"
        assert session.get(InstallationStateRecord, 1).setup_completed is False

    with sessions() as session:
        RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        ).set_secret("beve", "password", BEVE_VALUES["password"])
        session.commit()
        record = session.scalar(select(RuntimeConfigurationRecord).where(
            RuntimeConfigurationRecord.namespace == "beve",
            RuntimeConfigurationRecord.key == "password",
        ))
        record.value = "corrupt-ciphertext"
        session.commit()
        with pytest.raises(SetupPreflightError) as captured:
            finalizer(session, key_file, environment).complete(code)
        assert captured.value.category == "beve_configuration_invalid"


def test_missing_or_corrupt_persisted_tuya_configuration_is_rejected(
    finalization_context,
) -> None:
    sessions, key_file, environment = finalization_context
    code = prepare_ready_installation(sessions, key_file, environment)
    with sessions() as session:
        record = session.scalar(select(RuntimeConfigurationRecord).where(
            RuntimeConfigurationRecord.namespace == "tuya_devices"
        ))
        session.delete(record)
        session.commit()
        with pytest.raises(SetupPreflightError) as captured:
            finalizer(session, key_file, environment).complete(code)
        assert captured.value.category == "tuya_configuration_invalid"

    with sessions() as session:
        RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        ).set_tuya_device_configuration([TUYA_DEVICE])
        session.commit()
        record = session.scalar(select(RuntimeConfigurationRecord).where(
            RuntimeConfigurationRecord.namespace == "tuya_devices"
        ))
        record.value = "corrupt-ciphertext"
        session.commit()
        with pytest.raises(SetupPreflightError) as captured:
            finalizer(session, key_file, environment).complete(code)
        assert captured.value.category == "tuya_configuration_invalid"


def test_missing_master_key_and_wrong_code_cannot_finalize(
    finalization_context, tmp_path
) -> None:
    sessions, key_file, environment = finalization_context
    code = prepare_ready_installation(sessions, key_file, environment)
    with sessions() as session:
        missing_key_finalizer = finalizer(
            session,
            tmp_path / "missing-master.key",
            environment,
        )
        with pytest.raises(SetupPreflightError) as captured:
            missing_key_finalizer.complete(code)
        assert captured.value.category == "master_key_unavailable"
        with pytest.raises(SetupStateError):
            finalizer(session, key_file, environment).complete("incorrect-code")


def test_second_finalization_is_locked_without_state_corruption(
    finalization_context,
) -> None:
    sessions, key_file, environment = finalization_context
    code = prepare_ready_installation(sessions, key_file, environment)
    with sessions() as session:
        finalizer(session, key_file, environment).complete(code)
        with pytest.raises(SetupLockedError):
            finalizer(session, key_file, environment).complete(code)
        state = session.get(InstallationStateRecord, 1)
        assert state.runtime_activation_pending is True
        assert state.setup_token_hash is None


def test_concurrent_finalization_has_one_winner(tmp_path) -> None:
    database = tmp_path / "concurrent-finalization.sqlite3"
    engine = create_engine(
        f"sqlite:///{database}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    key_file = tmp_path / "concurrent-master.key"
    initialize_runtime_master_key(key_file)
    environment = Settings(
        _env_file=None,
        app_env="test",
        runtime_master_key_file=key_file,
        beve_username=None,
        beve_password=None,
        beve_station_id=None,
        beve_device_id=None,
    )
    code = prepare_ready_installation(sessions, key_file, environment)

    def attempt() -> str:
        with sessions() as session:
            try:
                finalizer(session, key_file, environment).complete(code)
                return "completed"
            except SetupLockedError:
                return "locked"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))

    assert results.count("completed") == 1
    assert results.count("locked") == 1
    with sessions() as session:
        state = session.get(InstallationStateRecord, 1)
        assert state.setup_completed is True
        assert state.setup_token_hash is None
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_activation_acknowledgement_only_clears_a_pending_completed_runtime(
    finalization_context,
) -> None:
    sessions, key_file, environment = finalization_context
    code = prepare_ready_installation(sessions, key_file, environment)
    with sessions() as session:
        setup = SetupService(session)
        assert setup.mark_runtime_activated() is False
        finalizer(session, key_file, environment).complete(code)
        assert setup.mark_runtime_activated() is True
        state = session.get(InstallationStateRecord, 1)
        assert state.runtime_activation_pending is False
        assert state.runtime_activated_at is not None
        assert setup.mark_runtime_activated() is False
        assert session.scalar(select(SystemEventRecord).where(
            SystemEventRecord.message == "Runtime configuration activated"
        )) is not None


def test_finalized_runtime_requires_persisted_values_and_performs_no_reads(
    finalization_context,
) -> None:
    sessions, key_file, environment = finalization_context
    prepare_ready_installation(sessions, key_file, environment)
    try:
        runtime = build_application_runtime(
            environment,
            beve_client_factory=NoNetworkBeveClient,
            tuya_client_factory=NoNetworkTuyaClient,
            session_factory=sessions,
            provision=False,
            require_persisted_configuration=True,
        )
        assert runtime.inverter_device_reference == BEVE_VALUES["device_id"]
        assert runtime.breaker_service.registered_breaker_ids == (TUYA_DEVICE["id"],)
    finally:
        configure_application_runtime(None)

    with sessions() as session:
        session.delete(session.scalar(select(RuntimeConfigurationRecord).where(
            RuntimeConfigurationRecord.namespace == "tuya_devices"
        )))
        session.commit()
    with pytest.raises(RuntimeConfigurationError, match="Persisted Tuya"):
        build_application_runtime(
            environment,
            beve_client_factory=NoNetworkBeveClient,
            tuya_client_factory=NoNetworkTuyaClient,
            session_factory=sessions,
            provision=False,
            require_persisted_configuration=True,
        )


@pytest.mark.asyncio
async def test_successful_startup_acknowledges_activation_once(
    finalization_context, monkeypatch
) -> None:
    import apps.main as main_module

    sessions, key_file, environment = finalization_context
    code = prepare_ready_installation(sessions, key_file, environment)
    with sessions() as session:
        finalizer(session, key_file, environment).complete(code)

    class Collector:
        started = 0
        stopped = 0

        async def start(self):
            self.started += 1

        async def stop(self):
            self.stopped += 1

    class Breakers:
        closed = 0

        def close(self):
            self.closed += 1

    collector = Collector()
    breakers = Breakers()
    holder = {"runtime": None}

    def build(**kwargs):
        assert kwargs["require_persisted_configuration"] is True
        holder["runtime"] = SimpleNamespace(
            collector=collector,
            breaker_service=breakers,
        )
        return holder["runtime"]

    @contextmanager
    def local_scope():
        with sessions() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    async def no_op():
        return None

    monkeypatch.setattr(main_module, "_installation_runtime_state", lambda: (True, True))
    monkeypatch.setattr(main_module, "build_application_runtime", build)
    monkeypatch.setattr(main_module, "get_application_runtime", lambda: holder["runtime"])
    monkeypatch.setattr(main_module, "get_energy_collector", lambda: collector if holder["runtime"] else None)
    monkeypatch.setattr(main_module, "session_scope", local_scope)
    monkeypatch.setattr(main_module.connection_manager, "start", no_op)
    monkeypatch.setattr(main_module.connection_manager, "stop", no_op)
    monkeypatch.setattr(main_module.health_monitor, "start", no_op)
    monkeypatch.setattr(main_module.health_monitor, "stop", no_op)

    async with main_module.lifespan(app):
        with sessions() as session:
            state = session.get(InstallationStateRecord, 1)
            assert state.runtime_activation_pending is False
            assert state.runtime_activated_at is not None
        assert collector.started == 1
    assert collector.stopped == 1
    assert breakers.closed == 1


@pytest.mark.asyncio
async def test_failed_runtime_build_leaves_activation_pending_and_status_available(
    finalization_context, monkeypatch
) -> None:
    import apps.main as main_module

    sessions, key_file, environment = finalization_context
    code = prepare_ready_installation(sessions, key_file, environment)
    with sessions() as session:
        finalizer(session, key_file, environment).complete(code)

    async def no_op():
        return None

    def fail_build(**_kwargs):
        raise RuntimeConfigurationError("safe test failure")

    monkeypatch.setattr(main_module, "_installation_runtime_state", lambda: (True, True))
    monkeypatch.setattr(main_module, "build_application_runtime", fail_build)
    monkeypatch.setattr(main_module, "configure_application_runtime", lambda _runtime: None)
    monkeypatch.setattr(main_module, "get_application_runtime", lambda: None)
    monkeypatch.setattr(main_module, "get_energy_collector", lambda: None)
    monkeypatch.setattr(main_module.connection_manager, "start", no_op)
    monkeypatch.setattr(main_module.connection_manager, "stop", no_op)
    monkeypatch.setattr(main_module.health_monitor, "start", no_op)
    monkeypatch.setattr(main_module.health_monitor, "stop", no_op)

    async with main_module.lifespan(app):
        with sessions() as session:
            assert SetupService(session).progress() == {
                "setup_required": False,
                "setup_completed": True,
                "activation_required": True,
            }


def test_completion_api_and_all_first_run_mutations_lock_after_success(
    finalization_context,
) -> None:
    sessions, key_file, environment = finalization_context
    code = prepare_ready_installation(sessions, key_file, environment)

    def override_db():
        with sessions() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def override_runtime(session=Depends(get_db)):
        return RuntimeConfigurationService(
            session,
            environment=environment,
            master_key_file=str(key_file),
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_runtime_configuration_service] = override_runtime
    client = TestClient(app, base_url="https://testserver")
    try:
        completed = client.post(
            "/api/v1/setup/complete", json={"setup_code": code}
        )
        assert completed.status_code == 200
        assert completed.json()["success"] is True
        assert completed.json()["setup"] == {
            "setup_required": False,
            "setup_completed": True,
            "activation_required": True,
        }
        assert completed.json()["runtime_activation"] == "restart_required"
        assert code not in completed.text

        status = client.get("/api/v1/setup/status")
        assert status.json() == {
            "setup_required": False,
            "setup_completed": True,
            "activation_required": True,
        }
        assert client.post("/api/v1/setup/verify", json={"setup_code": code}).json() == {"valid": False}
        locked_requests = [
            ("/api/v1/setup/administrator", {"setup_code": code, "email": "new@example.test", "password": "long-enough-password"}),
            ("/api/v1/setup/beve/test", {"setup_code": code, **BEVE_VALUES}),
            ("/api/v1/setup/beve", {"setup_code": code, **BEVE_VALUES}),
            ("/api/v1/setup/tuya/cloud", {"setup_code": code, "region": "eu", "access_id": "test-id", "access_secret": "test-secret"}),
            ("/api/v1/setup/tuya/scan", {"setup_code": code, "onboarding_session": "x" * 32}),
            ("/api/v1/setup/tuya/status", {"setup_code": code}),
            ("/api/v1/setup/tuya/devices", {"setup_code": code, "onboarding_session": "x" * 32, "devices": [{"device_ref": "r" * 16, "friendly_name": "Test", "area": "Test"}]}),
            ("/api/v1/setup/complete", {"setup_code": code}),
        ]
        for path, payload in locked_requests:
            response = client.post(path, json=payload)
            assert response.status_code == 410, (path, response.text)
            assert code not in response.text
        with sessions() as session:
            with pytest.raises(SetupLockedError):
                SetupService(session).initialize(rotate=True)
    finally:
        app.dependency_overrides.clear()
