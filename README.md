# Smart Renewable Energy Management System

Monitoring and administration software for the Department of Information
Technology. The repository contains a React frontend and a FastAPI backend for
read-only BEVE inverter telemetry, local TinyTuya TMPH breaker telemetry,
historical reporting, alerts, audited breaker control, and operations.

See [docs/system-guide.md](docs/system-guide.md) for architecture, setup,
configuration, endpoint inventories, deployment, security, and known limits.

Quick checks:

```bash
cd backend
python -m pytest

cd ../frontend
npm run lint
npm run build
```

## Release 1.0.0 installer

The release archive is for a **fresh Ubuntu Server 22.04, 24.04, or 26.04 LTS**
VM (amd64 or arm64) with at least 10 GiB free. Its production hostname must
resolve in DNS, and the operator must provide a certificate and matching private
key covering that hostname. Do not enter setup or hardware credentials over HTTP.

Build the reviewed source package on a development machine:

```bash
python3 scripts/build_release.py
cd dist
sha256sum -c SHA256SUMS
```

Copy `solar-energy-system-v1.0.0.tar.gz` and `SHA256SUMS` to the VM. Verify the
checksum there before extracting and running the installer:

```bash
sha256sum -c SHA256SUMS
tar -xzf solar-energy-system-v1.0.0.tar.gz
cd solar-energy-system-v1.0.0
./install.sh --check --hostname energy.example.edu.ng \
  --cert /path/to/fullchain.pem --key /path/to/privkey.pem
sudo ./install.sh --hostname energy.example.edu.ng \
  --cert /path/to/fullchain.pem --key /path/to/privkey.pem
```

Replace the example hostname and paths with real operator-supplied values.
`--postgres-port PORT` selects a different loopback-only PostgreSQL port when
necessary. `--check` is read-only; a failed preflight changes nothing. Ports 80,
443, 8000 and the chosen PostgreSQL port must be free on the fresh VM.

The installer verifies release content and TLS inputs, reuses or installs Docker
Engine with Compose, generates separate database and JWT secrets, builds the
reviewed images from the archive, starts PostgreSQL, migrates the schema,
initializes the external runtime master key, starts FastAPI and Nginx, checks
HTTPS health, enables reboot/backup services, and prints the one-time setup code
directly to the terminal. It does **not** create an administrator, ask for
BEVE/Tuya credentials, switch breakers, configure UFW, or erase an existing
installation. Open the displayed `https://<hostname>/setup` URL and complete
the wizard there. Save the setup code securely; it is not written to a file.

The installation lives under `/opt/solar-energy`: application source and
`deployment/` are siblings, with separate `config/`, `secrets/`, `certs/`,
`backups/`, and `release/` directories. The production backup timer retains
matching database dumps for 30 days by default; the **same** master key and
external secret files must be backed up securely with the database. Run:

```bash
sudo systemctl status solar-energy.service solar-energy-backup.timer
sudo docker compose --env-file /opt/solar-energy/deployment/.env \
  -f /opt/solar-energy/deployment/compose.yaml ps
curl -I https://energy.example.edu.ng/healthz
```

There is no automatic upgrade or uninstall script in v1.0. Back up the database
and external secrets, stage and verify a new release, run migrations, then
restart and verify services as described in
[deployment/README.md](deployment/README.md). Never overwrite an existing
installation with `install.sh`. See [docs/system-guide.md](docs/system-guide.md)
for architecture, recovery, and hardware-specific limitations. Full clean-VM,
backup/restore, and live-hardware acceptance must be completed on the target
infrastructure before declaring production acceptance.
