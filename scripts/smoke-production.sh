#!/bin/sh
# Read-only post-deployment smoke test for a publicly reachable ApplyEase site.
# It intentionally does not authenticate, create data, or print any secret.
set -eu

usage() {
  echo "Usage: $0 https://your-domain.example" >&2
  exit 64
}

[ "$#" -eq 1 ] || usage
base_url=${1%/}

case "$base_url" in
  https://*) ;;
  *)
    echo "Expected an HTTPS base URL (for example https://applyease.example)." >&2
    exit 64
    ;;
esac

domain=${base_url#https://}
case "$domain" in
  *"/"*|"?"*|"#"*|"")
    echo "Pass only an HTTPS origin, without a path, query, or fragment." >&2
    exit 64
    ;;
esac

ready_body=$(curl --fail --silent --show-error --connect-timeout 10 --max-time 20 "$base_url/health/ready")
case "$ready_body" in
  *'"status":"ok"'*'"database":"ok"'*) ;;
  *)
    echo "Readiness response did not report an available database: $ready_body" >&2
    exit 1
    ;;
esac

case "$ready_body" in
  *'"version":"'*'"'*) ;;
  *)
    echo "Readiness response did not identify the running release." >&2
    exit 1
    ;;
esac

headers=$(curl --fail --silent --show-error --head --connect-timeout 10 --max-time 20 "$base_url/health/ready")
printf '%s\n' "$headers" | grep -qi '^strict-transport-security:' || {
  echo "Missing Strict-Transport-Security on HTTPS readiness response." >&2
  exit 1
}
printf '%s\n' "$headers" | grep -qi '^content-security-policy:' || {
  echo "Missing Content-Security-Policy on HTTPS readiness response." >&2
  exit 1
}
printf '%s\n' "$headers" | grep -qi '^cross-origin-opener-policy: same-origin' || {
  echo "Missing Cross-Origin-Opener-Policy: same-origin on HTTPS readiness response." >&2
  exit 1
}
printf '%s\n' "$headers" | grep -qi '^cross-origin-resource-policy: same-origin' || {
  echo "Missing Cross-Origin-Resource-Policy: same-origin on HTTPS readiness response." >&2
  exit 1
}

http_status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --connect-timeout 10 --max-time 20 "http://$domain/health/ready")
case "$http_status" in
  301|302|307|308) ;;
  *)
    echo "HTTP health endpoint did not redirect to HTTPS (received $http_status)." >&2
    exit 1
    ;;
esac

echo "Production smoke test passed for $base_url"
