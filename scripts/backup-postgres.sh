#!/usr/bin/env sh
# Create a PostgreSQL custom-format backup without exposing database credentials.
# Usage:
#   sh scripts/backup-postgres.sh --output-dir ./backups
#   sh scripts/backup-postgres.sh --production --output-dir /srv/applyease-backups
#   sh scripts/backup-postgres.sh --schema-only --output-dir /tmp/applyease-backup-check
set -eu

production=false
schema_only=false
output_dir=""

usage() {
  echo "Usage: $0 [--production] [--schema-only] --output-dir DIRECTORY" >&2
  exit 64
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --production) production=true ;;
    --schema-only) schema_only=true ;;
    --output-dir) shift; [ "$#" -gt 0 ] || usage; output_dir="$1" ;;
    --help|-h) usage ;;
    *) usage ;;
  esac
  shift
done

[ -n "$output_dir" ] || usage
mkdir -p "$output_dir"
umask 077

compose() {
  if [ "$production" = true ]; then
    [ -f .env.production ] || { echo "Missing .env.production" >&2; exit 66; }
    docker compose --env-file .env.production -f docker-compose.production.yml "$@"
  else
    docker compose "$@"
  fi
}

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
kind="full"
[ "$schema_only" = true ] && kind="schema"
archive="$output_dir/applyease-${kind}-${timestamp}.dump"
container_archive="/tmp/applyease-backup-${timestamp}.dump"

dump_args="--format=custom --no-owner --no-privileges"
[ "$schema_only" = true ] && dump_args="$dump_args --schema-only"

echo "Creating ${kind} PostgreSQL backup at ${archive}"
# The database container already has POSTGRES_USER/POSTGRES_DB; do not read or
# print any secret on the host. The redirection writes a binary custom archive.
compose exec -T postgres sh -ceu 'pg_dump $1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' sh "$dump_args" > "$archive"

[ -s "$archive" ] || { echo "Backup failed: archive is empty" >&2; rm -f "$archive"; exit 1; }
# pg_restore's custom format requires a seekable file rather than stdin. Copy it
# into the database container only for validation, then remove it immediately.
cleanup_container_archive() {
  compose exec -T postgres rm -f "$container_archive" >/dev/null 2>&1 || true
}
trap cleanup_container_archive EXIT HUP INT TERM
compose cp "$archive" "postgres:${container_archive}" >/dev/null
compose exec -T postgres sh -ceu 'pg_restore --list "$1" >/dev/null' sh "$container_archive"
cleanup_container_archive
trap - EXIT HUP INT TERM

if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$archive" > "${archive}.sha256"
else
  sha256sum "$archive" > "${archive}.sha256"
fi
chmod 600 "$archive" "${archive}.sha256"
echo "Backup verified: ${archive}"
echo "Checksum: ${archive}.sha256"
