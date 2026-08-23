#!/usr/bin/env sh
# Start a disposable, localhost-only production stack and verify the public
# proxy chain. The unique Compose project creates isolated networks/volumes.
# Usage: sh scripts/verify-production-stack.sh [ENV_TEMPLATE]
set -eu

template="${1:-deploy/production-integration.env.example}"
[ -f "$template" ] || { echo "Missing integration environment template: $template" >&2; exit 66; }
command -v docker >/dev/null 2>&1 || { echo "Docker is required" >&2; exit 69; }
command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 69; }

workspace="$(mktemp -d /tmp/applyease-production-stack.XXXXXX)"
env_file="$workspace/.env"
project="applyease-production-check-$$"
cp "$template" "$env_file"
chmod 600 "$env_file"

compose() {
  docker compose -p "$project" --env-file "$env_file" -f docker-compose.production.yml "$@"
}

cleanup() {
  # Compose normally removes every resource. If a CI runner or interactive
  # terminal delivers a signal while Compose is waiting on Milvus shutdown,
  # use the unique project label as a narrowly-scoped second cleanup path.
  # Never target a broad name prefix or the developer's normal Compose stack.
  compose down -v --remove-orphans >/dev/null 2>&1 || true

  container_ids="$(docker ps -aq --filter "label=com.docker.compose.project=$project" 2>/dev/null || true)"
  if [ -n "$container_ids" ]; then
    docker rm -f $container_ids >/dev/null 2>&1 || true
  fi

  volume_ids="$(docker volume ls -q --filter "label=com.docker.compose.project=$project" 2>/dev/null || true)"
  if [ -n "$volume_ids" ]; then
    docker volume rm $volume_ids >/dev/null 2>&1 || true
  fi

  network_ids="$(docker network ls -q --filter "label=com.docker.compose.project=$project" 2>/dev/null || true)"
  if [ -n "$network_ids" ]; then
    docker network rm $network_ids >/dev/null 2>&1 || true
  fi
  rm -rf "$workspace"
}
trap cleanup EXIT
trap 'cleanup; exit 130' HUP INT TERM

# Compose can return before an entire dependency chain has transitioned to
# healthy on slower runners. Build once, then start in two explicit stages.
compose build backend frontend
compose up -d postgres milvus backend

backend_id=""
attempt=0
while :; do
  backend_id="$(compose ps -q backend)"
  if [ -n "$backend_id" ] && [ "$(docker inspect --format '{{.State.Health.Status}}' "$backend_id")" = "healthy" ]; then
    break
  fi
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    compose logs --tail=120 backend postgres milvus >&2 || true
    echo "Backend did not become healthy" >&2
    exit 1
  fi
  sleep 1
done

compose up -d frontend

frontend_id=""
attempt=0
while :; do
  frontend_id="$(compose ps -q frontend)"
  if [ -n "$frontend_id" ] && [ "$(docker inspect --format '{{.State.Health.Status}}' "$frontend_id")" = "healthy" ]; then
    break
  fi
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 45 ]; then
    compose logs --tail=120 frontend backend >&2 || true
    echo "Frontend did not become healthy" >&2
    exit 1
  fi
  sleep 1
done

# Start the public edge only after its two dependency stages are healthy. This
# avoids Compose's timing-sensitive chained `service_healthy` startup on busy
# CI runners while preserving the same production topology.
compose up -d --no-deps caddy

attempt=0
until curl -kfsS --max-time 5 https://localhost/health/ready > "$workspace/ready.json"; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 45 ]; then
    compose logs --tail=120 >&2 || true
    echo "Production integration readiness did not succeed" >&2
    exit 1
  fi
  sleep 1
done

grep -q '"status":"ok"' "$workspace/ready.json"
grep -q '"migration":"0012_ai_usage_buckets"' "$workspace/ready.json"
grep -q '"version":"integration-check-2026-08-20"' "$workspace/ready.json"

http_status="$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' http://localhost/health/ready)"
[ "$http_status" = "308" ] || { echo "Expected HTTP to redirect, got $http_status" >&2; exit 1; }

headers="$(curl -ksSI --max-time 5 https://localhost/health/ready)"
printf '%s\n' "$headers" | grep -qi '^strict-transport-security: max-age=31536000'
printf '%s\n' "$headers" | grep -qi "^content-security-policy: default-src 'none'"

unauth_status="$(curl -ksS --max-time 5 -o /dev/null -w '%{http_code}' https://localhost/api/v1/auth/me)"
[ "$unauth_status" = "401" ] || { echo "Expected unauthenticated API response, got $unauth_status" >&2; exit 1; }

# The public frontend relay must shed an abusive authentication burst before
# it can turn into a credential-stuffing or SMTP/resource exhaustion event.
# Empty login bodies are deliberately invalid and create no account/session;
# their first responses come from FastAPI (422), then Nginx must return 429.
auth_limited=0
for attempt in $(seq 1 25); do
  status="$(curl -ksS --max-time 5 -o /dev/null -w '%{http_code}' -X POST https://localhost/api/v1/auth/login)"
  if [ "$status" = "429" ]; then
    auth_limited=1
    break
  fi
done
[ "$auth_limited" = "1" ] || { echo "Expected Nginx authentication burst limit to return 429" >&2; exit 1; }

caddy_id="$(compose ps -q caddy)"
postgres_id="$(compose ps -q postgres)"
milvus_id="$(compose ps -q milvus)"
[ -n "$caddy_id" ] && [ -n "$frontend_id" ] && [ -n "$backend_id" ] && [ -n "$postgres_id" ] && [ -n "$milvus_id" ] || { echo "Expected all production services" >&2; exit 1; }

caddy_networks="$(docker inspect --format '{{range $network, $_ := .NetworkSettings.Networks}}{{$network}} {{end}}' "$caddy_id")"
frontend_networks="$(docker inspect --format '{{range $network, $_ := .NetworkSettings.Networks}}{{$network}} {{end}}' "$frontend_id")"
backend_networks="$(docker inspect --format '{{range $network, $_ := .NetworkSettings.Networks}}{{$network}} {{end}}' "$backend_id")"
printf '%s\n' "$caddy_networks" | grep -q "${project}_edge"
! printf '%s\n' "$caddy_networks" | grep -q "${project}_app"
printf '%s\n' "$frontend_networks" | grep -q "${project}_edge"
printf '%s\n' "$frontend_networks" | grep -q "${project}_app"
printf '%s\n' "$backend_networks" | grep -q "${project}_app"
! printf '%s\n' "$backend_networks" | grep -q "${project}_edge"
[ -z "$(docker port "$backend_id")" ] || { echo "Backend must not publish a host port" >&2; exit 1; }

# Production memory ceilings stop one malformed parser/model/index workload
# from exhausting the entire VM. Assert the effective Docker HostConfig, not
# merely the Compose source text.
memory_limit() {
  actual="$(docker inspect --format '{{.HostConfig.Memory}}' "$1")"
  [ "$actual" = "$2" ] || { echo "Expected memory limit $2, got $actual for $1" >&2; exit 1; }
}
memory_limit "$caddy_id" 268435456
memory_limit "$frontend_id" 268435456
memory_limit "$backend_id" 805306368
memory_limit "$postgres_id" 805306368
memory_limit "$milvus_id" 1073741824

echo "Isolated production stack verification passed."
