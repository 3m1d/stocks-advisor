ALEMBIC_CONFIG ?= app/alembic.ini
export ALEMBIC_CONFIG

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

.PHONY: fastapi-run-dev fastapi-run-dev-local

# Запустить сервер для разработки. Конфиг базы берется из config.toml
fastapi-run-dev:
	APP_CONFIG=config.toml uv run fastapi dev app/main.py

# Сервер для разработки с локальной БД (в docker контейнере, см. docker-compose.yml)
fastapi-run-dev-local:
	APP_CONFIG=config_local.toml uv run fastapi dev app/main.py

###############
# Utils
###############

.PHONY: hash-password generate-jwt-certs

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
