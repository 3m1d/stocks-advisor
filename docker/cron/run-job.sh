#!/bin/bash
set -euo pipefail

cd /app

# Env comes from docker compose: env_file (.env) + environment overrides.
# Do not source .env here — it would overwrite compose values (e.g. MLFLOW URLs).

export APP_CONFIG="${APP_CONFIG:-config.toml}"

exec uv run python3 -m "$@"
