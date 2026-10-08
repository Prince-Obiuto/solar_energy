# Linux VM container deployment — Phase 8

This Compose deployment targets Docker Engine and Compose on an Ubuntu Server
VM on Proxmox. Run commands from the repository root unless indicated.
The existing Python/Vite development workflow remains available.

This deployment requires a valid certificate before administrators enter setup,
BEVE, Tuya, or login credentials. HTTP only redirects to HTTPS. The application
keeps Secure, HttpOnly, SameSite=Lax authentication cookies; it does not weaken
them for a plain-HTTP LAN test.

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

The proven reader is now a tracked vendor snapshot at `energy/siseli`, with its
MIT license and exact provenance/hashes in `energy/siseli/UPSTREAM.md`. It is
derived from Conexo-Casa's public Solar of Things Home Assistant integration;
the retained source snapshot is the locally verified reader rather than an
unreviewed build-time download or an unrelated PyPI package. The backend image
copies only this snapshot and verifies that `SolarOfThingsAPI` imports without
contacting the cloud. No vendor authentication code is changed by deployment.

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
`CONFIG_DIRECTORY`, `BACKUP_DIRECTORY`, `CERTIFICATE_DIRECTORY`,
`POSTGRES_PASSWORD_FILE`, `JWT_SECRET_KEY_FILE`, and `APP_HOSTNAME`.
`POSTGRES_PORT` defaults to 5432; choose an unused port
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
sudo install -d -m 0750 -o root -g root /opt/solar-energy/certs
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

Install the institutionally supplied certificate as
`/opt/solar-energy/certs/fullchain.pem` and private key as
`/opt/solar-energy/certs/privkey.pem`. The web service mounts this directory
read-only at `/etc/nginx/certs`; neither file is copied into an image or Git.
The private key should be root-owned and mode `0600`; the certificate may be
root-owned and mode `0644`. `APP_HOSTNAME` must match a certificate SAN. A
certificate for a hostname does not validate when users browse a bare LAN IP,
unless that IP is explicitly in its SAN. HSTS is enabled only in the HTTPS
production configuration, so do not point this Compose configuration at a
temporary/self-signed laboratory certificate. ACME can be added later if the
chosen hostname is publicly resolvable and its inbound validation path is
approved; this phase deliberately does not add an untested Certbot service.

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
external paths, valid certificate, and the tracked Siseli snapshot present:

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml config --quiet
deployment/scripts/preflight.sh
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

## HTTPS, network, firewall and permissions

| Listener | Interface | Purpose |
|---|---|---|
| TCP 80 | all host IPv4/IPv6 interfaces | Nginx HTTPS redirect only |
| TCP 443 | all host IPv4/IPv6 interfaces | Nginx TLS SPA, REST, WebSocket |
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

Nginx redirects `http://<host>/…` with HTTP 308 to `https://<host>/…`, then
keeps full `/api/v1` paths and forwards the validated host/client IP/protocol.
It sets `X-Forwarded-Proto: https`; Uvicorn is already configured to trust proxy
headers only from loopback. FastAPI's `ALLOWED_HOSTS` remains the authority for
accepted hostnames and rejects wildcards outside development. The Nginx default
server does not replace that application boundary. The proxy supports
Upgrade/Connection for `/api/v1/ws/energy` and discards untrusted incoming
forwarding chains.
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
application middleware. Docker JSON logs for database, backend and web are
bounded to five 10 MiB files each. Setup initialization keeps the `none` driver
because it prints a one-time code only to the attached operator terminal.

`devices.json` is never baked into an image and is not needed for production
onboarding. If maintaining an existing development fallback, place the reviewed
file in the protected config directory, mode `0600`, owner 10001. The existing
read-only directory mount makes `/run/solar-config/devices.json` available;
finalized setup still requires persisted configuration and does not accept that
fallback as activation proof.

### UFW policy

Do not apply firewall changes from Compose or application startup. First confirm
the management subnet and active SSH port so SSH is not locked out. For an SSH
service on port 22 and a department network where the TinyTuya devices use
`10.20.30.0/24`, an operator may adapt these commands:

```bash
sudo ufw allow from <management-subnet> to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow from 10.20.30.0/24 to any port 6666 proto udp
sudo ufw allow from 10.20.30.0/24 to any port 6667 proto udp
sudo ufw allow from 10.20.30.0/24 to any port 7000 proto udp
sudo ufw allow out to 10.20.30.0/24 port 6668 proto tcp
sudo ufw enable
sudo ufw status numbered
```

The ports above come from the installed TinyTuya 1.20.0 source: discovery
listens on UDP 6666, 6667 and 7000; protocol 3.5 discovery sends to UDP 7000;
local device commands/status use TCP 6668. Host networking allows this traffic
without privileged mode. Keep the scope restricted to the actual breaker subnet
and preserve outbound DNS/HTTPS for BEVE/Siseli and temporary Tuya Cloud
onboarding. Never allow PostgreSQL or FastAPI through UFW from the LAN.

## Smoke checks and operations

Use a separate `COMPOSE_PROJECT_NAME`, unused database port, and new external
directories for disposable validation. Never point tests at the valuable
development database/config. Inspect the rendered configuration with `config
--quiet` before starting; it validates schema without printing configuration.

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml ps -a
curl -I http://"$APP_HOSTNAME"/
curl --fail --cacert /opt/solar-energy/certs/fullchain.pem "https://$APP_HOSTNAME/healthz"
curl --fail --cacert /opt/solar-energy/certs/fullchain.pem "https://$APP_HOSTNAME/api/v1/health"
curl --fail --cacert /opt/solar-energy/certs/fullchain.pem "https://$APP_HOSTNAME/api/v1/setup/status"
curl --fail --output /dev/null "https://$APP_HOSTNAME/setup"
curl --fail --output /dev/null "https://$APP_HOSTNAME/login"
curl --fail --output /dev/null "https://$APP_HOSTNAME/energy"
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

## Backups, retention and restore

Use `deployment/scripts/backup.sh` for the deployment-level database archive.
It runs `pg_dump` inside the PostgreSQL container, writes a custom compressed
archive to a same-directory `.partial` file, verifies non-zero output, then
atomically renames it to `solar_energy_YYYY-MM-DD_HHMMSS.dump`. It never copies
the live PostgreSQL volume and never passes a password on the command line.
It reads only non-secret database name/user settings from `deployment/.env` and
uses the database container's local authentication.

```bash
cd /opt/solar-energy
deployment/scripts/backup.sh
docker compose --env-file deployment/.env -f deployment/compose.yaml exec -T db \
  pg_restore --list < /opt/solar-energy/backups/solar_energy_<timestamp>.dump
```

Retention is a simple bounded daily policy: `BACKUP_RETENTION_DAYS` defaults to
30. Deletion is limited to one level of the configured backup directory and to
the `solar_energy_*.dump` naming pattern; it never recursively removes a path.
The application-level backup job continues to record backup history and alerts,
but the deployment script is suitable for the system timer below.

A recoverable installation is a set, not merely a dump:

1. the PostgreSQL archive;
2. the matching `/opt/solar-energy/config/master.key`;
3. deployment `.env` and the separately protected PostgreSQL/JWT secret files;
4. `fullchain.pem` and `privkey.pem` unless an institutional certificate system
   manages and backs them up separately.

The database contains encrypted runtime configuration. Without the matching
master key it cannot decrypt saved BEVE/Tuya values; the master key without the
database does not restore users, state, or configuration. Keep at least one
restricted offline copy of the key. Do not email, commit, or include it in a
world-readable archive, and never print it during backup or restore.

Test a restore into a separately named database before relying on it. Stop only
backend/web writers, keep PostgreSQL running, and state the target explicitly:

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml stop backend web
# Create and authorize an explicit non-production restore target according to
# local PostgreSQL policy, then inspect/restore the chosen archive into it:
docker compose --env-file deployment/.env -f deployment/compose.yaml exec -T db \
  pg_restore --clean --if-exists --no-owner --dbname=<explicit-test-database> \
  < /opt/solar-energy/backups/solar_energy_<timestamp>.dump
```

For recovery to the real deployment, restore the same key, certificate and
protected deployment files before starting backend. Run `alembic upgrade head`
after restoring an older archive, then start backend, check activation/login,
and finally start web. Do not overwrite an active production database until the
target, archive, rollback plan, and downtime are explicitly approved.

Install, review, and enable the supplied systemd timer only on the VM:

```bash
sudo install -m 0644 deployment/systemd/solar-energy-backup.service /etc/systemd/system/
sudo install -m 0644 deployment/systemd/solar-energy-backup.timer /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/solar-energy-backup.service /etc/systemd/system/solar-energy-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now solar-energy-backup.timer
sudo systemctl list-timers solar-energy-backup.timer
```

The timer is nightly at 02:00 with a bounded random delay and persists missed
runs. It is not enabled automatically by this repository.

## Reboot, upgrades and recovery

### Routed Tuya discovery patch on an existing installation

The routed discovery and manual-IP onboarding patch needs backend and web image
rebuilds and container recreation. Preserve
the current PostgreSQL volume, `deployment/.env`, and `config/`, `secrets/`,
`certs/`, and `backups/`. Take the existing protected backup before updating.
Copy the reviewed changed backend source and `deployment/compose.yaml` into the
existing installation, preserving that sibling layout. Edit the existing
`deployment/.env` to add/update this non-secret setting (do not replace the file
with the example):

```dotenv
TUYA_DISCOVERY_NETWORKS=10.10.20.0/27
```

This enables force scanning of the approved routed IoT CIDR after ordinary UDP
discovery and exact-ID fallback. If a cloud candidate is still unmatched, setup
can verify its known IPv4 address within the same approved ranges using the
server-held Device ID and local key. This is read-only and does not operate the
relay. Comma-separated RFC1918 IPv4 CIDRs are accepted,
at most 8 ranges, each /24 or narrower, at most 256 total addresses. Blank
disables this fallback. Ensure VM routing and firewall policy permit TCP 6668
to those ranges. The backend uses host networking and receives the setting
through Compose.

On the running server:

```bash
cd /opt/solar-energy
sudo docker compose --env-file deployment/.env -f deployment/compose.yaml config --quiet
sudo docker compose --env-file deployment/.env -f deployment/compose.yaml build backend web
sudo docker compose --env-file deployment/.env -f deployment/compose.yaml up -d --no-deps --wait backend web
sudo docker compose --env-file deployment/.env -f deployment/compose.yaml exec -T backend \
  python -c 'from apps.core.config import settings; print(settings.tuya_discovery_networks)'
sudo docker compose --env-file deployment/.env -f deployment/compose.yaml ps
```

No schema changes are included. Do not rerun `install.sh`, database initialization,
`runtime-key-init`, or `setup-init`; keep the existing secrets and master key.
`restart backend` alone would not pick up a rebuilt image or changed environment.
Verify HTTPS `/api/v1/health` using the current trusted certificate/hostname.
Container recreation clears temporary onboarding sessions: re-enter Tuya Cloud
credentials in the existing setup wizard, scan again, and enter a Known device
IP for each unmatched cloud candidate. A successful read adds it to the normal
selection list; select breakers and run the existing read-only verification.
Confirm all expected breakers are verified before final encrypted persistence.
No relay switching is needed for validation.

Enable Docker once on the VM:

```bash
sudo systemctl enable --now docker
```

After the project has first been started with `docker compose up -d`, the
`unless-stopped` policy restarts database, backend and web when Docker returns
after a reboot. The migration helper is intentionally one-shot; during upgrades
run migrations explicitly before recreating services:

```bash
deployment/scripts/backup.sh
docker compose --env-file deployment/.env -f deployment/compose.yaml build
docker compose --env-file deployment/.env -f deployment/compose.yaml up -d --wait db
docker compose --env-file deployment/.env -f deployment/compose.yaml run --rm migrate
docker compose --env-file deployment/.env -f deployment/compose.yaml up -d --wait backend web
```

Never automatically downgrade. Verify HTTPS health, normal login, dashboard,
inverter source status, breaker status, and WebSocket updates after each upgrade.
A cloud or breaker outage is application-level degraded state, not proof that a
healthy container should be replaced.

| Symptom | Safe diagnosis | Safe recovery |
|---|---|---|
| Backend unhealthy | `docker compose … ps`, `logs --tail 100 backend`, HTTPS `/api/v1/health` | Check DB/migration state and mounted key, then restart backend after correcting the stated issue. |
| PostgreSQL unhealthy | `docker compose … ps`, `logs --tail 100 db`, `exec db pg_isready` | Check volume space and logs; do not delete the volume. |
| Missing master key or corrupt runtime config | Backend log has a safe composition error; setup status shows activation pending | Restore the matching protected key/config from backup; do not regenerate a key over an existing installation. |
| BEVE unavailable | Dashboard marks cloud data stale/unavailable | Check Internet/DNS and Siseli status; keep last known data and do not reconfigure the inverter. |
| Breaker offline | Device/area health reports offline | Check power, LAN/VLAN/Wi-Fi isolation and UDP/TCP firewall scope; use read-only verification first. |
| Finalized setup still pending | `/api/v1/setup/status` reports activation required | Inspect backend composition error, fix persisted configuration/key, then restart backend. |
| TLS certificate missing/expired | Web does not become healthy or browser rejects HTTPS | Install a valid matching certificate/key with restricted permissions, run Nginx validation, then recreate web. |

The live VM acceptance sequence is: verify certificate, open HTTPS `/setup`,
complete administrator and read-only BEVE/Tuya onboarding, match breakers by
exact ID, perform read-only verification, finalize setup, restart backend,
confirm activation, sign in, validate dashboard/device health and WebSocket
updates. Only after monitoring is stable may authorized staff use the existing
read-back/audited breaker-control workflow with connected loads made safe first.

## Versioned release installer

Phase 9 packages only allowlisted application files into
`dist/solar-energy-system-v1.0.0.tar.gz` with `dist/SHA256SUMS`. Build with
`python3 scripts/build_release.py`; verify with `sha256sum -c SHA256SUMS` before
copying or extracting the archive. The archive carries its own
`CONTENT_SHA256SUMS` and manifest, which `install.sh` checks before changing the
host. The installer does not require Git or fetch source code.

On a **fresh** supported Ubuntu Server VM, run `./install.sh --check --hostname
<actual-hostname> --cert <fullchain.pem> --key <privkey.pem>` first, then run
the same command with `sudo` and without `--check`. An operator-supplied valid
certificate and matching private key are required; no self-signed production
mode or automatic ACME flow is included. The installer uses the existing
Phase-8 sibling layout at `/opt/solar-energy/{backend,frontend,energy,deployment}`
because `compose.yaml` builds from `..`. External `config/`, `secrets/`,
`certs/`, `backups/`, and `release/` remain alongside that source.

Installation reuses a healthy Docker Engine/Compose or installs them from the
official Docker Ubuntu apt repository. It builds the reviewed images, starts
PostgreSQL, runs migrations, initializes the runtime master key, starts the
backend and HTTPS web, displays the one-time setup code directly on the
terminal, and enables the Compose and nightly backup systemd units. It refuses
an existing installation or database volume. It does not collect hardware
credentials, finalize the setup wizard, configure UFW, or switch breakers.
Complete `/setup` only over trusted HTTPS.

No automatic upgrade or uninstall script is shipped. For upgrades, preserve
`/opt/solar-energy/{config,secrets,certs,backups}`, back up PostgreSQL and the
master key, verify the new release, build its images, run `alembic upgrade head`
through the migration service, restart backend/web, then validate health and
application behavior. Do not run `install.sh` over an existing installation.
The manual backup/restore, firewall, and recovery instructions above still
apply. Full clean-VM, backup/restore, and hardware acceptance are separate
release gates; a successful source build alone does not prove them.
