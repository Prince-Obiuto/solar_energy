#!/usr/bin/env bash
# Create a custom-format PostgreSQL backup through the database container.
# This script never reads, prints, or passes a database password as an argument.
set -euo pipefail
umask 077

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
deployment_dir=$(cd -- "$script_dir/.." && pwd -P)
repository_dir=$(cd -- "$deployment_dir/.." && pwd -P)
compose_file="$deployment_dir/compose.yaml"
environment_file=${SOLAR_DEPLOYMENT_ENV:-"$deployment_dir/.env"}
backup_directory=${BACKUP_DIRECTORY:-/opt/solar-energy/backups}

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

environment_value() {
    local key=$1 line value
    line=$(grep -E "^${key}=" "$environment_file" | tail -n 1 || true)
    value=${line#*=}
    [[ -n "$line" && -n "$value" ]] || fail "Required deployment setting $key is missing"
    printf '%s' "$value"
}

[[ -f "$environment_file" && -r "$environment_file" ]] || fail "Deployment environment file is unavailable"
[[ -d "$backup_directory" && -w "$backup_directory" ]] || fail "Backup directory is unavailable"
backup_directory=$(realpath -e -- "$backup_directory") || fail "Backup directory is unavailable"
case "$backup_directory" in
    /opt/solar-energy/backups|/opt/solar-energy/backups/*) ;;
    *) fail "Backup directory is outside the approved deployment path" ;;
esac

database_name=$(environment_value POSTGRES_DB)
database_user=$(environment_value POSTGRES_USER)
retention_days=${BACKUP_RETENTION_DAYS:-$(grep -E '^BACKUP_RETENTION_DAYS=' "$environment_file" | tail -n 1 | cut -d= -f2- || true)}
retention_days=${retention_days:-30}
[[ "$retention_days" =~ ^[0-9]+$ && "$retention_days" -ge 1 && "$retention_days" -le 3650 ]] || fail "BACKUP_RETENTION_DAYS must be between 1 and 3650"

timestamp=$(date -u +%Y-%m-%d_%H%M%S)
final_file="$backup_directory/solar_energy_${timestamp}.dump"
partial_file="$backup_directory/.solar_energy_${timestamp}.dump.partial"
[[ ! -e "$final_file" && ! -e "$partial_file" ]] || fail "A backup with this timestamp already exists"

cleanup() {
    [[ -e "$partial_file" ]] && rm -f -- "$partial_file"
}
trap cleanup EXIT

cd -- "$repository_dir"
docker compose --env-file "$environment_file" -f "$compose_file" exec -T db \
    pg_dump --format=custom --compress=9 --no-owner --no-privileges \
    --username="$database_user" --dbname="$database_name" > "$partial_file"

[[ -s "$partial_file" ]] || fail "PostgreSQL did not produce a usable backup"
mv -- "$partial_file" "$final_file"
trap - EXIT

# Retention is deliberately constrained to matching files at this exact depth.
find "$backup_directory" -mindepth 1 -maxdepth 1 -type f -name 'solar_energy_*.dump' \
    -mtime "+$retention_days" -delete

printf 'Backup created: %s\n' "$final_file"
