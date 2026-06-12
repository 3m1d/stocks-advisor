# Streamlit production container

Runs the dashboard alongside MinIO and MLflow from `docker-compose-production.yml`.

## Prerequisites

- Docker Compose v2 on the VM (same host as MinIO/MLflow)
- PostgreSQL on a separate VM (app data, not MLflow DB)
- `.env` in repo root with app secrets (`DATABASE__*`, `JWT__*`, optional `MLFLOW__TRACKING_USERNAME/PASSWORD`)
- `production.env` from `production.env.example`

In `.env`, set Postgres to the external VM:

```bash
DATABASE__HOST=10.0.0.10
DATABASE__PORT=5432
DATABASE__NAME=stocks_advisor_db
DATABASE__USER=...
DATABASE__PASSWORD=...
```

Compose overrides MLflow/S3 URLs for the container network:

- `MLFLOW__TRACKING_URI=http://mlflow-service:5000`
- `MLFLOW__S3_ENDPOINT_URL=http://minio:9000`

## Start

```bash
cp production.env.example production.env   # edit secrets
cp .env.example .env                       # edit DATABASE__*, JWT__*

mkdir -p data/minio_data_production
make docker-up-prod
```

Streamlit listens on `127.0.0.1:8501` (see `STREAMLIT_HOST_PORT`). Put nginx/Caddy in front for HTTPS.

## Useful commands

```bash
make docker-build-streamlit-prod   # rebuild image only
make docker-logs-prod               # minio + mlflow + streamlit logs
docker compose -f docker-compose-production.yml --env-file production.env logs -f streamlit
```

## Cache

Prediction cache is stored in the `streamlit_cache` Docker volume (`/app/.cache/streamlit`).
