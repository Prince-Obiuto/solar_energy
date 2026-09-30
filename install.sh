#!/usr/bin/env bash
# Install a reviewed release archive on a fresh Ubuntu Server VM.
# Hardware credentials are entered later through the HTTPS setup wizard.
set -Eeuo pipefail
umask 077

readonly INSTALL_ROOT=/opt/solar-energy
readonly SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly REQUIRED_FREE_KIB=$((10 * 1024 * 1024))

hostname_name=
certificate_source=
key_source=
postgres_port=5432
check_only=false

usage() {
    cat <<'USAGE'
Usage: sudo ./install.sh --hostname NAME --cert FULLCHAIN.PEM --key PRIVKEY.PEM [--postgres-port PORT]
       ./install.sh --check --hostname NAME --cert FULLCHAIN.PEM --key PRIVKEY.PEM [--postgres-port PORT]

Installs a fresh release at /opt/solar-energy. --check is read-only and may run
without sudo. An existing installation is never overwritten. The installer does
not configure the firewall or collect BEVE/Tuya credentials.
USAGE
}

fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
step() { printf '\n==> %s\n' "$1"; }

parse_options() {
    while (($#)); do
        case "$1" in
            --hostname|--cert|--key|--postgres-port)
                (($# >= 2)) || fail "Missing value for $1"
                case "$1" in
                    --hostname) hostname_name=$2 ;;
                    --cert) certificate_source=$2 ;;
                    --key) key_source=$2 ;;
                    --postgres-port) postgres_port=$2 ;;
                esac
                shift 2 ;;
            --check|--preflight-only) check_only=true; shift ;;
            -h|--help) usage; exit 0 ;;
            --version) sed -n '1p' "$SCRIPT_DIR/VERSION"; exit 0 ;;
            *) fail "Unknown option: $1" ;;
        esac
    done
    [[ -n "$hostname_name" && -n "$certificate_source" && -n "$key_source" ]] || {
        usage >&2
        fail 'Hostname, certificate, and private key are required'
    }
}

validate_hostname() {
    local name=$1 label
    local -a labels=()
    [[ ${#name} -le 253 && "$name" == *.* && "$name" != localhost ]] || return 1
    [[ "$name" =~ ^[a-zA-Z0-9.-]+$ ]] || return 1
    IFS=. read -r -a labels <<< "$name"
    for label in "${labels[@]}"; do
        [[ ${#label} -ge 1 && ${#label} -le 63 ]] || return 1
        [[ "$label" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$ ]] || return 1
    done
}

validate_certificate() {
    local cert_pub key_pub key_mode
    [[ -f "$certificate_source" && ! -L "$certificate_source" ]] || fail 'Certificate is not a regular file'
    [[ -f "$key_source" && ! -L "$key_source" ]] || fail 'Private key is not a regular file'
    openssl x509 -in "$certificate_source" -noout >/dev/null 2>&1 || fail 'Certificate cannot be parsed'
    openssl pkey -in "$key_source" -noout -passin pass: >/dev/null 2>&1 || fail 'Private key cannot be parsed without a passphrase'
    openssl x509 -in "$certificate_source" -noout -checkend 86400 >/dev/null 2>&1 || fail 'Certificate expires within 24 hours'
    openssl x509 -in "$certificate_source" -noout -checkhost "$hostname_name" >/dev/null 2>&1 || fail 'Certificate does not cover the supplied hostname'
    openssl verify -purpose sslserver -verify_hostname "$hostname_name" -untrusted "$certificate_source" "$certificate_source" >/dev/null 2>&1 || fail 'Certificate chain is not trusted by this VM'
    cert_pub=$(openssl x509 -in "$certificate_source" -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum)
    key_pub=$(openssl pkey -in "$key_source" -pubout -outform DER -passin pass: 2>/dev/null | sha256sum)
    [[ "$cert_pub" == "$key_pub" ]] || fail 'Certificate and private key do not match'
    key_mode=$(stat -c %a -- "$key_source")
    (( (8#$key_mode & 0004) == 0 )) || fail 'Private key is world-readable'
}

port_available() {
    local port=$1
    [[ -z $(ss -H -ltn "sport = :$port") ]]
}

preflight() {
    local os_id os_version ubuntu_codename architecture available_kib port expected_files actual_files
    [[ $(uname -s) == Linux ]] || fail 'Linux is required'
    # shellcheck disable=SC1091
    source /etc/os-release
    os_id=${ID:-}
    os_version=${VERSION_ID:-}
    ubuntu_codename=${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}
    [[ "$os_id" == ubuntu ]] || fail 'Only Ubuntu Server is supported'
    case "$os_version:$ubuntu_codename" in
        22.04:jammy|24.04:noble|26.04:resolute) ;;
        *) fail 'Supported Ubuntu LTS releases: 22.04, 24.04, 26.04' ;;
    esac
    architecture=$(dpkg --print-architecture)
    [[ "$architecture" == amd64 || "$architecture" == arm64 ]] || fail 'Only amd64 and arm64 are supported'
    for tool in openssl sha256sum stat ss df getent dpkg dpkg-query apt-get systemctl install sed awk find grep mktemp cp mv sleep wc; do
        command -v "$tool" >/dev/null || fail "Required command is missing: $tool"
    done
    validate_hostname "$hostname_name" || fail 'Invalid production hostname'
    [[ "$postgres_port" =~ ^[0-9]+$ ]] && (( postgres_port >= 1 && postgres_port <= 65535 )) || fail 'Invalid PostgreSQL port'
    [[ -f "$SCRIPT_DIR/VERSION" && -f "$SCRIPT_DIR/deployment/compose.yaml" && -f "$SCRIPT_DIR/energy/siseli/api.py" && -f "$SCRIPT_DIR/CONTENT_SHA256SUMS" && -f "$SCRIPT_DIR/release-manifest.json" ]] || fail 'Use an extracted, intact release archive (not the source checkout)'
    (cd -- "$SCRIPT_DIR" && sha256sum --check --status CONTENT_SHA256SUMS) || fail 'Release content checksum verification failed'
    expected_files=$(wc -l < "$SCRIPT_DIR/CONTENT_SHA256SUMS")
    actual_files=$(find "$SCRIPT_DIR" -type f | wc -l)
    (( actual_files == expected_files + 1 )) || fail 'Release archive contains unexpected files'
    [[ -z $(find "$SCRIPT_DIR" -type l -print -quit) ]] || fail 'Release archive contains an unexpected symbolic link'
    [[ $(< "$SCRIPT_DIR/VERSION") =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'Invalid release version'
    validate_certificate
    [[ ! -L "$INSTALL_ROOT" ]] || fail 'Installation root must not be a symlink'
    for unit in solar-energy.service solar-energy-backup.service solar-energy-backup.timer; do
        [[ ! -e "/etc/systemd/system/$unit" ]] || fail "An existing $unit unit was found; refusing a fresh install"
    done
    if [[ -e "$INSTALL_ROOT" ]] && [[ -n $(find "$INSTALL_ROOT" -mindepth 1 -maxdepth 1 -print -quit) ]]; then
        fail 'An installation or other data already exists at /opt/solar-energy; nothing was overwritten'
    fi
    available_kib=$(df -Pk /opt | awk 'NR==2 {print $4}')
    [[ "$available_kib" =~ ^[0-9]+$ ]] && (( available_kib >= REQUIRED_FREE_KIB )) || fail 'At least 10 GiB of free disk space is required'
    for port in 80 443 8000 "$postgres_port"; do
        port_available "$port" || fail "Port $port is occupied; no process was stopped"
    done
    getent ahosts "$hostname_name" >/dev/null || fail 'Production hostname does not resolve in DNS'
    getent ahosts registry-1.docker.io >/dev/null || fail 'Docker registry DNS is unavailable'
    if docker_ready; then
        systemctl cat docker.service >/dev/null 2>&1 || fail 'Docker must provide docker.service for reboot integration'
    else
        getent ahosts download.docker.com >/dev/null || fail 'Docker package repository DNS is unavailable'
        if command -v curl >/dev/null; then
            curl -fsSI --max-time 10 https://download.docker.com/linux/ubuntu/gpg >/dev/null || fail 'Docker package repository is unreachable'
        fi
        for conflict in docker.io docker-compose docker-compose-v2 podman-docker containerd runc; do
            if dpkg-query -W -f='${Status}' "$conflict" 2>/dev/null | grep -q 'install ok installed'; then
                fail "Conflicting package $conflict is installed; resolve it manually before installation"
            fi
        done
    fi
    printf 'Preflight passed for Ubuntu %s (%s); no host state changed.\n' "$os_version" "$architecture"
}

docker_ready() {
    command -v docker >/dev/null && docker version --format '{{.Server.Version}}' >/dev/null 2>&1 && docker compose version >/dev/null 2>&1
}

install_docker_if_needed() {
    if docker_ready; then
        if ! command -v curl >/dev/null; then
            apt-get update
            apt-get install -y --no-install-recommends ca-certificates curl
        fi
        return 0
    fi
    step 'Installing Docker Engine and Compose from the official Ubuntu apt repository'
    apt-get update
    apt-get install -y --no-install-recommends ca-certificates curl
    install -d -m 0755 /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod 0644 /etc/apt/keyrings/docker.asc
    local architecture codename
    architecture=$(dpkg --print-architecture)
    # shellcheck disable=SC1091
    source /etc/os-release
    codename=${UBUNTU_CODENAME:-$VERSION_CODENAME}
    printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' \
        "$codename" "$architecture" > /etc/apt/sources.list.d/docker.sources
    apt-get update
    apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    docker_ready || fail 'Docker Engine or Compose did not become ready'
}

compose() {
    docker compose --env-file "$INSTALL_ROOT/deployment/.env" -f "$INSTALL_ROOT/deployment/compose.yaml" "$@"
}

wait_healthy() {
    local service=$1 container status count
    container=$(compose ps -q "$service")
    [[ -n "$container" ]] || fail "$service container was not created"
    for ((count=0; count<60; count++)); do
        status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")
        [[ "$status" == healthy ]] && return 0
        [[ "$status" == unhealthy || "$status" == exited || "$status" == dead ]] && fail "$service did not become healthy"
        sleep 3
    done
    fail "$service health timed out"
}

write_deployment_environment() {
    local temporary_environment
    temporary_environment=$(mktemp "$INSTALL_ROOT/deployment/.env.XXXXXX")
    printf 'COMPOSE_PROJECT_NAME=solar-energy\nPOSTGRES_DB=solar_energy\nPOSTGRES_USER=solar_energy\nPOSTGRES_PORT=%s\nAPP_ENV=production\nAPP_HOSTNAME=%s\nALLOWED_HOSTS=localhost,127.0.0.1,%s\nTZ=Africa/Lagos\nCONFIG_DIRECTORY=/opt/solar-energy/config\nBACKUP_DIRECTORY=/opt/solar-energy/backups\nCERTIFICATE_DIRECTORY=/opt/solar-energy/certs\nPOSTGRES_PASSWORD_FILE=/opt/solar-energy/secrets/postgres_password\nJWT_SECRET_KEY_FILE=/opt/solar-energy/secrets/jwt_secret\nBACKUP_RETENTION_DAYS=30\n' \
        "$postgres_port" "$hostname_name" "$hostname_name" > "$temporary_environment"
    chmod 0600 "$temporary_environment"
    mv -- "$temporary_environment" "$INSTALL_ROOT/deployment/.env"
}

install_release_files() {
    step 'Installing reviewed release files and external secret directories'
    install -d -m 0755 "$INSTALL_ROOT"
    install -d -m 0700 "$INSTALL_ROOT/secrets" "$INSTALL_ROOT/certs"
    install -d -m 0700 -o 10001 -g 10001 "$INSTALL_ROOT/config" "$INSTALL_ROOT/backups"
    install -d -m 0755 "$INSTALL_ROOT/release"
    cp -a --no-preserve=ownership -- "$SCRIPT_DIR/backend" "$SCRIPT_DIR/frontend" "$SCRIPT_DIR/energy" "$SCRIPT_DIR/deployment" "$INSTALL_ROOT/"
    install -m 0644 "$SCRIPT_DIR/.dockerignore" "$INSTALL_ROOT/.dockerignore"
    install -m 0644 "$SCRIPT_DIR/VERSION" "$INSTALL_ROOT/release/VERSION"
    install -m 0644 "$SCRIPT_DIR/README.md" "$INSTALL_ROOT/release/README.md"
    if [[ -f "$SCRIPT_DIR/release-manifest.json" ]]; then
        install -m 0644 "$SCRIPT_DIR/release-manifest.json" "$INSTALL_ROOT/release/release-manifest.json"
    fi
    install -m 0644 "$certificate_source" "$INSTALL_ROOT/certs/fullchain.pem"
    install -m 0600 "$key_source" "$INSTALL_ROOT/certs/privkey.pem"
    openssl rand -hex 48 > "$INSTALL_ROOT/secrets/postgres_password"
    openssl rand -hex 48 > "$INSTALL_ROOT/secrets/jwt_secret"
    chmod 0600 "$INSTALL_ROOT/secrets/postgres_password" "$INSTALL_ROOT/secrets/jwt_secret"
    write_deployment_environment
    # The hostname was validated as DNS-only before substitution.
    sed -i "s/server_name _;/server_name ${hostname_name};/g" "$INSTALL_ROOT/deployment/nginx/default.conf"
}

install_services() {
    step 'Registering Compose and backup services for reboot recovery'
    install -m 0644 "$INSTALL_ROOT/deployment/systemd/solar-energy.service" /etc/systemd/system/solar-energy.service
    install -m 0644 "$INSTALL_ROOT/deployment/systemd/solar-energy-backup.service" /etc/systemd/system/solar-energy-backup.service
    install -m 0644 "$INSTALL_ROOT/deployment/systemd/solar-energy-backup.timer" /etc/systemd/system/solar-energy-backup.timer
    systemctl daemon-reload
    systemctl enable docker solar-energy.service solar-energy-backup.timer
    systemctl start solar-energy-backup.timer
}

install_application() {
    local existing_volume
    [[ $EUID -eq 0 ]] || fail 'Run installation with sudo: sudo ./install.sh ...'
    preflight
    install_docker_if_needed
    existing_volume=$(docker volume ls --quiet --filter name='^solar-energy_postgres_data$')
    [[ -z "$existing_volume" ]] || fail 'An existing solar-energy PostgreSQL volume was found; refusing a fresh install'
    [[ -z $(docker ps -aq --filter label=com.docker.compose.project=solar-energy) ]] || fail 'Existing solar-energy containers were found; refusing a fresh install'
    install_release_files
    step 'Validating Compose and building production images'
    compose config --quiet
    compose build
    step 'Starting PostgreSQL and applying migrations'
    compose up -d db
    wait_healthy db
    compose run --rm --no-deps migrate
    step 'Initializing the external runtime encryption key'
    compose --profile operations run --rm --no-deps runtime-key-init
    [[ -s "$INSTALL_ROOT/config/master.key" ]] || fail 'Runtime master key was not created'
    step 'Starting FastAPI and Nginx'
    compose up --no-deps -d backend
    wait_healthy backend
    compose up --no-deps -d web
    wait_healthy web
    curl --fail --silent --show-error --noproxy '*' --max-time 15 \
        --resolve "$hostname_name:443:127.0.0.1" "https://$hostname_name/healthz" >/dev/null || fail 'HTTPS health check failed; verify certificate trust and Nginx'
    printf '\nSolar Energy Management System %s installed.\nSetup URL: https://%s/setup\n' "$(< "$SCRIPT_DIR/VERSION")" "$hostname_name"
    printf 'The one-time setup code follows. Keep it safe; it is not saved to installer logs.\n'
    # Direct terminal output avoids storing the plaintext code in files or logs.
    compose --profile operations run --rm --no-deps setup-init
    install_services
    printf '\nOpen the HTTPS setup URL in a browser to finish onboarding.\n'
    printf 'Firewall rules were not changed; review deployment/README.md before LAN access.\n'
}

main() {
    parse_options "$@"
    if [[ "$check_only" == true ]]; then
        preflight
        return
    fi
    trap 'printf "Installation stopped at line %s; existing data was not deleted.\n" "$LINENO" >&2' ERR
    install_application
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    main "$@"
fi
