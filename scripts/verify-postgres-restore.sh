#!/usr/bin/env sh
# Restore a custom-format ApplyEase PostgreSQL archive into an ephemeral,
# network-isolated PostgreSQL container. It never connects to the live database.
# Usage: sh scripts/verify-postgres-restore.sh --archive ./backups/applyease-full-....dump
set -eu

archive=""

usage() {
  echo "Usage: $0 --archive PATH_TO_CUSTOM_POSTGRES_DUMP" >&2
  exit 64
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --archive) shift; [ "$#" -gt 0 ] || usage; archive="$1" ;;
    --help|-h) usage ;;
    *) usage ;;
  esac
  shift
done

[ -n "$archive" ] || usage
[ -f "$archive" ] && [ -s "$archive" ] || { echo "Archive is missing or empty" >&2; exit 66; }

# Resolve the host path before mounting. The basename is deliberately fixed in
# the temporary container so a crafted path cannot affect the restore command.
archive_dir="$(cd "$(dirname "$archive")" && pwd -P)"
archive_name="$(basename "$archive")"
archive_path="$archive_dir/$archive_name"

command -v docker >/dev/null 2>&1 || { echo "Docker is required" >&2; exit 69; }

restore_name="applyease-restore-check-$(date -u +%Y%m%d%H%M%S)-$$"
restore_db="applyease_restore_check"
started=false

cleanup() {
  if [ "$started" = true ]; then
    docker rm -f "$restore_name" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT HUP INT TERM

# The restore database has no published ports and --network none, so an archive
# cannot cause a connection to production even if it contains unusual SQL.
docker run -d --rm \
  --name "$restore_name" \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --tmpfs /var/run/postgresql:rw,noexec,nosuid,size=16m \
  --tmpfs /var/lib/postgresql/data:rw,nosuid,size=768m \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  -e POSTGRES_DB="$restore_db" \
  -v "$archive_path:/restore/input.dump:ro" \
  postgres:16-alpine@sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777 >/dev/null
started=true

attempt=0
while ! docker exec "$restore_name" pg_isready -U postgres -d "$restore_db" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "Temporary PostgreSQL container did not become ready" >&2
    docker logs "$restore_name" >&2 || true
    exit 1
  fi
  sleep 1
done

docker exec "$restore_name" pg_restore \
  --exit-on-error \
  --no-owner \
  --no-privileges \
  -U postgres \
  -d "$restore_db" \
  /restore/input.dump

table_count="$(docker exec "$restore_name" psql -U postgres -d "$restore_db" -tAc "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")"
case "$table_count" in
  ''|*[!0-9]*) echo "Restore verification could not count public tables" >&2; exit 1 ;;
esac

if [ "$table_count" -lt 1 ]; then
  echo "Restore verification found no public tables" >&2
  exit 1
fi

echo "Restore verified in isolated container: ${table_count} public tables restored"
