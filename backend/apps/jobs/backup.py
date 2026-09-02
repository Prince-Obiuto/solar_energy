"""Atomic compressed PostgreSQL backups with retention and run history."""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from apps.core.config import settings
from apps.models.persistence import BackupRunRecord
from apps.schemas.alert import AlertSeverity
from apps.services.alert_service import AlertService


@dataclass(frozen=True)
class BackupConfig:
    database_url: str
    destination: Path
    secondary_destination: Path | None
    retention_days: int
    command: str
    timeout_seconds: int

    @classmethod
    def from_settings(cls) -> "BackupConfig":
        return cls(
            database_url=settings.database_url.get_secret_value(),
            destination=settings.backup_destination,
            secondary_destination=settings.backup_secondary_destination,
            retention_days=settings.backup_retention_days,
            command=settings.backup_command,
            timeout_seconds=settings.backup_timeout_seconds,
        )


class BackupJob:
    def __init__(
        self,
        session: Session,
        *,
        config: BackupConfig | None = None,
        runner: Callable = subprocess.run,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.config = config or BackupConfig.from_settings()
        self.runner = runner
        self.clock = clock or (lambda: datetime.now(UTC))

    def run(self) -> BackupRunRecord:
        started_at = self.clock()
        run_id = uuid.uuid4()
        filename = f"solar_energy_{started_at.strftime('%Y%m%dT%H%M%SZ')}_{str(run_id)[:8]}.dump"
        record = BackupRunRecord(
            id=run_id, status="running", started_at=started_at,
            filename=filename,
            destination="primary+secondary" if self.config.secondary_destination else "primary",
        )
        self.session.add(record)
        self.session.commit()
        partial: Path | None = None
        try:
            url = make_url(self.config.database_url)
            if not url.drivername.startswith("postgresql") or not url.database:
                raise ValueError("Backup requires a PostgreSQL database URL")
            self.config.destination.mkdir(parents=True, exist_ok=True)
            final_path = self.config.destination / filename
            partial = self.config.destination / f"{filename}.partial"
            command = [
                self.config.command,
                "--format=custom",
                "--compress=9",
                "--file",
                str(partial),
                url.database,
            ]
            environment = self._postgres_environment(url)
            result = self.runner(
                command,
                env=environment,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"pg_dump exited with status {result.returncode}")
            if not partial.is_file():
                raise RuntimeError("pg_dump did not produce a backup file")
            os.replace(partial, final_path)
            record.output_size_bytes = final_path.stat().st_size
            if self.config.secondary_destination:
                self._copy_secondary(final_path, filename)
            record.status = "succeeded"
            AlertService(self.session, clock=self.clock).resolve("None:system.backup_failure")
            self._enforce_retention(self.config.destination)
            if self.config.secondary_destination:
                self._enforce_retention(self.config.secondary_destination)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
            record.status = "failed"
            record.error_information = "PostgreSQL backup failed"
            AlertService(self.session, clock=self.clock).raise_alert(
                dedup_key="None:system.backup_failure",
                category="system.backup_failure",
                severity=AlertSeverity.CRITICAL,
                message="Scheduled PostgreSQL backup failed",
                metadata={"backup_run_id": str(record.id)},
            )
        finally:
            if partial is not None:
                partial.unlink(missing_ok=True)
            record.finished_at = self.clock()
            self.session.commit()
        return record

    @staticmethod
    def _postgres_environment(url) -> dict[str, str]:
        environment = os.environ.copy()
        if url.host:
            environment["PGHOST"] = url.host
        if url.port:
            environment["PGPORT"] = str(url.port)
        if url.username:
            environment["PGUSER"] = url.username
        if url.password:
            environment["PGPASSWORD"] = url.password
        sslmode = url.query.get("sslmode")
        if sslmode:
            environment["PGSSLMODE"] = sslmode
        return environment

    def _copy_secondary(self, source: Path, filename: str) -> None:
        destination = self.config.secondary_destination
        if destination is None:
            return
        destination.mkdir(parents=True, exist_ok=True)
        partial = destination / f"{filename}.partial"
        try:
            shutil.copy2(source, partial)
            os.replace(partial, destination / filename)
        finally:
            partial.unlink(missing_ok=True)

    def _enforce_retention(self, destination: Path) -> None:
        cutoff = self.clock() - timedelta(days=self.config.retention_days)
        for backup in destination.glob("solar_energy_*.dump"):
            try:
                modified = datetime.fromtimestamp(backup.stat().st_mtime, tz=UTC)
                if modified < cutoff:
                    backup.unlink()
            except OSError:
                continue


def list_backup_runs(session: Session, *, limit: int = 20) -> list[BackupRunRecord]:
    return list(session.scalars(
        select(BackupRunRecord).order_by(BackupRunRecord.started_at.desc()).limit(limit)
    ))
