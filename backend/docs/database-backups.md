# PostgreSQL backup operations

The backup job creates a PostgreSQL custom-format archive (`pg_dump -Fc`) with
level-9 compression. It writes to a `.partial` file and atomically renames the
file only after `pg_dump` succeeds. Run history is stored in `backup_runs`, and
failures create a `system.backup_failure` alert.

Configure these values in the protected backend environment file:

```dotenv
DATABASE_URL=postgresql+psycopg://<database-user>:<password>@<database-host>/<database-name>
BACKUP_DESTINATION=/path/owned/by/service/account
BACKUP_SECONDARY_DESTINATION=
BACKUP_RETENTION_DAYS=30
BACKUP_COMMAND=pg_dump
BACKUP_TIMEOUT_SECONDS=3600
```

`BACKUP_SECONDARY_DESTINATION` is optional. It can later point at a mounted
department backup PC or private-network storage. Mount and credential handling
belongs to the operating system; do not put network credentials in application
configuration. Both destinations must be writable by the service account.

## Manual backup

Activate the project virtual environment, load the protected environment file,
then run from `backend/`:

```bash
python -m apps.scripts.run_backup
```

The command returns a non-zero exit status on failure. Review results through
`GET /api/v1/backups/status` as an ADMIN, or query `backup_runs` directly.

## Restore

Stop writers or restore into a separate database first. PostgreSQL custom-format
archives are restored with `pg_restore`:

```bash
pg_restore --clean --if-exists --no-owner --dbname=<database-name> /path/to/solar_energy_<timestamp>_<id>.dump
```

Supply connection settings using protected `PGHOST`, `PGPORT`, `PGUSER`, and
`PGPASSWORD` environment variables (or a permission-restricted `.pgpass` file),
not command history. Test restore procedures regularly on a non-production
database before relying on a backup.

## systemd (recommended)

Create `/etc/systemd/system/solar-energy-backup.service`, replacing the bracketed
deployment values:

```ini
[Unit]
Description=Solar Energy PostgreSQL backup
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=<service-account>
Group=<service-group>
WorkingDirectory=<repository-path>/backend
EnvironmentFile=<protected-environment-file>
ExecStart=<virtualenv-path>/bin/python -m apps.scripts.run_backup
PrivateTmp=true
NoNewPrivileges=true
```

Create `/etc/systemd/system/solar-energy-backup.timer`:

```ini
[Unit]
Description=Nightly Solar Energy PostgreSQL backup

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true
RandomizedDelaySec=10m
Unit=solar-energy-backup.service

[Install]
WantedBy=timers.target
```

Validate and enable it:

```bash
sudo systemd-analyze verify /etc/systemd/system/solar-energy-backup.service /etc/systemd/system/solar-energy-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now solar-energy-backup.timer
sudo systemctl list-timers solar-energy-backup.timer
sudo systemctl start solar-energy-backup.service
sudo journalctl -u solar-energy-backup.service
```

`Persistent=true` runs a missed backup after the server returns. The randomized
delay avoids forcing every departmental scheduled task to start simultaneously.

## Cron alternative

If systemd is unavailable, install a crontab for the dedicated service account:

```cron
0 2 * * * cd <repository-path>/backend && <environment-loader> <virtualenv-path>/bin/python -m apps.scripts.run_backup
```

The environment loader must read a root/service-owned protected file. Do not
place credentials directly in the crontab. Arrange monitoring of the exit code;
the database alert records job failures but cannot detect a job that never ran.

## Operational checks

- Restrict backup directory and environment-file permissions.
- Monitor free space, timer execution, and `system.backup_failure` alerts.
- Confirm secondary storage is mounted before enabling its destination.
- Perform periodic test restores and document recovery time.
- Database history is operational metadata, not proof that an archive is
  independently recoverable.
