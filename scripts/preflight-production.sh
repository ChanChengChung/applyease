#!/usr/bin/env sh
# Validate production deployment inputs without printing secret values.
# Usage: sh scripts/preflight-production.sh [--env-file .env.production]
set -eu

env_file=".env.production"
if [ "${1:-}" = "--env-file" ]; then
  [ "$#" -eq 2 ] || { echo "Usage: $0 [--env-file .env.production]" >&2; exit 64; }
  env_file="$2"
elif [ "$#" -ne 0 ]; then
  echo "Usage: $0 [--env-file .env.production]" >&2
  exit 64
fi

[ -f "$env_file" ] || { echo "Missing production environment file: $env_file" >&2; exit 66; }

if stat -f '%Lp' "$env_file" >/dev/null 2>&1; then
  mode="$(stat -f '%Lp' "$env_file")"
else
  mode="$(stat -c '%a' "$env_file")"
fi
if [ "$mode" != "600" ]; then
  echo "Refusing unsafe environment file permissions ($mode). Run: chmod 600 $env_file" >&2
  exit 65
fi

required_keys='APP_DOMAIN APP_VERSION POSTGRES_USER POSTGRES_PASSWORD AUTH_SECRET MAIL_FROM SMTP_HOST SMTP_USERNAME SMTP_PASSWORD'
failed=false
for key in $required_keys; do
  value="$(sed -n "s/^${key}=//p" "$env_file" | tail -n 1)"
  if [ -z "$value" ]; then
    echo "Missing required setting: $key" >&2
    failed=true
  elif printf '%s' "$value" | grep -Eqi 'replace-with|your-provider|example\.com'; then
    echo "Placeholder value is not allowed for: $key" >&2
    failed=true
  fi
done

auth_secret="$(sed -n 's/^AUTH_SECRET=//p' "$env_file" | tail -n 1)"
if [ -n "$auth_secret" ] && [ "${#auth_secret}" -lt 32 ]; then
  echo "AUTH_SECRET must contain at least 32 characters" >&2
  failed=true
fi

database_password="$(sed -n 's/^POSTGRES_PASSWORD=//p' "$env_file" | tail -n 1)"
if [ -n "$database_password" ] && [ "${#database_password}" -lt 16 ]; then
  echo "POSTGRES_PASSWORD must contain at least 16 characters" >&2
  failed=true
fi

smtp_starttls="$(sed -n 's/^SMTP_STARTTLS=//p' "$env_file" | tail -n 1)"
if [ -n "$smtp_starttls" ] && [ "$smtp_starttls" != "true" ]; then
  echo "SMTP_STARTTLS must be true in production" >&2
  failed=true
fi

screenshot_ocr_enabled="$(sed -n 's/^SCREENSHOT_OCR_ENABLED=//p' "$env_file" | tail -n 1)"
gemini_api_key="$(sed -n 's/^GEMINI_API_KEY=//p' "$env_file" | tail -n 1)"
if [ "$screenshot_ocr_enabled" = "true" ] && [ -z "$gemini_api_key" ]; then
  echo "SCREENSHOT_OCR_ENABLED=true requires GEMINI_API_KEY (or set OCR to false)" >&2
  failed=true
fi

domain="$(sed -n 's/^APP_DOMAIN=//p' "$env_file" | tail -n 1)"
if [ -n "$domain" ] && ! printf '%s' "$domain" | grep -Eq '^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'; then
  echo "APP_DOMAIN must be a hostname without a scheme, path, or port" >&2
  failed=true
fi

[ "$failed" = false ] || exit 65

# Compose validates required interpolation and production topology. It does not
# start containers and does not write secret values to stdout.
docker compose --env-file "$env_file" -f docker-compose.production.yml config --quiet
echo "Production preflight passed. DNS, firewall, SMTP delivery, backup restore, and public HTTPS checks still require the real deployment environment."
