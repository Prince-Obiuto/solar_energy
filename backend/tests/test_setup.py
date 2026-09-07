"""First-run setup state, token, administrator, and API tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.setup import setup_limiter
from apps.db.base import Base
from apps.db.session import get_db
from apps.main import app
from apps.models.persistence import InstallationStateRecord, SystemEventRecord, UserRecord
from apps.services.setup_service import SetupLockedError, SetupService, SetupStateError

PASSWORD = "correct horse battery staple"


@pytest.fixture(autouse=True)
def isolate_setup_rate_limiter():
    setup_limiter.reset("verify:testclient")
    setup_limiter.reset("administrator:testclient")
    yield
    setup_limiter.reset("verify:testclient")
    setup_limiter.reset("administrator:testclient")


@pytest.fixture
def setup_context():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_initialize_hashes_token_is_idempotent_and_enforces_singleton(setup_context) -> None:
    with setup_context() as session:
        service = SetupService(session)
        code = service.initialize()
        session.commit()
        state = service.get_state()
        assert code and code not in state.setup_token_hash
        assert state.created_at.tzinfo is UTC
        assert service.verify(code) is True
        assert service.initialize() is None
        assert session.scalar(select(func.count()).select_from(InstallationStateRecord)) == 1
        session.add(InstallationStateRecord(id=2))
        with pytest.raises(IntegrityError):
            session.commit()


def test_wrong_token_and_rotation(setup_context) -> None:
    with setup_context() as session:
        service = SetupService(session)
        old = service.initialize(); session.commit()
        assert service.verify("WRONG-CODE-0000") is False
        failed = session.scalars(select(SystemEventRecord).where(
            SystemEventRecord.message == "Setup code verification failed"
        )).all()
        assert failed and all(event.details is None for event in failed)
        new = service.initialize(rotate=True); session.commit()
        assert new != old and service.verify(old) is False and service.verify(new) is True


def test_initial_admin_uses_auth_service_and_cannot_be_repeated(setup_context) -> None:
    with setup_context() as session:
        service = SetupService(session)
        code = service.initialize(); session.commit()
        user = service.create_administrator(code=code, email="ADMIN@EXAMPLE.TEST", password=PASSWORD, full_name="Initial Admin")
        session.commit()
        assert user.role == "admin" and user.email == "admin@example.test"
        assert service.get_state().admin_configured is True
        assert service.get_state().admin_configured_at.tzinfo is UTC
        assert session.scalar(select(SystemEventRecord).where(SystemEventRecord.category == "installation.setup"))
        with pytest.raises(SetupStateError):
            service.create_administrator(code=code, email="second@example.test", password=PASSWORD)


def test_invalid_token_and_weak_password_create_no_user(setup_context) -> None:
    with setup_context() as session:
        service = SetupService(session); code = service.initialize(); session.commit()
        with pytest.raises(SetupStateError):
            service.create_administrator(code="invalid", email="admin@example.test", password=PASSWORD)
        with pytest.raises(ValueError):
            service.create_administrator(code=code, email="admin@example.test", password="short")
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 0


def test_existing_users_are_never_exposed_to_first_admin_bootstrap(setup_context) -> None:
    from apps.services.auth_service import AuthService
    with setup_context() as session:
        AuthService(session).bootstrap_admin("existing@example.test", PASSWORD)
        state = SetupService(session).get_state()
        assert state.setup_initialized is True and state.admin_configured is True
        with pytest.raises(SetupStateError):
            SetupService(session).create_administrator(code="anything", email="new@example.test", password=PASSWORD)


def test_completed_setup_is_locked_and_status_is_minimal(setup_context) -> None:
    with setup_context() as session:
        service = SetupService(session); service.initialize()
        state = service.get_state(); state.setup_completed = True; state.completed_at = datetime.now(UTC); session.commit()
        assert service.progress() == {"setup_required": False, "setup_completed": True}
        with pytest.raises(SetupLockedError): service.initialize(rotate=True)


def test_progress_derives_each_future_setup_step(setup_context) -> None:
    with setup_context() as session:
        service = SetupService(session)
        assert service.progress()["next_step"] == "initialize"
        service.initialize()
        state = service.get_state()
        assert service.progress()["next_step"] == "administrator"
        state.admin_configured = True
        assert service.progress()["next_step"] == "beve"
        state.beve_configured = True
        assert service.progress()["next_step"] == "tuya"
        state.tuya_configured = True
        assert service.progress()["next_step"] == "devices"
        state.devices_verified = True
        assert service.progress()["next_step"] == "confirm"


def test_concurrent_first_admin_attempts_have_one_winner(tmp_path) -> None:
    database_path = tmp_path / "concurrent-setup.sqlite3"
    engine = create_engine(
        f"sqlite:///{database_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        code = SetupService(session).initialize()
        session.commit()

    def attempt(index: int) -> str:
        with factory() as session:
            try:
                SetupService(session).create_administrator(
                    code=code,
                    email=f"admin-{index}@example.test",
                    password=PASSWORD,
                )
                return "created"
            except SetupStateError:
                return "rejected"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, (1, 2)))

    with factory() as session:
        assert results.count("created") == 1
        assert results.count("rejected") == 1
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 1
        assert session.get(InstallationStateRecord, 1).admin_configured is True
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_initialize_setup_cli_prints_code_once_and_rotates(
    setup_context, monkeypatch, capsys
) -> None:
    from apps.scripts import initialize_setup

    @contextmanager
    def test_scope():
        with setup_context() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    monkeypatch.setattr(initialize_setup, "session_scope", test_scope)
    monkeypatch.setattr("sys.argv", ["initialize_setup"])
    assert initialize_setup.main() == 0
    first_output = capsys.readouterr().out
    first_code = re.search(r"[A-Z2-9]{4}(?:-[A-Z2-9]{4}){2}", first_output).group(0)

    assert initialize_setup.main() == 0
    second_output = capsys.readouterr().out
    assert "Setup is already initialized." in second_output
    assert first_code not in second_output

    monkeypatch.setattr("sys.argv", ["initialize_setup", "--rotate-token"])
    assert initialize_setup.main() == 0
    rotated_output = capsys.readouterr().out
    rotated_code = re.search(r"[A-Z2-9]{4}(?:-[A-Z2-9]{4}){2}", rotated_output).group(0)
    assert rotated_code != first_code
    with setup_context() as session:
        service = SetupService(session)
        assert service.verify(first_code) is False
        assert service.verify(rotated_code) is True


def test_setup_api_is_secret_safe_and_creates_admin(setup_context) -> None:
    with setup_context() as session:
        code = SetupService(session).initialize(); session.commit()
    def override_db():
        with setup_context() as session:
            yield session; session.commit()
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://testserver")
    try:
        status_response = client.get("/api/v1/setup/status")
        assert status_response.status_code == 200
        assert "token" not in status_response.text.lower() and "password" not in status_response.text.lower()
        assert client.post("/api/v1/setup/verify", json={"setup_code": "bad"}).json() == {"valid": False}
        response = client.post("/api/v1/setup/administrator", json={
            "setup_code": code, "email": "admin@example.test", "full_name": "Admin", "password": PASSWORD,
        })
        assert response.status_code == 201 and response.json()["administrator"]["role"] == "admin"
        assert "password" not in response.text.lower() and "token" not in response.text.lower()
    finally:
        app.dependency_overrides.clear()


def test_setup_api_rate_limits_verification_and_locks_completed_mutation(
    setup_context,
) -> None:
    with setup_context() as session:
        service = SetupService(session)
        service.initialize()
        session.commit()

    def override_db():
        with setup_context() as session:
            yield session
            session.commit()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://testserver")
    try:
        for _ in range(setup_limiter.attempts):
            assert client.post(
                "/api/v1/setup/verify", json={"setup_code": "invalid"}
            ).status_code == 200
        limited = client.post(
            "/api/v1/setup/verify", json={"setup_code": "invalid"}
        )
        assert limited.status_code == 429
        assert "invalid" not in limited.text

        setup_limiter.reset("administrator:testclient")
        with setup_context() as session:
            state = SetupService(session).get_state()
            state.setup_completed = True
            state.completed_at = datetime.now(UTC)
            session.commit()
        completed_status = client.get("/api/v1/setup/status")
        assert completed_status.status_code == 200
        assert completed_status.json() == {
            "setup_required": False,
            "setup_completed": True,
        }
        locked = client.post("/api/v1/setup/administrator", json={
            "setup_code": "not-returned",
            "email": "admin@example.test",
            "full_name": "Admin",
            "password": PASSWORD,
        })
        assert locked.status_code == 410
        assert "not-returned" not in locked.text
    finally:
        app.dependency_overrides.clear()
