"""Run one configured PostgreSQL backup for systemd or manual use."""

from apps.db.session import session_scope
from apps.jobs.backup import BackupJob


def main() -> None:
    with session_scope() as session:
        result = BackupJob(session).run()
    if result.status != "succeeded":
        raise SystemExit("Backup failed; consult the admin backup status endpoint")
    size = f"{result.output_size_bytes} bytes" if result.output_size_bytes is not None else "size unavailable"
    print(f"Backup completed: {result.filename} ({size})")


if __name__ == "__main__":
    main()
