ALEMBIC_CONFIG ?= app/alembic.ini
export ALEMBIC_CONFIG

# Export all variables from .env into subprocess environment
RUN_WITH_ENV = set -a && . ./.env && set +a &&

###############
# Init
###############

.PHONY: init uv-sync init-local-db

# Для запуска на проде нужен только python
init-prod: uv-sync generate-jwt-certs

# Инициализация проекта:
# - Установка зависимостей
# - Генерация сертификатов для JWT токенов
# - Запуск docker контейнеров и применение миграций для локальной БД
init: uv-sync generate-jwt-certs init-local-db

# Установка зависимостей
uv-sync:
	uv sync

# Запуск и применение миграций для локальной БД
init-local-db:
	make docker-up && sleep 10 && make alembic-run-migration

###############
# Alembic
###############

.PHONY: alembic-generate-migration-prod alembic-run-migration-prod alembic-generate-migration alembic-run-migration

# Сгенерировать новую миграцию на production БД
alembic-generate-migration-prod:
	@if [ -z "$(name)" ]; then \
		echo "Error: name is required. Usage: make alembic-generate-migration name=<migration_name>"; \
		exit 1; \
	fi
	$(RUN_WITH_ENV) APP_CONFIG=config.toml uv run alembic -c $(ALEMBIC_CONFIG) revision --autogenerate -m "$(name)"

# Применить миграцию на production БД
alembic-run-migration-prod:
	$(RUN_WITH_ENV) APP_CONFIG=config.toml uv run alembic -c $(ALEMBIC_CONFIG) upgrade head

# Сгенерировать новую миграцию для локальной БД
alembic-generate-migration:
	@if [ -z "$(name)" ]; then \
		echo "Error: name is required. Usage: make alembic-generate-migration name=<migration_name>"; \
		exit 1; \
	fi
	APP_CONFIG=config_local.toml uv run alembic -c $(ALEMBIC_CONFIG) revision --autogenerate -m "$(name)"

# Применить миграцию для локальной БД
alembic-run-migration:
	APP_CONFIG=config_local.toml uv run alembic -c $(ALEMBIC_CONFIG) upgrade head

###############
# App
###############

.PHONY: fastapi-run-dev-prod fastapi-run-dev streamlit-run-prod streamlit-run

# Запустить сервер для разработки.
# Конфиг БД берется из .env файла или переменных окружения.
fastapi-run-dev-prod:
	$(RUN_WITH_ENV) APP_CONFIG=config.toml uv run fastapi dev app/main.py

# Сервер для разработки с локальной БД (в docker контейнере, см. docker-compose.yml).
# Конфиг БД берется из config_local.toml файла.
fastapi-run-dev:
	APP_CONFIG=config_local.toml uv run fastapi dev app/main.py

# Запустить Streamlit UI дашборд
# Конфиг БД берется из .env файла или переменных окружения.
streamlit-run-prod:
	$(RUN_WITH_ENV) APP_CONFIG=config.toml uv run streamlit run streamlit_app.py

# Запустить Streamlit UI дашборд с локальной БД
streamlit-run:
	APP_CONFIG=config_local.toml uv run streamlit run streamlit_app.py

###############
# Docker
###############

.PHONY: docker-up docker-down docker-restart docker-up-prod docker-down-prod docker-logs-prod docker-clean-volumes

COMPOSE_PROD = docker compose -f docker-compose-production.yml --env-file production.env

# Запустить docker контейнеры
docker-up:
	docker compose up -d

# Остановить docker контейнеры
docker-down:
	docker compose down

# Перезапуск контейнеров
docker-restart: docker-down docker-up

# Запуск с production конфигом
docker-up-prod:
	mkdir -p data/minio_data_production
	$(COMPOSE_PROD) up -d --build

docker-down-prod:
	$(COMPOSE_PROD) down

docker-logs-prod:
	$(COMPOSE_PROD) logs -f minio mlflow-service

# Остановить docker контейнеры и удалить volumes, указанные в docker-compose.yml.
# Полезно, если нужно очистить тестовые данные в БД.
docker-clean-volumes:
	docker compose down -v

###############
# Utils
###############

.PHONY: hash-password generate-jwt-certs parse-data-from-moex-prod parse-data-from-moex parse-news-prod parse-news process-news-prod process-news

# Получить хэш пароля (алгоритм argon2)
hash-password:
	@if [ -z "$(password)" ]; then \
		echo "Error: password is required. Usage: make hash-password password=<your_password>"; \
		exit 1; \
	fi
	uv run app/scripts/hash_password.py "$(password)"

# Сгенерировать сертификаты для подписи JWT токенов
generate-jwt-certs:
	@mkdir -p app/certs
	openssl genrsa -out app/certs/jwt-private.pem 2048
	openssl rsa -in app/certs/jwt-private.pem -outform PEM -pubout -out app/certs/jwt-public.pem
	@echo "JWT keys generated successfully"

# Парсинг данных из MOEX (по умолчанию — последние 60 дней до сегодня)
# Usage: make parse-data-from-moex-prod [start=YYYY-MM-DD] [end=YYYY-MM-DD]
parse-data-from-moex-prod:
	@now=$$(date +%Y-%m-%d); \
	end_dt='$(end)'; \
	start_dt='$(start)'; \
	[ -z "$$end_dt" ] && end_dt=$$now; \
	[ -z "$$start_dt" ] && start_dt=$$(date -d "$$end_dt - 60 day" +%Y-%m-%d); \
	$(RUN_WITH_ENV) APP_CONFIG=config.toml uv run python3 -m app.daemons.parsers.asset_parser --start $$start_dt --end $$end_dt

# Парсинг данных из MOEX в локальную БД (по умолчанию — последние 60 дней до сегодня)
# Usage: make parse-data-from-moex [start=YYYY-MM-DD] [end=YYYY-MM-DD]
parse-data-from-moex:
	@now=$$(date +%Y-%m-%d); \
	end_dt='$(end)'; \
	start_dt='$(start)'; \
	[ -z "$$end_dt" ] && end_dt=$$now; \
	[ -z "$$start_dt" ] && start_dt=$$(date -d "$$end_dt - 60 day" +%Y-%m-%d); \
	APP_CONFIG=config_local.toml uv run python3 -m app.daemons.parsers.asset_parser --start $$start_dt --end $$end_dt

# Парсинг новостей (по умолчанию — последние 60 дней до сегодня)
# Usage: make parse-news-prod [start=YYYY-MM-DD] [end=YYYY-MM-DD]
parse-news-prod:
	@now=$$(date +%Y-%m-%d); \
	end_dt='$(end)'; \
	start_dt='$(start)'; \
	[ -z "$$end_dt" ] && end_dt=$$now; \
	[ -z "$$start_dt" ] && start_dt=$$(date -d "$$end_dt - 60 day" +%Y-%m-%d); \
	$(RUN_WITH_ENV) APP_CONFIG=config.toml uv run python3 -m app.daemons.parsers.news_parser --start $$start_dt --end $$end_dt

# Парсинг новостей в локальную БД (по умолчанию — последние 60 дней до сегодня)
# Usage: make parse-news [start=YYYY-MM-DD] [end=YYYY-MM-DD]
parse-news:
	@now=$$(date +%Y-%m-%d); \
	end_dt='$(end)'; \
	start_dt='$(start)'; \
	[ -z "$$end_dt" ] && end_dt=$$now; \
	[ -z "$$start_dt" ] && start_dt=$$(date -d "$$end_dt - 60 day" +%Y-%m-%d); \
	APP_CONFIG=config_local.toml uv run python3 -m app.daemons.parsers.news_parser --start $$start_dt --end $$end_dt

# Обработка новостей: тикеры, сектор, тональность (по умолчанию — последние 60 дней до сегодня)
# Usage: make process-news-prod [source=kommersant] [start=YYYY-MM-DD] [end=YYYY-MM-DD] [gpu=1]
process-news-prod:
	@now=$$(date +%Y-%m-%d); \
	end_dt='$(end)'; \
	start_dt='$(start)'; \
	[ -z "$$end_dt" ] && end_dt=$$now; \
	[ -z "$$start_dt" ] && start_dt=$$(date -d "$$end_dt - 60 day" +%Y-%m-%d); \
	args="--start $$start_dt --end $$end_dt"; \
	[ -n "$(source)" ] && args="$$args --source $(source)"; \
	[ "$(gpu)" = "1" ] && args="$$args --gpu"; \
	$(RUN_WITH_ENV) APP_CONFIG=config.toml uv run python3 -m app.daemons.analyzers.news_processor $$args

# Обработка новостей в локальной БД (по умолчанию — последние 60 дней до сегодня)
# Usage: make process-news [source=kommersant] [start=YYYY-MM-DD] [end=YYYY-MM-DD] [gpu=1]
process-news:
	@now=$$(date +%Y-%m-%d); \
	end_dt='$(end)'; \
	start_dt='$(start)'; \
	[ -z "$$end_dt" ] && end_dt=$$now; \
	[ -z "$$start_dt" ] && start_dt=$$(date -d "$$end_dt - 60 day" +%Y-%m-%d); \
	args="--start $$start_dt --end $$end_dt"; \
	[ -n "$(source)" ] && args="$$args --source $(source)"; \
	[ "$(gpu)" = "1" ] && args="$$args --gpu"; \
	APP_CONFIG=config_local.toml uv run python3 -m app.daemons.analyzers.news_processor $$args

###############
# Tests
###############

.PHONY: mlflow-smoke-test mlflow-smoke-test-prod dl-experiments-search dl-experiments-prd dl-experiments-analysis dl-demonstration

# Проверка подключения к MLFlow
mlflow-smoke-test:
	APP_CONFIG=config_local.toml uv run python -m app.scripts.mlflow_smoke_test

mlflow-smoke-test-prod:
	$(RUN_WITH_ENV) APP_CONFIG=config.toml uv run python -m app.scripts.mlflow_smoke_test

###############
# Training & demonstration
###############

# Подбор гиперпараметров LSTM (все тикеры из conf/config.yaml)
dl-experiments-search:
	$(RUN_WITH_ENV) uv run python -m stocks_dl.cli.dl_experiments mode=search environment=prod experiment=lstm_checkpoint

# Только один тикер: make dl-experiments-search-ticker TICKER=GAZP
dl-experiments-search-ticker:
	$(RUN_WITH_ENV) uv run python -m stocks_dl.cli.dl_experiments mode=search environment=prod experiment=lstm_checkpoint ticker=$(TICKER)

# PRD для всех тикеров (нужен search summary CSV или runs в MLflow)
dl-experiments-prd:
	$(RUN_WITH_ENV) uv run python -m stocks_dl.cli.dl_experiments mode=prd environment=prod experiment=lstm_checkpoint

dl-experiments-prd-ticker:
	$(RUN_WITH_ENV) uv run python -m stocks_dl.cli.dl_experiments mode=prd environment=prod experiment=lstm_checkpoint ticker=$(TICKER)

# Анализ ошибок PRD
dl-experiments-analysis:
	$(RUN_WITH_ENV) uv run python -m stocks_dl.cli.dl_experiments mode=analysis environment=prod experiment=lstm_checkpoint

dl-experiments-analysis-ticker:
	$(RUN_WITH_ENV) uv run python -m stocks_dl.cli.dl_experiments mode=analysis environment=prod experiment=lstm_checkpoint ticker=$(TICKER)

# Демонстрация PRD (все тикеры)
dl-demonstration:
	$(RUN_WITH_ENV) uv run python -m stocks_dl.cli.dl_demonstration environment=prod experiment=lstm_checkpoint

dl-demonstration-ticker:
	$(RUN_WITH_ENV) uv run python -m stocks_dl.cli.dl_demonstration environment=prod experiment=lstm_checkpoint ticker=$(TICKER)
