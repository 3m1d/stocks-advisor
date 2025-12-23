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

- **`api/`** - API-ручки

- **`certs/`** - сертификаты

- **`config/`** — настройки приложения

- **`core/`** — основная бизнес-логика приложения:
  - `auth/` - аутентификация
  - `clients/` — клиенты для внешних API
  - `database/` — работа с базой данных (БД)
    - `db_models/` - SQLAlchemy модели таблиц БД. Из них alembic генерирует миграции в БД
    - `repository/` - CRUD операции с таблицами БД
  - `processors/` - обработчики данных
  - `schemas/` - Pydantic схемы данных

- **`daemons/`** — демоны (фоновые процессы)

- **`docs/`** — документация проекта

- **`scripts/`** — CLI-скрипты

## Разработка

### Локальная разработка

1. Установить `uv`
2. Выполнить `make init`
3. Запустить приложение: `make fastapi-run-dev-local`

### Разработка с удаленной БД

1. Установить `uv`
2. Создать в корне репозитория файл `.env` с содержимым из [.env.example](../.env.example).
3. Сгенерировать ключи: `make generate-jwt-certs`
4. Если БД пустая, нужно применить миграции: `make alembic-run-migration`
5. Запустить приложение:

```bash
uv run fastapi dev app/web/main.py
# или make fastapi-run-dev
```

### Авторизация

Для некоторых API-ручек нужна авторизация. Для этого нужно:

1. Отправить POST запрос на `/api/v1/jwt/login` с username и password в заголовке `Authorization: Basic <username:password в base64>`.
2. Получить JWT токен в ответе.
3. В заголовке запроса добавить `Authorization: Bearer <JWT токен>`.

По умолчанию, у админского аккаунта `username=admin`, `password=admin`. Можно поменять на другой, заменив в файле `.env` значения `JWT__ADMIN_USERNAME` и `JWT__ADMIN_PASSWORD_HASH`.

Чтобы получить хэш пароля, запустите: `make hash-password password=<password>`

### Как подключиться к production БД?

#### На VM

Если код запускается в VM с доступом к БД, то в `.env` нужно указать IP адрес сервера с БД:

```env
DATABASE__HOST=<postgresql IP>
```

#### Локально

Если код запускается на другом устройстве (ноутбук, компьютер), то нужно сначала прокинуть порт БД через SSH:

```bash
ssh -L 54321:<postgresql IP>:5432 <user>@<server IP> -p <ssh port>
```

И указать в `.env` адрес `localhost`:

```env
DATABASE__HOST=localhost
DATABASE__PORT=54321
```

### Как добавить/изменить таблицу БД?

При добавлении новой модели SQLALchemy или при изменнии существующей модели, нужно:

1. Запустить создание миграции (в директории `app/alembic/versions`):

```bash
# Для локальной БД:
make alembic-generate-migration-local name=<название_миграции>
# Для удаленной БД:
make alembic-generate-migration name=<название_миграции>
```

2. Проверить созданную миграцию. Нужно соблюдать осторожность с миграциями, которые изменяют/удаляют поля таблиц, иначе есть риск потери данных в БД.

3. Запустить выполнение миграции в БД:

```bash
# Для локальной БД:
make alembic-run-migration-local
# Для удаленной БД:
make alembic-run-migration
```

### Как пользоваться приложением?

Сначала нужно спарсить данные из MOEX. Это можно сделать, выполнив команду: `make parse-data-from-moex-local`.

После этого можно пользоваться prediction API: `POST /api/v1/predict/forward`.
