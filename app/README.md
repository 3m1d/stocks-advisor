# Инвестиционный Советник

## О приложении

`Инвестиционный советник` - приложение, занимающееся прогнозированием цен на акции, основываясь на исторических данных и новостях.

### Архитектура

```mermaid
flowchart TB
    subgraph Parse["Parse"]
        MP["asset_parser"]
    end

    subgraph DB["PostgreSQL"]
        AR[("asset_candle<br>─────────<br>- Сырые данные MOEX<br>- Тикер, OHLCV")]
    end

    subgraph Serve["Serve"]
        WEB["web-interface<br>─────────<br>- ML-модели"]
    end

    USER(("👤 User"))

    MOEX --> MP

    MP --> AR

    AR --> WEB

    WEB --> USER
```

### Пайплайн работы приложения

#### 1. Парсинг и обработка данных

- Парсит "Японские свечи" с MOEX

#### 2. Прогнозирование

По запросу пользователя выдает прогнозируемую стоимость акций.

## Структура приложения

- **`alembic/`** - миграции в БД

- **`config/`** — настройки приложения

- **`core/`** — основная бизнес-логика приложения:
  - `clients/` — клиенты для внешних API
  - `database/` — работа с базой данных (БД)
    - `db_models/` - SQLAlchemy модели таблиц БД. Из них alembic генерирует миграции в БД
    - `repository/` - CRUD операции с таблицами БД
  - `processors/` - обработчики данных
  - `schemas/` - Pydantic схемы данных

- **`daemons/`** — демоны

- **`docs/`** — документация проекта

- **`web/`** — веб-приложение на FastAPI

## Разработка

### Начало работы

1. Установить `uv`
2. Запустить `uv sync`
3. Создать в корне репозитория файл `.env` с содержимым:

```env
DATABASE__HOST=<postgresql IP>
DATABASE__PORT=5432
DATABASE__NAME=stocks_advisor_db
DATABASE__USER=<user>
DATABASE__PASSWORD=<password>
```

Поля `DATABASE__HOST`, `DATABASE__USER` и `DATABASE__PASSWORD` нужно заполнить самостоятельно.

4. Проверить, что приложение стартует:

```bash
uv run fastapi dev app/web/main.py
```

### Как подключиться к БД?

#### С удаленной VM

Если код запускается в VM с доступом к БД, то в `.env` нужно указать IP адрес сервера с БД:

```env
DATABASE__HOST=<postgresql IP>
DATABASE__PORT=5432
DATABASE__NAME=stocks_advisor_db
DATABASE__USER=<user>
DATABASE__PASSWORD=<password>
```

#### Локально

Если код запускается локально на ноутбуке, то нужно сначала прокинуть порт БД через SSH:

```bash
ssh -L 5432:<postgresql IP>:5432 <user>@<server IP> -p <ssh port>
```

И указать в `.env` адрес `localhost`:

```env
DATABASE__HOST=localhost
DATABASE__PORT=5432
DATABASE__NAME=stocks_advisor_db
DATABASE__USER=<user>
DATABASE__PASSWORD=<password>
```

### Как добавить/изменить таблицу БД?

При добавлении новой модели SQLALchemy или при изменнии существующей модели, нужно:

1. Запустить создание миграции (в директории `app/alembic/versions`):

```bash
uv run alembic -c app/alembic.ini revision --autogenerate -m <название_миграции>
# или make alembic-generate-migration name=<название_миграции>
```

2. Проверить созданную миграцию. Нужно соблюдать осторожность с миграциями, которые изменяют/удаляют поля таблиц, иначе есть риск потери данных в БД.

3. Запустить выполнение миграции в БД:

```bash
uv run alembic upgrade head
# или alembic-run-migration
```
