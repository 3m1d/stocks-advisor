# Stocks Advisor

## Структура приложения

- **`core/`** — основная бизнес-логика приложения:
  - `clients/` — клиенты для внешних API
  - `config/` — конфигурация и настройки приложения
  - `database/` — работа с базой данных
  - `schemas/` - Pydantic схемы данных

- **`daemons/`** — демоны

- **`web/`** — веб-приложение на FastAPI

- **`docs/`** — документация проекта:
  - `database/` - описание таблиц базы данных

## Разработка

### Миграции

При добавлении новой модели SQLALchemy или при изменнии существующей модели, нужно:

- Запустить `uv run alembic -c app/alembic.ini revision --autogenerate -m <Название миграции>` (или `make alembic-generate-migration`)
- Проверить созданную миграцию
- Запустить `uv run alembic upgrade head` (или `alembic-run-migration`)
