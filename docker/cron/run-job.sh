#!/bin/bash
set -euo pipefail

cd /app

if [ -f /app/.env ]; then
  set -a
  # shellcheck disable=SC1091
  source /app/.env
  set +a
fi

export APP_CONFIG="${APP_CONFIG:-config.toml}"

exec uv run python3 -m "$@"
