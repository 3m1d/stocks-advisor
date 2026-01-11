ALEMBIC_CONFIG ?= app/alembic.ini
export ALEMBIC_CONFIG

###############
# Init
###############

.PHONY: init uv-sync init-local-db

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
	make docker-up && sleep 10 && make alembic-run-migration-local

###############
# Alembic
###############

.PHONY: alembic-generate-migration alembic-run-migration alembic-generate-migration-local alembic-run-migration-local

# Сгенерировать новую миграцию
alembic-generate-migration:
	@if [ -z "$(name)" ]; then \
		echo "Error: name is required. Usage: make alembic-generate-migration name=<migration_name>"; \
		exit 1; \
	fi
	APP_CONFIG=config.toml uv run alembic -c $(ALEMBIC_CONFIG) revision --autogenerate -m "$(name)"

# Применить миграцию
alembic-run-migration:
	APP_CONFIG=config.toml uv run alembic -c $(ALEMBIC_CONFIG) upgrade head

# Сгенерировать новую миграцию для локальной БД
alembic-generate-migration-local:
	@if [ -z "$(name)" ]; then \
		echo "Error: name is required. Usage: make alembic-generate-migration name=<migration_name>"; \
		exit 1; \
	fi
	APP_CONFIG=config_local.toml uv run alembic -c $(ALEMBIC_CONFIG) revision --autogenerate -m "$(name)"

# Применить миграцию для локальной БД
alembic-run-migration-local:
	APP_CONFIG=config_local.toml uv run alembic -c $(ALEMBIC_CONFIG) upgrade head

###############
# App
###############

.PHONY: fastapi-run-dev fastapi-run-dev-local streamlit-run streamlit-run-local

# Запустить сервер для разработки.
# Конфиг БД берется из .env файла или переменных окружения.
fastapi-run-dev:
	APP_CONFIG=config.toml uv run fastapi dev app/main.py

# Сервер для разработки с локальной БД (в docker контейнере, см. docker-compose.yml).
# Конфиг БД берется из config_local.toml файла.
fastapi-run-dev-local:
	APP_CONFIG=config_local.toml uv run fastapi dev app/main.py

# Запустить Streamlit UI дашборд
# Конфиг БД берется из .env файла или переменных окружения.
streamlit-run:
	APP_CONFIG=config.toml uv run streamlit run streamlit_app.py

# Запустить Streamlit UI дашборд с локальной БД
streamlit-run-local:
	APP_CONFIG=config_local.toml uv run streamlit run streamlit_app.py

###############
# Docker
###############

.PHONY: docker-up docker-down docker-clean-volumes

# Запустить docker контейнеры
docker-up:
	docker compose up -d

# Остановить docker контейнеры
docker-down:
	docker compose down

# Остановить docker контейнеры и удалить volumes, указанные в docker-compose.yml.
# Полезно, если нужно очистить тестовые данные в БД.
docker-clean-volumes:
	docker compose down -v

###############
# Utils
###############

.PHONY: hash-password generate-jwt-certs parse-data-from-moex parse-data-from-moex-local

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

# Парсинг данных из MOEX за последние 60 дней
parse-data-from-moex:
	@now=$$(date +%Y-%m-%d); \
	start_dt=$$(date -d "$$now - 60 day" +%Y-%m-%d); \
	APP_CONFIG=config.toml uv run python3 -m app.daemons.parsers.asset_parser --start $$start_dt --end $$now

# Парсинг данных из MOEX в локальную БД за последние 60 дней
parse-data-from-moex-local:
	@now=$$(date +%Y-%m-%d); \
	start_dt=$$(date -d "$$now - 60 day" +%Y-%m-%d); \
	APP_CONFIG=config_local.toml uv run python3 -m app.daemons.parsers.asset_parser --start $$start_dt --end $$now
