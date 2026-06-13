# Cron service

Периодически запускает парсинг и обработку данных (MOEX, новости). Обучение LSTM — в отдельном контейнере `cron-train` (см. `docker/cron-train/README.md`).

## Расписание

Расписание задаётся в `docker/cron/crontab`.

## Запуск

Запускается вместе с остальными контейнерами в prod конфиге:

```bash
make docker-up-prod
```

Сборка образа:

```bash
make docker-build-prod          # streamlit + cron + cron-train
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
```

## Ручной запуск

```bash
docker exec stocks-advisor-cron /app/docker/cron/run-job.sh app.daemons.parsers.asset_parser --incremental
docker exec stocks-advisor-cron /app/docker/cron/run-job.sh app.daemons.parsers.news_parser --incremental
docker exec stocks-advisor-cron /app/docker/cron/run-job.sh app.daemons.analyzers.news_processor --incremental
```

## Конфиги

- Переменные окружения: `.env` (монтируется read-only в `/app/.env` и через `env_file`)
- Конфиг приложения: `APP_CONFIG=config.toml`
- Требует доступа к PostgreSQL (`DATABASE__HOST`) и внешним MOEX/news API
