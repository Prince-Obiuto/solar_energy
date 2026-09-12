# Linux VM container deployment — Phase 7

This Compose deployment targets Docker Engine and Compose on an Ubuntu Server
VM on Proxmox. Run commands from the repository root unless indicated.
The existing Python/Vite development workflow remains available.

**This phase serves HTTP for container validation. Do not perform real production
credential onboarding over plain HTTP.** Phase 8 must provide HTTPS before live
BEVE/Tuya onboarding. Production authentication already uses Secure cookies;
browser login/WebSocket sessions on a plain HTTP LAN IP cannot use those cookies.
Keep that security policy enabled. Validate routing and unauthenticated behavior
now; validate authenticated browser behavior after HTTPS is configured.

## Images and prerequisites

- Backend: official `python:3.12-slim-trixie`, Python virtual environment built
  from existing requirements, PostgreSQL 17 client for the existing backup job,
  CA certificates and timezone data. The normal process runs as UID/GID 10001.
- Frontend: official `node:24-bookworm-slim` with `npm ci` and Vite production
  build, then official `nginx:stable-alpine` with only the built assets/config.
  Node 24 satisfies the checked-in Vite 8 and ESLint 10 engine requirements.
- Database: official `postgres:17-bookworm`, with project-scoped named volume
  `<project>_postgres_data`. PostgreSQL 17 is supported through November 2029
  ([version policy](https://www.postgresql.org/support/versioning/)). The existing
  schema uses no newer-major-specific feature. Never change the major against
  an existing data volume without a reviewed upgrade procedure.
- Current migration head is `20260912_10`.
- Compose must support health/completion dependencies and bind
  `create_host_path: false`. Docker Engine on Linux is required for this host
  networking arrangement. Do not scale backend workers or replicas: collector,
  WebSocket and temporary onboarding state are currently process-local.

The proven `energy/siseli/{__init__.py,api.py,const.py}` library must exist in
the build checkout. It is present in the current local tree but `/energy/` is
Git-ignored. The backend Dockerfile copies only those three library files and
checks that `SolarOfThingsAPI` imports without contacting the cloud. A fresh
clone must receive the same reviewed library from the maintainer before a build;
do not substitute an unrelated PyPI package or copy the whole hardware folder.
No vendor authentication code is reimplemented or changed by this deployment.
Establish a reviewed redistributable/versioned library artifact before installer
packaging. Library protocol constants remain internal to that dependency.

Both Dockerfiles intentionally use the **repository root context**. The root
`.dockerignore` is authoritative and allowlists application source, migrations,
frontend assets, Nginx configuration, requirements and those exact library files.
It excludes Git history, local environment files, virtual environments, test
databases, captures, dumps and hardware secrets. Per-application `.dockerignore`
files also protect future application-local build contexts. Never use an
unfiltered copy of the repository or `COPY . .` in a runtime image.

## Configuration and external secrets

```bash
cp deployment/.env.example deployment/.env
```

Edit only non-secret values. `ALLOWED_HOSTS` must contain `localhost,127.0.0.1`
and the actual VM hostname/LAN IP (and future domain), without schemes or ports.
Do not use `*`. No frontend rebuild is needed when the hostname/IP changes.
REST uses `/api/v1`; WebSocket uses browser-derived `ws[s]://<origin>/api/v1/ws/energy`.
Vite's existing `/api` proxy continues to serve local development.

Required Compose variables: `POSTGRES_DB`, `POSTGRES_USER`, `ALLOWED_HOSTS`,
`CONFIG_DIRECTORY`, `BACKUP_DIRECTORY`, `POSTGRES_PASSWORD_FILE`,
`JWT_SECRET_KEY_FILE`. `POSTGRES_PORT` defaults to 5432; choose an unused port
for disposable tests. Project name and polling intervals are configurable in
the template. Other application settings retain their existing defaults;
add deliberate non-secret environment overrides under the shared backend
environment anchor if required. Hardware configuration comes from the wizard.

Compose fixes `APP_ENV=production`, API prefix `/api/v1`, and application time
zone `Africa/Lagos`. Database sessions/storage remain UTC. `CORS_ORIGINS` is
whitespace because the current settings ignore empty environment values;
its parsed origin list is empty, appropriate for this same-origin deployment.

On the VM, prepare external directories (administrative privileges required):

```bash
sudo install -d -m 0700 -o 10001 -g 10001 /opt/solar-energy/config
sudo install -d -m 0700 -o 10001 -g 10001 /opt/solar-energy/backups
sudo install -d -m 0700 -o root -g root /opt/solar-energy/secrets
```

Create separate cryptographically random database and JWT secret files without
printing values or replacing existing files. For example, run this once on the
VM; an existing file causes an error and is preserved:

```bash
sudo python3 - <<'PY'
import os
import secrets
from pathlib import Path
directory = Path('/opt/solar-energy/secrets')
for name in ('postgres_password', 'jwt_secret'):
    descriptor = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(secrets.token_urlsafe(48) + '\n')
    os.chmod(directory / name, 0o444)
PY
```

The host secrets directory is root-only (`0700`). Its files are `0444` so the
different backend/PostgreSQL users can read the specific read-only secret mounts
granted to them. Host users cannot traverse the directory. Local Compose file
secrets are bind mounts; do not assume `uid/gid/mode` secret options remap host
ownership ([Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/)).
Run deployment commands as an operator with Docker and protected-file access,
usually via `sudo docker compose` on this VM. Docker access is privileged access.

The container entrypoint reads mounted files, safely URL-encodes the database
credentials, sets `DATABASE_URL` and `JWT_SECRET_KEY` only in the child process
environment, and execs the requested command. It never prints them. Compose
configuration/image metadata contains paths rather than password values.
Do not dump process environments. PostgreSQL uses `POSTGRES_PASSWORD_FILE`.
Changing this file alone does not rotate a password in an existing database.

The separate runtime encryption key lives at
`/opt/solar-energy/config/master.key`, mounted as
`/run/solar-config/master.key`. It is created as UID/GID 10001, mode `0600`.
Normal services have a read-only config mount; only the explicit key helper can
write it. Back up this key separately from the database with restricted access.
Never rotate it casually: losing the matching key loses encrypted hardware
configuration. The persistent backup directory is writable only by the backend
user; PostgreSQL backup data belongs there, not in container layers. An optional
secondary backup destination can be added as a distinct mount and existing
`BACKUP_SECONDARY_DESTINATION` setting later.

## Build, initialize and start

These are deliberate operations, not an installer. With a configured template,
external paths and the reviewed Siseli library present:

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml config --quiet
docker compose --env-file deployment/.env -f deployment/compose.yaml build
docker compose --env-file deployment/.env -f deployment/compose.yaml run --rm --no-deps runtime-key-init
docker compose --env-file deployment/.env -f deployment/compose.yaml up -d --wait db
docker compose --env-file deployment/.env -f deployment/compose.yaml run --rm migrate
docker compose --env-file deployment/.env -f deployment/compose.yaml run --rm --no-deps migrate alembic current
docker compose --env-file deployment/.env -f deployment/compose.yaml run --rm setup-init
docker compose --env-file deployment/.env -f deployment/compose.yaml up -d --wait backend web
```

`runtime-key-init` preserves an existing valid key and prints only its path.
`setup-init` prints the one-time setup code to the attached operator terminal;
the `none` logging driver and `--rm` avoid retaining it in Docker logs/containers.
Do not redirect, capture, paste, or record the setup code. This helper is under
the operations profile and never runs during ordinary restarts. Initialization
creates no administrator and contacts no hardware. During Phase 7, stop at the
initial setup screen; defer real credential onboarding until HTTPS exists.

`migrate` uses the same backend image and waits for database health. Normal
`up` also runs its separate migration dependency and requires successful exit
before backend starts; a failed migration stops that startup path. Explicit
`run --rm migrate` may be followed by another harmless `upgrade head` during
`up`. Never run automatic downgrades. On image updates, explicitly rerun
migrations before recreating services; `restart` does not apply migrations.

Normal backend startup only starts the existing application: one Uvicorn worker,
one collector, no reload, key generation, setup initialization, scan or admin
creation in the entrypoint. Phase 6 activation works through the ordinary restart
after successful finalization (when real HTTPS onboarding becomes available):

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml restart backend
docker compose --env-file deployment/.env -f deployment/compose.yaml ps -a
```

Use Check Activation in the browser. Persisted configuration is authoritative;
failed runtime composition keeps activation pending. HTTP process health alone
does not assert that hardware is reachable or activation succeeded.

## Network, health and permissions

| Listener | Interface | Purpose |
|---|---|---|
| TCP 80 | all host IPv4/IPv6 interfaces | Nginx SPA, REST, WebSocket |
| TCP 8000 | 127.0.0.1 only | FastAPI, no Docker port publishing |
| TCP configured DB port (5432 default) | 127.0.0.1 only | mapped PostgreSQL |

Ensure those ports are free on the VM; the existing local developer Uvicorn may
already occupy 8000. Backend and web use `network_mode: host`; PostgreSQL stays
on the Compose bridge with a loopback-only publication. No service is privileged.
Host networking preserves TinyTuya UDP broadcast discovery and LAN TCP access,
including dynamic connections, without speculative port forwarding. See
[Docker networking](https://docs.docker.com/compose/how-tos/networking/).
Host firewall, VLANs, VM NIC/bridge and Wi-Fi client isolation must still allow
the required traffic. Outbound DNS/HTTPS for BEVE/Siseli and temporary Tuya Cloud
remains available. This phase makes no claim of a successful live LAN scan.

Nginx keeps full `/api/v1` paths, forwards the original host/client IP/protocol,
and supports Upgrade/Connection for `/api/v1/ws/energy`. It discards untrusted
incoming forwarding chains; Uvicorn trusts proxy headers only from loopback.
Ordinary API reads have 60-second timeouts; setup requests have 240 seconds to
cover bounded scanning/verification; WebSockets have 90-second idle timeouts
against the existing 20-second heartbeat. SPA `try_files` fallback supports
refresh on `/setup`, `/login`, `/energy`, and other React routes. The health URL
`/healthz` is Nginx-local; `/api/v1/health` goes through FastAPI.

Backend health uses Python urllib on `/health` and makes no hardware calls.
Nginx health uses its static `/healthz`; PostgreSQL uses `pg_isready` without a
password argument. `db`, `backend`, and `web` restart `unless-stopped`; helpers
never auto-restart. Backend waits for DB health and migration completion, web
waits for backend health ([dependency conditions](https://docs.docker.com/reference/compose-file/services/)).
An unhealthy state is diagnostic; Docker does not restart a still-running
unhealthy container automatically.

Backend drops all capabilities, uses `no-new-privileges`, a read-only root and
bounded temporary storage. UDP/TCP requires no privileged mode. Nginx retains
only port-binding, ownership, and worker UID/GID transition capabilities: its
root master binds port 80 and workers run as nginx. It has a read-only root with
writable cache/PID tmpfs. PostgreSQL retains the official image initialization
permissions and writable data volume; blindly making it read-only would break
database startup. Logs go to stdout/stderr; proxy logs exclude query strings,
cookies, headers and bodies. Normal app access logging uses the existing safe
application middleware. Docker log rotation is left for the operations phase.

`devices.json` is never baked into an image and is not needed for production
onboarding. If maintaining an existing development fallback, place the reviewed
file in the protected config directory, mode `0600`, owner 10001. The existing
read-only directory mount makes `/run/solar-config/devices.json` available;
finalized setup still requires persisted configuration and does not accept that
fallback as activation proof.

## Smoke checks and operations

Use a separate `COMPOSE_PROJECT_NAME`, unused database port, and new external
directories for disposable validation. Never point tests at the valuable
development database/config. Inspect the rendered configuration with `config
--quiet` before starting; it validates schema without printing configuration.

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml ps -a
curl --fail http://127.0.0.1/healthz
curl --fail http://127.0.0.1/api/v1/health
curl --fail http://127.0.0.1/api/v1/setup/status
curl --fail --output /dev/null http://127.0.0.1/setup
curl --fail --output /dev/null http://127.0.0.1/login
curl --fail --output /dev/null http://127.0.0.1/energy
docker compose --env-file deployment/.env -f deployment/compose.yaml exec web nginx -t
docker compose --env-file deployment/.env -f deployment/compose.yaml logs --tail 100 backend web
docker compose --env-file deployment/.env -f deployment/compose.yaml stop
docker compose --env-file deployment/.env -f deployment/compose.yaml down
```

`down` preserves named volumes and host directories. Do not add `--volumes` for
an installation you intend to keep. Containerized backup/restore should use
`pg_dump`/`pg_restore`, not copies of a live database directory. The existing
backup command is available through `run --rm --no-deps backend python -m
apps.scripts.run_backup`; configure scheduling separately.

Before setup initialization, status must show setup required and not initialized.
After the one-shot initialization, it must show initialized and the administrator
step. An unauthenticated WebSocket upgrade must be denied by the backend; a 403
confirms its authorization boundary, but is not proof of an authenticated 101
upgrade. After Phase 8 HTTPS, validate a real authenticated browser WebSocket,
normal login, setup completion/restart, dashboard and TinyTuya read-only LAN
discovery. Do not test breaker switching as a deployment smoke check.

## Validation recorded in this working session

Docker CLI/Compose were inspected. The Docker daemon socket is not accessible
to the session user, and non-interactive sudo requires a password. Container
builds, PostgreSQL migrations inside Docker, Nginx runtime validation and live
container smoke tests must be executed on an accessible Docker host before
calling this deployment validated. No real BEVE/Tuya onboarding was performed.
The final task report records local tests and Compose schema validation results.

Recorded validation for this implementation:

- Focused container-entrypoint/setup-finalization/runtime tests: 40 passed.
- Full backend suite on a fresh migrated disposable SQLite database: 298 passed,
  4 existing dependency/datetime deprecation warnings.
- Frontend `npm run lint` and `npm run build`: passed, 712 modules built.
- `docker compose --env-file deployment/.env.example -f deployment/compose.yaml
  config --quiet`: passed (Compose 5.3.1).
- `docker compose ... build`: attempted, blocked by Docker socket permission
  denial before image build. These results do not establish image/runtime health.
- `git diff --check`: passed.
