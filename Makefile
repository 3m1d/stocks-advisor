.PHONY: alembic-generate-migration alembic-run-migration hash-password generate-jwt-certs

ALEMBIC_CONFIG ?= app/alembic.ini
export ALEMBIC_CONFIG

###############
# Alembic
###############

# Сгенерировать новую миграцию
alembic-generate-migration:
	@if [ -z "$(name)" ]; then \
		echo "Error: name is required. Usage: make alembic-generate-migration name=<migration_name>"; \
		exit 1; \
	fi
	uv run alembic -c $(ALEMBIC_CONFIG) revision --autogenerate -m "$(name)"

# Применить миграцию
alembic-run-migration:
	uv run alembic -c $(ALEMBIC_CONFIG) upgrade head


###############
# App
###############

# Запустить сервер для разработки
fastapi-run-dev:
	uv run fastapi dev app/main.py

###############
# Utils
###############

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
	@echo "Generating JWT private key..."
	openssl genrsa -out app/certs/jwt-private.pem 2048
	@echo "Generating JWT public key..."
	openssl rsa -in app/certs/jwt-private.pem -outform PEM -pubout -out app/certs/jwt-public.pem
	@echo "JWT keys generated successfully in app/certs/"
