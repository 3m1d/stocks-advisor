# Cron service

Периодически запускает парсинг и анализ данных, а также переобучение LSTM по cron расписанию.

## Расписание

Расписание задаётся в `docker/cron/crontab`.

## Запуск

Запускается вместе с остальными контейнерами в prod конфиге:

```bash
make docker-up-prod
```

Сборка образа:

```bash
make docker-build-prod          # streamlit + cron
make docker-build-cron-prod     # только cron
```

## Логи

Стандартный вывод cron-демона:

```bash
docker compose -f docker-compose-production.yml --env-file production.env logs -f cron
```

Вывод каждой кронджобы (один файл на pipeline):

```bash
docker exec stocks-advisor-cron tail -f /var/log/cron/asset_parser.log
docker exec stocks-advisor-cron tail -f /var/log/cron/news_parser.log
docker exec stocks-advisor-cron tail -f /var/log/cron/news_processor.log
docker exec stocks-advisor-cron tail -f /var/log/cron/lstm_retrain.log
```

## Запуск крона вручную

```bash
docker exec stocks-advisor-cron /app/docker/cron/run-job.sh app.daemons.parsers.asset_parser --incremental
docker exec stocks-advisor-cron /app/docker/cron/run-lstm-retrain.sh
```

## Конфиги

- Переменные окружения: `.env` (монтируется read-only в `/app/.env` и через `env_file`)
- Конфиг приложения: `APP_CONFIG=config.toml`
- Требует доступа к PostgreSQL (`DATABASE__HOST`), MLflow/MinIO и внешним MOEX/news API
- Переобучение LSTM: `retrain.run_search=false` (только PRD); для grid search передайте `retrain.run_search=true` в `run-lstm-retrain.sh`
