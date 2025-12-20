.PHONY: alembic-generate-migration alembic-run-migration

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

fastapi-run-dev:
	uv run fastapi dev app/main.py