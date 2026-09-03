# Smart Renewable Energy Management System guide

This document describes the implementation currently present in the repository.
It does not imply hardware support beyond the verified BEVE and TMPH mappings.

## 1. Architecture overview

```text
FiveStar inverter → Wi-Fi dongle → Internet → BEVE/Siseli cloud → Internet ─┐
                                                                            ├─ normalized services → collector/cache → REST/WebSocket
TMPH breaker → local Wi-Fi/LAN → TinyTuya ──────────────────────────────────┘                           │
                                                                                                      └─ PostgreSQL

React ─ REST /api/v1 + authenticated WS /api/v1/ws/energy
```

Vendor request formats and datapoints remain under `backend/apps/integrations/`.
API, services, persistence, realtime messages, and React consume normalized
models. The inverter integration exposes no write method. Breaker writes pass
through an ADMIN-only, allowlisted, audited, read-back-verified workflow.

The collector is intentionally decoupled from FastAPI requests. Dashboard and
WebSocket consumers use collector/cache or persisted state rather than polling
hardware per widget.

BEVE connectivity describes availability of the cloud telemetry path, not
direct reachability of the physical inverter. A BEVE failure retains the last
known inverter values and marks their `data_status` stale/unavailable. TinyTuya
connectivity is local and may mark a breaker offline after bounded LAN retries.

## 2. Repository structure

```text
backend/
  apps/api/             FastAPI route adapters
  apps/core/            settings, security, permissions, logging, rate limit
  apps/db/              SQLAlchemy engine and transactional sessions
  apps/integrations/    BEVE and TinyTuya protocol boundaries
  apps/jobs/            collector, health monitor, backup job
  apps/models/          domain and SQLAlchemy models
  apps/realtime/        WebSocket connection/event management
  apps/schemas/         API and reusable Pydantic schemas
  apps/services/        application services
  apps/scripts/         admin bootstrap and one-shot backup commands
  migrations/           Alembic revisions
  tests/                backend tests and hardware fakes
frontend/
  src/app/              providers, authentication, routing
  src/features/         feature components, hooks, REST adapters
  src/components/       shared UI, layout, charts and tables
  src/services/         Axios and realtime clients
docs/                   system-level documentation
```

## 3. Local development instructions

Requirements are Python 3.12-compatible tooling, PostgreSQL, Node.js 20+, and
npm. Do not use real hardware credentials in a shared development environment.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env

cd frontend
npm install
cp .env.example .env
```

Fill only local values in the ignored `.env` files. Start PostgreSQL and apply
migrations before starting the complete backend.

## 4. Backend startup

```bash
cd backend
python -m uvicorn apps.main:app --reload
```

Swagger is available at `/docs`; health endpoints are `/health` and
`/api/v1/health`. Production should run without `--reload` behind a TLS reverse
proxy and with an explicit worker/process policy.

## 5. Frontend startup

```bash
cd frontend
npm run dev
```

For production assets:

```bash
npm run lint
npm run build
```

Serve `frontend/dist/` through the production web server and proxy `/api/v1`
including WebSocket upgrades to FastAPI.

## 6. Environment variables

Backend variables are documented with safe placeholders in
`backend/.env.example`:

- Application: `APP_NAME`, `APP_ENV`, `APP_VERSION`, `API_V1_PREFIX`.
- HTTP security: `CORS_ORIGINS`, `ALLOWED_HOSTS`, `MAX_REQUEST_BODY_BYTES`,
  `LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS`, `LOG_LEVEL`.
- Database/auth: `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`,
  `ACCESS_TOKEN_EXPIRE_MINUTES`, initial-admin values.
- BEVE/Siseli: username, password, station/device identifiers, time zone and
  timeout. The `siseli` package owns vendor authentication and request signing;
  application IDs/secrets are not application configuration.
- TinyTuya: `TUYA_DEVICE_FILE`, local socket timeout, polling interval and
  control verification delay. Secrets remain in the wizard-generated file.
- Collection: independent BEVE/Tuya intervals, persistence interval, retry,
  stale, WebSocket and health-monitor timings.
- Alerts: optional electrical threshold values. Blank means disabled.
- Backup: primary/secondary destination, retention, command and timeout.

Frontend variables are in `frontend/.env.example`: REST base, optional absolute
WebSocket URL, and the display stale threshold. Production JWT and credential
values must never use repository defaults.

## 7. PostgreSQL setup

Create a dedicated database and least-privilege application account using local
department policy. Put its URL only in the protected backend environment file.
The schema stores areas/devices, normalized telemetry, users, control/system
events, alerts, and backup history. Hardware secrets are not Device columns.

Telemetry tables have device/timestamp and timestamp indexes. Device, alert,
event, user, control request, and backup status/time access paths have dedicated
indexes or uniqueness constraints.

## 8. Alembic migrations

```bash
cd backend
alembic upgrade head
alembic current
```

Test downgrade behavior on a disposable database before production changes:

```bash
alembic downgrade -1
alembic upgrade head
```

Never downgrade production without a database backup and reviewed recovery plan.

## 9. BEVE inverter integration

`backend/apps/integrations/inverter/` wraps the proven `SolarOfThingsAPI` login
and device listing from the repository-local `energy/siseli` package (or an
installed `siseli` package), then uses that authenticated session for the
verified current-state endpoint. Authentication signing and session details
remain owned by that library. The adapter is strictly read-only;
it normalizes inverter, battery, solar, and grid categories, preserves legitimate
hardware zero values, and maps only absent values to null. Credentials and
session details are never serialized or logged.

BEVE cloud connectivity and inverter source-data freshness are deliberately
separate. `last_successful_poll_at` is the backend time when a structurally
valid cloud response completed; `source_timestamp` is the unchanged vendor time
inside that response. Repeated Siseli samples therefore keep the cloud
`connected` while their source age increases. `BEVE_POLL_STALE_AFTER_SECONDS`
controls connectivity staleness and `BEVE_SOURCE_STALE_AFTER_SECONDS` controls
source-data safety (default 900 seconds). A delayed source sample remains
visible but cannot advance automatic load-management confirmation.

## 10. Tuya breaker configuration

The verified device is WIFl Smart Meter Pro / TMPH, category `znjdq`, protocol
3.5. Run the TinyTuya wizard on the backend host to produce `devices.json`, then
set `TUYA_DEVICE_FILE` if it is not at `backend/devices.json`. At startup the
application loads every valid TMPH entry, constructs an independent local-LAN
client and breaker registration for each, and starts an independent collector
loop. The list is variable-length; adding a supported breaker requires a wizard
entry, not a Python change.

`devices.json` contains local keys. It, `snapshot.json`, `tinytuya.json`,
`tuya-raw.json`, and `.env` are recursively ignored and must never be committed,
logged, returned by REST, or published by WebSocket. Normal monitoring uses only
local TinyTuya communication and does not consume `tinytuya.json` cloud
credentials. Configure DHCP reservations/static leases for deployed breakers;
the saved IP is used directly and the backend does not scan the LAN on every
poll.

Only verified control DPs 1, 9, 38, 40 and 41 are allowlisted. Calibration DPs
22–25 and unknown DPs 21, 26 and 42 cannot be written through the adapter.

## 11. Device onboarding

1. Run the TinyTuya wizard and confirm the local IP, protocol and TMPH identity.
2. Keep its generated files readable only by the backend service account.
3. Start the application. Missing Area and Device rows are provisioned
   transactionally and idempotently before collection starts.
4. Customize friendly names/areas in the database if required; existing values
   are preferred on subsequent starts and are not overwritten.
5. Verify normalized read-only telemetry before exercising ADMIN controls.
6. Test read-back verification and audit persistence under supervision.

FastAPI lifespan composes the environment-backed read-only BEVE client, every
configured TinyTuya breaker, normalized services, persistence adapter, event
publisher and collector. Development can start without hardware configuration;
partially supplied BEVE settings fail with a sanitized configuration error.

The collector uses monotonic start-to-start scheduling, bounded retries, and a
per-source async lock. Breaker socket access also has a shared per-device lock:
collector polling and a command's complete read/write/read-back sequence cannot
overlap for the same breaker, while different breakers remain independent.
Monitoring routes consume collector state first and persisted state second;
they never initiate TinyTuya traffic. WebSocket-triggered frontend refreshes are
debounced/coalesced so bursts result in at most one request in flight.

## 12. REST endpoint inventory

Public: `GET /`, `GET /health`, `GET /api/v1/health`, `POST /auth/login`, and
`POST /auth/logout` under `/api/v1`.

Authenticated routes under `/api/v1`:

- Auth: `GET /auth/me`.
- Dashboard: `GET /dashboard`, `/dashboard/summary`, `/dashboard/areas`.
- Devices/energy: `GET /devices`, `/devices/{id}`, `/energy`,
  `/energy/latest`, `/energy/history`.
- Inverter: `GET /inverter`, `/inverter/battery`, `/inverter/solar`,
  `/inverter/grid`.
- Breakers: `GET /breakers`, `/breakers/{id}` and ADMIN control routes for
  switch, countdown, relay restore mode, indicator mode, and child lock.
- Reports: `GET /reports`, `/reports/export.csv`, `/reports/export.pdf`.
- Alerts: list, detail, and acknowledgement endpoints.
- Smart load management: `GET /load-management` (authenticated read-only status).
- Administration: users list/create/update, audit logs, control inventory, and
  backup status.

Exact schemas and query parameters are authoritative in `/docs`.

## 13. WebSocket event inventory

Authenticated endpoint: `WS /api/v1/ws/energy`. Messages are normalized and may
include `inverter.status`, `battery.status`, `solar.status`, `grid.status`,
`breaker.telemetry`, `breaker.status`, `device.online`, `device.offline`,
`energy.update`, `load_management.status`, `load_management.shed`,
`load_management.restored`, `load_management.action_failed`, alert lifecycle
events, and `system.status`. The browser sends
`{"type":"ping"}`; the server responds with a system-status pong. Connection
cleanup and broadcast isolation prevent one failed client breaking others.

## 14. Authentication and RBAC

Passwords are PBKDF2-SHA256 hashes. JWT access tokens expire and are placed in an
HttpOnly, SameSite=Lax cookie; production cookies are Secure. The frontend does
not persist tokens in local storage. Login failures use a generic response and
are audited. An in-process sliding-window limiter bounds login attempts per
client address; use a shared reverse-proxy limiter when deploying multiple
workers.

Roles are hierarchical: STUDENT for dashboard/permitted reports, STAFF for
detailed devices/areas, and ADMIN for controls/users/audit/backup operations.
Frontend guards improve UX; backend dependencies are the security boundary.

Bootstrap the first administrator once:

```bash
cd backend
python -m apps.scripts.bootstrap_admin
```

## 15. Breaker control and smart load-management workflow

An ADMIN submits an allowlisted, validated request ID and value. Switch requests
also require explicit confirmation and a reason. The service reads the previous
value, writes through TinyTuya, waits briefly, reads the DP again, and reports
success only on exact type/value match. Each lifecycle is stored in
`control_events`; request IDs prevent duplicate execution. There is no inverter
control. The ADMIN Controls page exposes only the verified Tuya command surface.

Smart load management consumes only a successful current BEVE/Siseli battery
SOC sample from the existing collector. It never uses dashboard persistence,
stale last-known data, or an independent polling loop, and it never writes to
the inverter. After two consecutive qualifying readings (configurable), it
uses the same audited TinyTuya DP1 command and read-back verification path as
manual control.

Confirmation counts distinct, increasing `source_timestamp` values—not HTTP
polls. Five successful polls returning the same Siseli sample count once, and a
timestamp moving backwards does not count. A source sample older than
`BEVE_SOURCE_STALE_AFTER_SECONDS` pauses automation without changing either
relay; the last known SOC remains available for monitoring.

| Policy | Shed | Restore |
| --- | ---: | ---: |
| Lecturer Offices | SOC ≤ 20% | SOC ≥ 22% |
| Admin Office | SOC ≤ 15% | SOC ≥ 17% |

The two-percent hysteresis gap prevents relay chatter. Values inside the gap
preserve automation ownership/state. `load_shedding_states` records whether the
automation successfully shed each load, so ownership survives restarts. A
manually OFF breaker is never automatically restored. If an administrator turns
an auto-shed breaker ON while its confirmed low-SOC condition remains, the
enabled safety policy is authoritative and may shed it again after a new full
confirmation sequence. Failed or mismatched commands remain eligible for a
later retry and never claim successful ownership.

Configure TinyTuya external device references (not local keys) with:

```dotenv
LOAD_SHEDDING_ENABLED=true
LOAD_SHEDDING_CONFIRM_READINGS=2
LOAD_SHEDDING_LECTURER_BREAKER_ID=
LOAD_SHEDDING_LECTURER_SHED_SOC=20
LOAD_SHEDDING_LECTURER_RESTORE_SOC=22
LOAD_SHEDDING_ADMIN_BREAKER_ID=
LOAD_SHEDDING_ADMIN_SHED_SOC=15
LOAD_SHEDDING_ADMIN_RESTORE_SOC=17
```

Blank IDs disable the affected policy. Set `LOAD_SHEDDING_ENABLED=false` to
guarantee no automatic commands. At deployment, map each ID to the corresponding
entry already loaded from `TUYA_DEVICE_FILE`, apply migrations, verify the
read-only status endpoint, then supervise threshold/control tests with isolated
loads. BEVE/Siseli remains strictly read-only; only Tuya breakers are controlled.

## 16. Audit logging

Authentication and report access use `system_events`; breaker commands use
`control_events`. `GET /api/v1/logs` exposes a bounded ADMIN-only normalized view
without raw detail payloads. Application request logs include only method, path,
status and duration—never headers, query strings, bodies, credentials or tokens.

## 17. Reporting

PostgreSQL-backed raw/minute/hour/day history supports inverter, battery, solar,
grid and area sources with bounded date/device/area filters. CSV uses ISO 8601
timestamps; PDF provides a bounded technical summary. Access/export is audited.
Tuya accumulated energy remains neutrally named because its unit is unverified.

## 18. Alerts

The health engine handles supported offline, stale, polling, control,
authentication, malformed telemetry, collector, database, backup and WebSocket
conditions. Electrical thresholds are disabled until explicitly configured.
Active alerts are deduplicated and can be resolved/acknowledged. Legitimate BEVE
states and real zero values are not faults.

## 19. Backup and restore

The one-shot backup job uses compressed custom-format `pg_dump`, atomic rename,
retention, optional secondary copy, persisted history, and failure alerts. The
nightly systemd timer, manual backup, restore and cron alternative are documented
in [backend/docs/database-backups.md](../backend/docs/database-backups.md).

## 20. Production deployment

- Use TLS and proxy HTTP/WebSocket traffic through the same trusted origin.
- Set `APP_ENV=production`, a random JWT secret, exact CORS origins and allowed
  hosts; keep environment-file permissions restrictive.
- Run Alembic before starting the service.
- Use dedicated OS/database accounts and writable telemetry/backup locations.
- Install the systemd backup timer and monitor its status.
- Configure log rotation, disk monitoring, PostgreSQL backup verification, and
  reverse-proxy request/rate limits.
- Do not use reload mode or expose PostgreSQL/Tuya devices publicly.
- Validate hardware connectivity and a restore in a staging environment.

## 21. Known limitations

- No REST device/area onboarding endpoint exists.
- The frontend custom report date picker is not connected.
- The settings UI is read-only because no settings mutation API exists.
- Login limiting is process-local; multi-worker deployments need a shared edge
  limiter.
- Request body limiting uses declared Content-Length; the reverse proxy must also
  enforce body and connection limits.
- No automated frontend unit-test script is currently defined.

## 22. Hardware-specific TODOs

- Verify the unit/scaling of TMPH accumulated-energy DP17 before using `kWh`.
- Confirm each deployed breaker's supported capability set and configuration DPs.
- Validate supervised control timing/read-back behavior on Library and Admin
  offices breakers before operational use.
- Verify BEVE session behavior, mapping, station/device selection, and time-zone
  handling against the deployed FiveStar inverter after vendor changes.
- Define and secure the production runtime composition/onboarding mechanism.
- Test network loss/recovery, stale thresholds, and polling rates on the actual
  department LAN without hammering either hardware source.
