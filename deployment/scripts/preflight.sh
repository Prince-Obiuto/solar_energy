#!/usr/bin/env bash
# Read-only production deployment diagnostics. It never prints file contents.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
deployment_dir=$(cd -- "$script_dir/.." && pwd -P)
environment_file=${SOLAR_DEPLOYMENT_ENV:-"$deployment_dir/.env"}
require_runtime_key=false
[[ ${1:-} == --require-runtime-key ]] && require_runtime_key=true

failures=0
check() {
    local label=$1
    shift
    if "$@"; then
        printf 'PASS %s\n' "$label"
    else
        printf 'FAIL %s\n' "$label" >&2
        failures=$((failures + 1))
    fi
}

environment_value() {
    local key=$1 line value
    line=$(grep -E "^${key}=" "$environment_file" | tail -n 1 || true)
    value=${line#*=}
    [[ -n "$line" && -n "$value" ]] || return 1
    printf '%s' "$value"
}

restricted() {
    local path=$1 mode
    mode=$(stat -c '%a' "$path" 2>/dev/null) || return 1
    (( (8#$mode & 0022) == 0 ))
}

port_unused() {
    local port=$1
    ! ss -ltn "sport = :$port" 2>/dev/null | grep -q ":$port"
}

[[ -f "$environment_file" && -r "$environment_file" ]] || {
    printf 'FAIL deployment environment file is unavailable\n' >&2
    exit 1
}

check 'Linux host' test "$(uname -s)" = Linux
check 'Docker CLI' command -v docker
check 'Docker Compose plugin' docker compose version
check 'deployment compose file' test -f "$deployment_dir/compose.yaml"
check 'required host configuration' environment_value APP_HOSTNAME
check 'explicit allowed hosts' bash -c '! grep -Eq "^ALLOWED_HOSTS=.*\\*" "$1"' _ "$environment_file"

config_directory=$(environment_value CONFIG_DIRECTORY || true)
backup_directory=$(environment_value BACKUP_DIRECTORY || true)
certificate_directory=$(environment_value CERTIFICATE_DIRECTORY || true)
password_file=$(environment_value POSTGRES_PASSWORD_FILE || true)
jwt_file=$(environment_value JWT_SECRET_KEY_FILE || true)

for item in \
    "configuration directory:$config_directory" \
    "backup directory:$backup_directory" \
    "certificate directory:$certificate_directory" \
    "PostgreSQL password file:$password_file" \
    "JWT secret file:$jwt_file"; do
    label=${item%%:*}
    path=${item#*:}
    check "$label exists" test -n "$path" -a -e "$path"
    [[ -n "$path" ]] && check "$label permissions" restricted "$path"
done

if [[ -n "$certificate_directory" ]]; then
    check 'TLS certificate exists' test -s "$certificate_directory/fullchain.pem"
    check 'TLS private key exists' test -s "$certificate_directory/privkey.pem"
fi
if [[ "$require_runtime_key" == true && -n "$config_directory" ]]; then
    check 'runtime master key exists' test -s "$config_directory/master.key"
    check 'runtime master key permissions' restricted "$config_directory/master.key"
fi

# Do this before startup. A running deployment intentionally occupies these.
check 'port 80 available before deployment' port_unused 80
check 'port 443 available before deployment' port_unused 443
check 'port 8000 available before deployment' port_unused 8000
postgres_port=$(environment_value POSTGRES_PORT || printf '5432')
check 'configured PostgreSQL port available before deployment' port_unused "$postgres_port"

if (( failures > 0 )); then
    printf 'Deployment preflight found %d issue(s); no host state was changed.\n' "$failures" >&2
    exit 1
fi
printf 'Deployment preflight passed.\n'
