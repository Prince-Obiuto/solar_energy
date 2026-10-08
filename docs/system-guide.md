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
  apps/core/            settings, authentication, permissions, logging, rate limit
  apps/db/              SQLAlchemy engine and transactional sessions
  apps/integrations/    BEVE and TinyTuya protocol boundaries
  apps/jobs/            collector, health monitor, backup job
  apps/models/          domain and SQLAlchemy models
  apps/realtime/        WebSocket connection/event management
  apps/security/        runtime-secret encryption and external key handling
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
deployment/             Linux VM Compose, Nginx and one-shot operational workflows
```

## 3. Local development instructions

Requirements are Python 3.12-compatible tooling, PostgreSQL, Node.js 24 (or a
version satisfying the checked-in Vite/ESLint engine constraints), and
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

### First-run installation

After applying database migrations, initialize the singleton installation state:

```bash
cd backend
alembic upgrade head
python -m apps.scripts.initialize_setup
```

The command displays a cryptographically generated setup code exactly once;
only its password-grade hash is stored. Keep the code private and use it with
the `/api/v1/setup` flow to create the first administrator. Re-running the
command does not reveal or replace the code. Before setup completion, explicitly
replace a lost code with:

```bash
python -m apps.scripts.initialize_setup --rotate-token
```

`python -m apps.scripts.bootstrap_admin` remains available as the existing
environment-driven recovery/headless administration option. Databases that
already contain users are migrated with the administrator step marked configured;
existing users and normal authentication are unchanged.

Open `/setup` in the React application and enter the one-time code. The wizard
resumes from the backend's authoritative installation state and guides the
operator through these stages:

1. Create the initial administrator.
2. Test and securely save the read-only BEVE/Siseli configuration.
3. Use temporary Tuya Cloud credentials to retrieve candidates, scan the local
   LAN, select breakers, assign friendly names/areas, and verify each device.
4. Review the saved configuration and permanently finalize first-run setup.

Setup codes, passwords, Tuya Cloud credentials, and opaque onboarding sessions
remain only in browser memory and are not written to browser storage. Tuya Cloud
credentials are used ephemerally and are not persisted by the backend. Closing
or reloading the page discards temporary authorization and discovery state, but
completed stages resume from the database after the operator re-enters the
setup code. Finalization performs a local decryption and typed-configuration
preflight; it does not contact BEVE, Tuya Cloud, or physical breakers. A
successful finalization permanently invalidates the setup code and closes every
first-run mutation endpoint.

After finalization, the application shows an activation screen and keeps normal
routes locked. Restart the backend service once. Startup constructs the normal
runtime from authoritative persisted configuration and only then acknowledges
activation, after which unauthenticated users proceed to the normal login page.
If runtime composition fails, activation remains pending and the activation
screen remains available. First-run setup cannot be reopened; future hardware
changes require a separate authenticated administrator configuration workflow.

### Runtime configuration master key

Persistent installation configuration uses an external Fernet master key. Set
`RUNTIME_MASTER_KEY_FILE` to a path outside the source tree, then initialize it
once:

```bash
cd backend
python -m apps.scripts.initialize_runtime_key
```

The command creates parent directories when necessary, writes a new key with
mode `0600` on Linux, and prints only its path. If a valid file already exists,
the command reports that fact and leaves it unchanged. It never rotates or
replaces a key. An absent setting, unreadable/missing key, or malformed existing
key produces an explicit safe error.

Back up the master key separately with access restricted to authorized system
administrators. Encrypted configuration cannot be recovered if this key is
lost. A database backup contains ciphertext, not usable plaintext credentials;
restoration therefore requires both the database and its matching key. Never
commit, log, email, or place `master.key` in a database backup.

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

### Linux VM containers

Phase 8 adds the [Compose deployment workflow](../deployment/README.md) for an
Ubuntu Server VM on Proxmox: PostgreSQL, a single backend worker/collector and
Nginx serving the React build. Nginx redirects TCP 80 to TLS on TCP 443 and
proxies REST/WebSocket traffic to loopback FastAPI. Backend and Nginx use host
networking for TinyTuya LAN discovery; FastAPI and PostgreSQL remain
loopback-only. PostgreSQL, certificate, runtime-key, backup and secret paths
remain outside container layers.

The verified `energy/siseli` source is now tracked with its upstream MIT license
and provenance record, so clean source clones contain the exact reader used by
the backend image. Real onboarding requires valid HTTPS, a matching certificate,
Docker runtime validation, and the live LAN checklist in the deployment guide.

## 6. Environment variables

Backend variables are documented with safe placeholders in
`backend/.env.example`:

- Application: `APP_NAME`, `APP_ENV`, `APP_VERSION`, `API_V1_PREFIX`.
- HTTP security: `CORS_ORIGINS`, `ALLOWED_HOSTS`, `MAX_REQUEST_BODY_BYTES`,
  `LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS`, `LOG_LEVEL`.
- Database/auth: `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`,
  `ACCESS_TOKEN_EXPIRE_MINUTES`, initial-admin values. `RUNTIME_MASTER_KEY_FILE`
  points to the separate runtime-secret encryption key; relative paths resolve
  from `backend/`, while absolute paths support production secret mounts.
- BEVE/Siseli: username, password, station/device identifiers, time zone and
  timeout. The `siseli` package owns vendor authentication and request signing;
  application IDs/secrets are not application configuration.
- TinyTuya: `TUYA_DEVICE_FILE`, local socket timeout, polling interval, control
  verification delay, onboarding-session TTL/count, and bounded scan retry.
  Production onboarding encrypts the selected local-device document; the
  ignored wizard-generated file remains a development fallback.
- Collection: independent BEVE/Tuya intervals, persistence interval, retry,
  stale, WebSocket and health-monitor timings. `ENERGY_MAX_INTEGRATION_GAP_SECONDS`
  bounds output-power integration so missing cloud intervals are not treated as
  continuously measured load.
- Alerts: optional electrical threshold values. Blank means disabled.
- Backup: primary/secondary destination, retention, command and timeout.

Frontend variables are in `frontend/.env.example`: REST base, optional absolute
WebSocket URL, and the display stale threshold. Production JWT and credential
values must never use repository defaults.

## 7. PostgreSQL setup

Create a dedicated database and least-privilege application account using local
department policy. Put its URL only in the protected backend environment file.
The schema stores areas/devices, normalized telemetry, users, control/system
events, alerts, backup history, and bounded runtime configuration. Hardware
secrets are not Device columns. Runtime secret rows contain authenticated
Fernet ciphertext; non-secret rows contain compact JSON-serialized values.

Runtime configuration is split into `beve`, `tuya_cloud`, `tuya_devices`, and
`system` namespaces with a unique `(namespace, key)` constraint. Known sensitive
keys—including BEVE username/password, Tuya access credentials, and local device
keys—cannot be written through the service as plaintext. Configuration changes
create `installation.configuration` audit events containing only namespace,
changed key name, action, secret classification, and optional actor identifier.
Values and ciphertext are excluded.
The Tuya Cloud namespace remains available to the generic configuration layer,
but first-run onboarding deliberately writes no Cloud credential rows.

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

### BEVE first-run setup

After the administrator step, the operator supplies only the four values the
production integration requires: username, password, station ID, and device ID.
The base URL, `Africa/Lagos` timezone, and timeout continue to use the existing
deployment settings and are not duplicated in the request.

`POST /api/v1/setup/beve/test` accepts the setup code and those four values. It
uses a short-lived instance of the same read-only `BeveClient`,
`InverterAdapter`, and mapper used in production. Success requires login,
station/device matching, a valid telemetry envelope, successful normalized
mapping, and at least one supported telemetry signal. A zero output/PV value,
`PV Not Connected`, `Battery Mode`, or `No Charging` is valid operating data and
does not fail verification. The response contains only a small normalized
summary; credentials, identifiers, tokens, sessions, and raw vendor data are
never returned.

`POST /api/v1/setup/beve` repeats the test before writing, encrypts username and
password through the runtime-configuration service, stores station/device IDs
as non-secret JSON values, reads the persisted values back, and verifies them a
second time. A savepoint restores any previous known-good configuration when
the final check fails. Only a successful final check sets
`beve_configured=true`, advancing `GET /api/v1/setup/status` from `beve` to
`tuya`. Both endpoints require an initialized, incomplete setup with an initial
administrator and valid setup code. Repeated failures are bounded by the
existing setup rate limiter.

Failures use safe categories: `authentication_failed`, `device_not_found`,
`network_error`, `timeout`, `malformed_response`, `configuration_invalid`, or
`vendor_error`. Audit events record only the operation and result category.

Configuration changes are activated by a normal backend restart. Runtime
composition then resolves PostgreSQL values before environment fallbacks and
creates its usual single collector. The setup endpoints never create a
collector and do not hot-swap one, avoiding duplicate hardware polling. Existing
environment-only development remains supported, but it is never copied into
PostgreSQL implicitly; production onboarding requires explicit entry and
verification.

## 10. Tuya breaker configuration

The verified device is WIFl Smart Meter Pro / TMPH, category `znjdq`, protocol
3.5. First-run onboarding uses TinyTuya 1.20.0's Python APIs directly; it never
spawns or parses the TinyTuya CLI. `POST /api/v1/setup/tuya/cloud` accepts the
setup code, region, Access ID, Access Secret, and optional anchor Device ID. It
calls `Cloud.getdevices()` and immediately clears/discards the Cloud object's
credentials after extracting device IDs and local keys into a bounded,
process-local onboarding session. Cloud credentials, tokens, raw responses, and
local keys are never returned or persisted.

The opaque onboarding session lasts 15 minutes by default and is bounded to 10
concurrent sessions. `POST /api/v1/setup/tuya/scan` explicitly invokes
`deviceScan(..., poll=False, byID=True)` with a bounded scan duration. Cloud and
LAN records are matched only by exact Tuya Device ID. An unmatched cloud device
gets at most one bounded `find_device(dev_id=...)` fallback attempt; names and IP
addresses are never identities. If keyed candidates remain unmatched and
`TUYA_DISCOVERY_NETWORKS` is configured, `scanner.devices` then force-scans only
those approved CIDRs with the temporary cloud IDs/keys supplied in memory,
`discover=False`, `verbose=False`, `poll=False`, and exact-ID filtering. No
`devices.json` or snapshot is written. Vendor scan debug logging is suppressed
for the scan thread because it can contain keys. Results must have an exact
candidate ID and an address inside an approved CIDR. The existing scan response
and safe error categories apply to both discovery paths.

`TUYA_DISCOVERY_NETWORKS` is a comma-separated list of explicit RFC1918 IPv4
CIDRs. Each must be /24 or narrower, with at most 8 CIDRs and 256 total addresses
(counting network/broadcast addresses). Invalid, public, loopback, link-local,
multicast, IPv6, and overly broad ranges fail configuration validation. Blank
disables routed scanning. The production template configures `10.10.20.0/27`;
operators must approve their own networks. UDP broadcasts do not cross routed
subnets; the VM needs routed TCP 6668 access to the approved IoT networks.
Concurrent scans are rejected rather than overlapped. Runtime still uses direct
TinyTuya TCP after encrypted setup; these CIDRs apply only to onboarding.

`POST /api/v1/setup/tuya/devices` accepts one or more opaque candidate refs with
operator-assigned friendly names and areas. Each selection must have a cloud
local key, a discovered LAN address, and a reported protocol version. The same
production `TuyaClient`, `TuyaBreakerAdapter`, and mapper then perform a status
read. Relay ON, relay OFF, and legitimate zero telemetry all pass; the setup
path exposes no switching or datapoint-write call.

After every selection verifies, the complete local-device document is encrypted
as one `tuya_devices/devices` runtime setting. A savepoint protects any previous
known-good document during persistence/read-back validation. Only then are
`tuya_configured` and `devices_verified` set, advancing setup to `confirm`. The
opaque session is destroyed immediately. Runtime activation is restart-based so
the application creates only its normal single collector.

At startup encrypted persisted devices take precedence. If no persisted device
document exists, `TUYA_DEVICE_FILE`/`devices.json` remains the development and
backward-compatible fallback and is never migrated automatically. Every valid
entry constructs an independent local-LAN client and breaker registration.

`devices.json` contains local keys. It, `snapshot.json`, `tinytuya.json`,
`tuya-raw.json`, and `.env` are recursively ignored and must never be committed,
logged, returned by REST, or published by WebSocket. Normal monitoring uses only
local TinyTuya communication and does not consume `tinytuya.json` cloud
credentials. Configure DHCP reservations/static leases for deployed breakers.
The setup IP is an initial address, not identity; the existing client can recover
a changed address by exact Device ID after a failed connection and never scans
continuously.

Only verified control DPs 1, 9, 38, 40 and 41 are allowlisted. Calibration DPs
22–25 and unknown DPs 21, 26 and 42 cannot be written through the adapter.

## 11. Device onboarding

1. Enter Tuya Cloud credentials locally during the token-protected setup flow.
2. Run the explicit LAN scan and select only exact-ID matched breaker candidates.
3. Assign printable friendly names/areas and complete read-only local verification.
4. Restart the backend after encrypted persistence. Missing Area and Device rows are provisioned
   transactionally and idempotently before collection starts.
5. Customize friendly names/areas in the database if required; existing values
   are preferred on subsequent starts and are not overwritten.
6. Test read-back verification and audit persistence under supervision before
   exercising ADMIN controls.

FastAPI lifespan composes the resolved read-only BEVE client, every
configured TinyTuya breaker, normalized services, persistence adapter, event
publisher and collector. Development can start without hardware configuration;
partially supplied BEVE settings fail with a sanitized configuration error.

The runtime-configuration provider resolves typed BEVE values and the encrypted
Tuya device document. Persisted Tuya devices override `devices.json`; when no
persisted document exists the file remains the fallback. BEVE fields retain
per-field `persisted`, `environment`, or `missing` source metadata. A persisted
value wins; an absent row falls back to the existing environment setting. A
persisted encrypted row that cannot be decrypted fails explicitly and never
falls back to an environment credential or gets overwritten. When the external
master-key path is configured, `build_application_runtime()` uses this provider
at startup. No secrets are copied to PostgreSQL automatically.

The collector uses monotonic start-to-start scheduling, bounded retries, and a
per-source async lock. Breaker socket access also has a shared per-device lock:
collector polling and a command's complete read/write/read-back sequence cannot
overlap for the same breaker, while different breakers remain independent.
Monitoring routes consume collector state first and persisted state second;
they never initiate TinyTuya traffic. WebSocket-triggered frontend refreshes are
debounced/coalesced so bursts result in at most one request in flight.

## 12. REST endpoint inventory

Public: `GET /`, `GET /health`, `GET /api/v1/health`, `POST /auth/login`,
`POST /auth/logout`, `GET /setup/status`, `POST /setup/verify`, and the
one-time-token-protected `POST /setup/administrator`, `POST /setup/beve/test`,
`POST /setup/beve`, `POST /setup/tuya/cloud`, `POST /setup/tuya/scan`, and
`POST /setup/tuya/devices` under `/api/v1`. Tuya setup additionally requires an
initialized, admin-configured, BEVE-configured, incomplete installation.

Authenticated routes under `/api/v1`:

- Auth: `GET /auth/me`.
- Dashboard: `GET /dashboard`, `/dashboard/summary`, `/dashboard/areas`.
- Devices/energy: `GET /devices`, `/devices/{id}`, `/energy`,
  `/energy/latest`, `/energy/history`, and aggregate `/energy/summary?from=YYYY-MM-DD&to=YYYY-MM-DD`.
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

The authenticated Energy page uses `/energy/summary` and Africa/Lagos calendar
days. Solar generation is the maximum verified daily cumulative Siseli value;
system consumption is trapezoidal integration of persisted inverter output
power with oversized gaps excluded. Grid imported energy remains unavailable
until the import/export direction of Siseli `GridPower` is verified; raw grid
power is not relabeled by assumption. Null means unavailable, while a measured
zero remains zero.

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

- Build the versioned 1.0.0 source archive with `python3 scripts/build_release.py`,
  verify `dist/SHA256SUMS`, and run the extracted `install.sh` only on a fresh
  supported Ubuntu Server VM. See the root README and deployment guide.
- The installer requires a real hostname and matching certificate/key, checks
  release contents, starts Compose services, and prints the one-time setup code
  directly to the terminal; it never collects BEVE/Tuya credentials.
- Use the tracked Compose deployment guide with a valid mounted certificate and
  HTTPS same-origin REST/WebSocket proxy. TCP 80 redirects to 443.
- Set `APP_ENV=production`, external random JWT/database secret files, explicit
  `ALLOWED_HOSTS`, and restricted `/opt/solar-energy/{config,secrets,certs,backups}`
  permissions. Wildcard hosts are rejected outside development.
- Run `deployment/scripts/preflight.sh`, back up PostgreSQL, then run Alembic
  before starting an upgraded backend.
- Install the supplied nightly systemd backup timer only after reviewing it.
- Docker limits long-running JSON logs to five 10 MiB files; monitor disk space,
  backup inspection/restores, app health and certificate expiry.
- Do not expose FastAPI or PostgreSQL on the LAN. Restrict TinyTuya UDP/TCP UFW
  rules to the actual breaker subnet and preserve BEVE/Tuya Cloud egress.
- Validate HTTPS, a disposable restore, and read-only hardware monitoring before
  attempting any supervised breaker-control acceptance test.

## 21. Known limitations

- The frontend custom report date picker is not connected.
- The settings UI is read-only because no settings mutation API exists.
- Login limiting is process-local; multi-worker deployments need a shared edge
  limiter.
- Request body limiting uses declared Content-Length; the reverse proxy must also
  enforce body and connection limits.
- No automated frontend unit-test script is currently defined.
- BEVE setup activation is restart-based; no live collector hot-swap is exposed.
- Tuya onboarding sessions are process-local; keep setup traffic on one backend
  instance. A later container deployment must retain host-LAN UDP discovery and
  local breaker connectivity.

## 22. Hardware-specific TODOs

- Verify the unit/scaling of TMPH accumulated-energy DP17 before using `kWh`.
- Confirm each deployed breaker's supported capability set and configuration DPs.
- Validate supervised control timing/read-back behavior on Library and Admin
  offices breakers before operational use.
- Verify BEVE session behavior, mapping, station/device selection, and time-zone
  handling against the deployed FiveStar inverter after vendor changes.
- Run Tuya onboarding against the department account/LAN and verify all intended
  breakers are exact-ID matches before Phase 5 UI work.
- Test network loss/recovery, stale thresholds, and polling rates on the actual
  department LAN without hammering either hardware source.
