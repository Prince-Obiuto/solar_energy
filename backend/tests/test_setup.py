"""First-run setup state, token, administrator, and API tests."""
from __future__ import annotations
from datetime import UTC, datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from apps.db.base import Base
from apps.db.session import get_db
from apps.main import app
from apps.models.persistence import InstallationStateRecord, SystemEventRecord, UserRecord
from apps.services.setup_service import SetupLockedError, SetupService, SetupStateError

PASSWORD = "correct horse battery staple"


@pytest.fixture
def setup_context():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine); engine.dispose()


def test_initialize_hashes_token_is_idempotent_and_enforces_singleton(setup_context) -> None:
    with setup_context() as session:
        service = SetupService(session)
        code = service.initialize()
        session.commit()
        state = service.get_state()
        assert code and code not in state.setup_token_hash
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
