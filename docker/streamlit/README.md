# Streamlit production container

Запускает дашборд вместе с MinIO и MLflow из `docker-compose-production.yml`.

## Требования

- Запущенный PostgreSQL
- MLFlow и S3 в соседних docker-контейнерах
- `.env` и `production.env` в корне репозитория

Compose перезаписывает URL-ы MLflow/S3:

- `MLFLOW__TRACKING_URI=http://mlflow-service:5000`
- `MLFLOW__S3_ENDPOINT_URL=http://minio:9000`

## Запуск

```bash
make docker-up-prod
```

Streamlit слушает на `127.0.0.1:8501` (см. `STREAMLIT_HOST_PORT`).
