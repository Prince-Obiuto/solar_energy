"""Authentication, token expiry, audit, and hierarchical RBAC tests."""

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.core.config import settings
from apps.core.security import hash_password
from apps.db.base import Base
from apps.db.session import get_db
from apps.main import app
from apps.models import UserRole
from apps.models.persistence import SystemEventRecord, UserRecord
from apps.services.auth_service import AuthService


PASSWORD = "correct horse battery staple"


@pytest.fixture
def auth_context():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    with factory() as session:
        for role in UserRole:
            session.add(UserRecord(
                id=uuid.uuid4(), email=f"{role.value}@example.test", full_name=role.value.title(),
                password_hash=hash_password(PASSWORD), role=role.value, is_active=True,
            ))
        session.commit()
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def login(client: TestClient, role: UserRole, password: str = PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": f"{role.value}@example.test", "password": password})


def bearer(client: TestClient, role: UserRole) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, role).json()['access_token']}"}


def test_valid_login_and_current_user(auth_context) -> None:
    client, factory = auth_context
    response = login(client, UserRole.STUDENT)
    assert response.status_code == 200
    current = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert current.status_code == 200
    assert current.json()["role"] == "student"
    with factory() as session:
        assert session.scalar(select(SystemEventRecord).where(SystemEventRecord.category == "auth.login.succeeded"))


def test_login_cookie_authenticates_current_user(auth_context) -> None:
    client, _ = auth_context

    response = login(client, UserRole.ADMIN)

    assert response.status_code == 200
    assert "access_token" in response.cookies

    current = client.get("/api/v1/auth/me")

    assert current.status_code == 200
    assert current.json()["role"] == "admin"


def test_invalid_login_is_generic_and_audited(auth_context) -> None:
    client, factory = auth_context
    response = login(client, UserRole.STUDENT, "wrong-password")
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    with factory() as session:
        event = session.scalar(select(SystemEventRecord).where(SystemEventRecord.category == "auth.login.failed"))
        assert event is not None
        assert "wrong-password" not in str(event.details)


def test_expired_token_is_rejected(auth_context) -> None:
    client, factory = auth_context
    with factory() as session:
        user = session.scalar(select(UserRecord).where(UserRecord.role == "student"))
        subject = str(user.id)
    expired = jwt.encode(
        {"sub": subject, "type": "access", "iat": datetime.now(UTC) - timedelta(hours=2), "exp": datetime.now(UTC) - timedelta(hours=1)},
        settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm,
    )
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_missing_token_is_rejected(auth_context) -> None:
    client, _ = auth_context
    response = client.get("/api/v1/energy")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_student_permissions(auth_context) -> None:
    client, _ = auth_context
    headers = bearer(client, UserRole.STUDENT)
    assert client.get("/api/v1/dashboard", headers=headers).status_code == 200
    assert client.get("/api/v1/energy", headers=headers).status_code == 200
    assert client.get("/api/v1/reports", headers=headers).status_code == 200
    assert client.get("/api/v1/devices", headers=headers).status_code == 403


def test_staff_permissions(auth_context) -> None:
    client, _ = auth_context
    headers = bearer(client, UserRole.STAFF)
    assert client.get("/api/v1/energy", headers=headers).status_code == 200
    assert client.get("/api/v1/devices", headers=headers).status_code == 200
    assert client.get("/api/v1/breakers", headers=headers).status_code == 200
    assert client.get("/api/v1/logs", headers=headers).status_code == 403


def test_admin_permissions(auth_context) -> None:
    client, _ = auth_context
    headers = bearer(client, UserRole.ADMIN)
    assert client.get("/api/v1/energy", headers=headers).status_code == 200
    assert client.get("/api/v1/devices", headers=headers).status_code == 200
    assert client.get("/api/v1/logs", headers=headers).status_code == 200
    assert client.get("/api/v1/controls", headers=headers).status_code == 200
    assert client.get("/api/v1/users", headers=headers).status_code == 200


def test_admin_can_create_user_without_password_exposure(auth_context) -> None:
    client, _ = auth_context
    response = client.post(
        "/api/v1/users", headers=bearer(client, UserRole.ADMIN),
        json={"email": "new.student@example.test", "full_name": "New Student", "password": PASSWORD, "role": "student"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "student"
    assert "password" not in response.text


def test_privilege_escalation_is_blocked(auth_context) -> None:
    client, _ = auth_context
    student_token = login(client, UserRole.STUDENT).json()["access_token"]
    assert client.get("/api/v1/logs", headers={"Authorization": f"Bearer {student_token}"}).status_code == 403
    payload = jwt.get_unverified_claims(student_token)
    payload["role"] = "admin"
    forged = jwt.encode(payload, "attacker-secret", algorithm=settings.jwt_algorithm)
    assert client.get("/api/v1/logs", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_initial_admin_bootstrap_is_one_time_and_does_not_elevate(auth_context) -> None:
    _, factory = auth_context
    with factory() as session:
        with pytest.raises(ValueError, match="will not be elevated"):
            AuthService(session).bootstrap_admin("student@example.test", PASSWORD)
        with pytest.raises(ValueError, match="before any users exist"):
            AuthService(session).bootstrap_admin("new-admin@example.test", PASSWORD)
        session.execute(delete(SystemEventRecord))
        session.execute(delete(UserRecord))
        session.commit()
        created = AuthService(session).bootstrap_admin("first-admin@example.test", PASSWORD)
        repeated = AuthService(session).bootstrap_admin("first-admin@example.test", PASSWORD)
        assert created.id == repeated.id
        assert created.role == UserRole.ADMIN.value
