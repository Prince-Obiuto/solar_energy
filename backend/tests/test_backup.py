"""PostgreSQL backup job, retention, alerts, and ADMIN API tests."""

import os
import subprocess
import uuid
import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apps.db.base import Base
from apps.api.backups import backup_status, router as backup_router
from apps.core.permissions import require_admin
from apps.jobs.backup import BackupConfig, BackupJob
from apps.models import UserRole
from apps.models.persistence import AlertRecord, BackupRunRecord, UserRecord


NOW = datetime(2026, 9, 1, 2, 0, tzinfo=UTC)
DATABASE_URL = "postgresql+psycopg://backup_user:do-not-disclose@db.internal/solar_energy"


@pytest.fixture
def backup_context(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'backup-tests.sqlite3'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = BackupConfig(
        database_url=DATABASE_URL,
        destination=tmp_path / "primary",
        secondary_destination=tmp_path / "secondary",
        retention_days=7,
        command="pg_dump",
        timeout_seconds=60,
    )
    yield factory, config
    Base.metadata.drop_all(engine)
    engine.dispose()


def successful_runner(calls):
    def runner(command, **kwargs):
        calls.append((command, kwargs))
        output = command[command.index("--file") + 1]
        with open(output, "wb") as archive:
            archive.write(b"compressed-postgresql-archive")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return runner


def test_successful_compressed_backup_is_atomic_copied_and_hides_secrets(backup_context) -> None:
    factory, config = backup_context
    calls = []
    with factory() as session:
        result = BackupJob(
            session, config=config, runner=successful_runner(calls), clock=lambda: NOW
        ).run()

    command, options = calls[0]
    assert result.status == "succeeded" and result.output_size_bytes == 29
    assert "--format=custom" in command and "--compress=9" in command
    assert "do-not-disclose" not in " ".join(command)
    assert DATABASE_URL not in " ".join(command)
    assert options["env"]["PGPASSWORD"] == "do-not-disclose"
    assert (config.destination / result.filename).read_bytes() == b"compressed-postgresql-archive"
    assert (config.secondary_destination / result.filename).is_file()
    assert not list(config.destination.glob("*.partial"))
    assert not list(config.secondary_destination.glob("*.partial"))


def test_failed_and_timed_out_backups_create_one_deduplicated_alert(backup_context) -> None:
    factory, config = backup_context
    failures = [
        lambda *_args, **_kwargs: SimpleNamespace(returncode=2, stdout="", stderr="contains secret"),
        lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("pg_dump", 60)),
    ]
    with factory() as session:
        for runner in failures:
            result = BackupJob(session, config=config, runner=runner, clock=lambda: NOW).run()
            assert result.status == "failed"
            assert result.error_information == "PostgreSQL backup failed"
        records = session.scalars(select(BackupRunRecord)).all()
        alerts = session.scalars(select(AlertRecord)).all()

    assert len(records) == 2
    assert len(alerts) == 1 and alerts[0].category == "system.backup_failure"
    assert "secret" not in alerts[0].message
    assert all("do-not-disclose" not in (record.error_information or "") for record in records)


def test_retention_only_removes_expired_managed_archives(backup_context) -> None:
    factory, config = backup_context
    for destination in (config.destination, config.secondary_destination):
        destination.mkdir(parents=True)
        expired = destination / "solar_energy_20260801T020000Z_old.dump"
        unrelated = destination / "keep.dump"
        expired.write_bytes(b"old")
        unrelated.write_bytes(b"unrelated")
        old_timestamp = (NOW - timedelta(days=8)).timestamp()
        os.utime(expired, (old_timestamp, old_timestamp))

    with factory() as session:
        BackupJob(
            session, config=config, runner=successful_runner([]), clock=lambda: NOW
        ).run()

    for destination in (config.destination, config.secondary_destination):
        assert not (destination / "solar_energy_20260801T020000Z_old.dump").exists()
        assert (destination / "keep.dump").exists()


def test_success_resolves_prior_backup_failure_alert(backup_context) -> None:
    factory, config = backup_context
    failed = lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="")
    with factory() as session:
        BackupJob(session, config=config, runner=failed, clock=lambda: NOW).run()
        BackupJob(session, config=config, runner=successful_runner([]), clock=lambda: NOW).run()
        alert = session.scalar(select(AlertRecord))
    assert alert is not None and alert.resolved_at == NOW and alert.active is False


def test_backup_status_endpoint_is_admin_only_and_returns_safe_history(backup_context) -> None:
    factory, config = backup_context
    users = {}
    with factory() as session:
        for role in UserRole:
            user = UserRecord(
                id=uuid.uuid4(), email=f"{role.value}.backup@example.test",
                password_hash="unused-in-token-auth-test",
                role=role.value, is_active=True,
            )
            session.add(user)
            users[role] = user
        BackupJob(session, config=config, runner=successful_runner([]), clock=lambda: NOW).run()
        session.commit()

    for role in (UserRole.STUDENT, UserRole.STAFF):
        with pytest.raises(HTTPException) as denied:
            require_admin(user=users[role])
        assert denied.value.status_code == 403
    assert require_admin(user=users[UserRole.ADMIN]).role == UserRole.ADMIN.value
    assert any(dependency.dependency is require_admin for dependency in backup_router.routes[0].dependencies)

    with factory() as session:
        response = asyncio.run(backup_status(limit=20, session=session))
    assert response.total == 1 and response.current.status.value == "succeeded"
    serialized = response.model_dump_json()
    assert str(config.destination) not in serialized
    assert "do-not-disclose" not in serialized and "backup_user" not in serialized
