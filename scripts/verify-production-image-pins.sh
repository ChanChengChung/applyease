#!/usr/bin/env sh
# Keep production image selection reproducible. This intentionally checks only
# deployment inputs, not docker-compose.yml used for local development.
set -eu

require_digest() {
  file="$1"
  pattern="$2"
  if ! grep -Eq "$pattern" "$file"; then
    echo "Expected a SHA-256-pinned production image in $file" >&2
    exit 1
  fi
}

require_digest backend/Dockerfile '^FROM python:3\.13-slim@sha256:[a-f0-9]{64}$'
require_digest frontend/Dockerfile '^FROM node:22-alpine@sha256:[a-f0-9]{64} AS build$'
require_digest frontend/Dockerfile '^FROM nginx:1\.27-alpine@sha256:[a-f0-9]{64}$'
require_digest docker-compose.production.yml 'image: caddy:2\.8-alpine@sha256:[a-f0-9]{64}'
require_digest docker-compose.production.yml 'image: postgres:16-alpine@sha256:[a-f0-9]{64}'
require_digest docker-compose.production.yml 'image: milvusdb/milvus:v2\.5\.5@sha256:[a-f0-9]{64}'
require_digest scripts/verify-postgres-restore.sh 'postgres:16-alpine@sha256:[a-f0-9]{64}'

echo "Production base images are SHA-256 pinned."
