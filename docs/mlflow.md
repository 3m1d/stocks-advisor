# MLflow + S3 (MinIO)

## Local development

| Сервис | URL | Назначение |
|--------|-----|------------|
| MLflow UI | http://localhost:5050 | Runs, metrics, Model Registry |
| MinIO API (S3) | http://localhost:9000 | Артефакты |
| MinIO Console | http://localhost:9001 | Веб-UI bucket'ов |
| PostgreSQL | `localhost:5432` | Метаданные MLflow (локальный контейнер) |

```bash
make docker-up
```

## Production (VPS)

PostgreSQL на **отдельной VM**. На ML VPS поднимаются только MinIO и MLflow.

### 1. Подготовить Postgres на DB VM

```sql
CREATE USER mlflow_user WITH PASSWORD '...';
CREATE DATABASE mlflow OWNER mlflow_user;
CREATE DATABASE mlflow_auth OWNER mlflow_user;
```

Разрешить подключение только с IP ML VPS (`pg_hba.conf` + firewall).

Перед сборкой образа отредактируйте `docker/mlflow/basic_auth.ini` (URI auth-БД и пароль admin).

### 2. Настроить ML VPS

```bash
cp production.env.example production.env
# отредактировать: MLFLOW_BACKEND_STORE_URI, MINIO_ROOT_*, MLFLOW_S3_BUCKET
make docker-prod-up
```

Сервисы с `restart: unless-stopped` — переживают перезагрузку VPS.

| Сервис | Доступ | Примечание |
|--------|--------|------------|
| MLflow | `127.0.0.1:5050` | Проксируйте через nginx/Caddy с TLS |
| MinIO API | `127.0.0.1:9000` | Только для MLflow внутри Docker |
| MinIO Console | `127.0.0.1:9001` | Админка; не публикуйте в интернет |

Проверка:

```bash
curl http://127.0.0.1:5050/health
make docker-prod-logs
```

Повторный init bucket безопасен:

```bash
docker compose -f docker-compose-production.yml --env-file production.env run --rm minio-init
```

### 3. Клиенты (ноутбуки)

```env
MLFLOW__TRACKING_URI=https://mlflow.yourdomain.com
MLFLOW_TRACKING_USERNAME=admin
MLFLOW_TRACKING_PASSWORD=your-password
```

С `--serve-artifacts` артефакты идут через MLflow API; прямой доступ к MinIO с ноутбуков не обязателен.

## Использование в коде

```python
from app.mlflow import configure_mlflow
import mlflow

configure_mlflow()

with mlflow.start_run(run_name="SBER-catboost"):
    mlflow.log_param("ticker", "SBER")
    mlflow.log_metric("rmse", 0.12)
    mlflow.sklearn.log_model(model, "model")
```
