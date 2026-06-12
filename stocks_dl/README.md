# DL модели

Здесь расположен код для полного цикла обучения LSTM модели:

- Загрузка готовых данных из БД
- Генерация признаков
- Перебор гиперпараметров
- Обучение модели
- Демонстрация работы модели
- Анализ ошибок
- Логгирование в MLFlow

## Структура

| Папка | Назначение |
|-------|------------|
| `cli/` | Утилиты для обучения и демонстрации модели |
| `conf/` | Hydra конфиги |
| `data/` | Загрузка и обработка данных |
| `training/` | Обучение модели |
| `workflows/` | Запуск экспериментов, инференс анализ ошибок |
| `viz/` | Отрисовка графиков |
| `artifacts/` | Работа с артефактами из MLFlow |

## Запуск

Команды запускаются с настройками по умолчанию из `conf/config.yaml`:

- Подключение к локальной БД
- Запуск на всех доступных тикерах сразу

### Запуск экспериментов

Запуск локально (локальные MLFlow и БД):

```bash
make dl-experiments-search
# Или так: uv run python -m stocks_dl.cli.dl_experiments
```

Запуск с production контуром (production MLFlow и БД):

```bash
make dl-experiments-search-prod
# Или так: uv run python -m stocks_dl.cli.dl_experiments environment=prod
```

### Обучение лучшей модели

```bash
make dl-experiments-prd
# На продакшне: make dl-experiments-prd-prod
```

### Плановое переобучение

Переобучение на свежих данных; по умолчанию без grid search (`retrain.run_search=false`):

```bash
make dl-experiments-retrain
# На продакшне: make dl-experiments-retrain-prod
# С перебором гиперпараметров: make dl-experiments-retrain-prod retrain.run_search=true
```

### Анализ ошибок модели

```bash
make dl-experiments-analysis
# На продакшне: make dl-experiments-analysis-prod
```

### Демонстрация работы модели

```bash
make dl-demonstration
# На продакшне: make dl-demonstration-prod
```

### Доп. параметры запуска

Для каждой из этих команд можно указать определенный тикер в параметре `TICKER`, например:

```bash
make dl-experiments-search TICKER=SBER
make dl-experiments-prd TICKER=SBER
make dl-experiments-analysis TICKER=SBER
make dl-demonstration TICKER=SBER
```

Другие параметры запуска можно переопределить, запустив команду напрямую. Например:

```bash
uv run python -m stocks_dl.cli.dl_experiments \
  mode=prd \
  experiment=lstm_checkpoint \
  ticker=GAZP \
  training.base_epochs=12 \
  data.enrichments_limit=500000 \
  training.verbose=true
```

Параметры:

- `mode` - режим работы:
  - `search` - перебор гиперпараметров
  - `prd` - обучение модели по лучшим гиперпараметрам
  - `retrain` - плановое переобучение (`retrain.run_search=true` добавляет search перед prd)
  - `analysis` - анализ ошибок модели
- `experiment` - название эксперимента в MLFlow
- `ticker` - тикер. `all` - все тикеры, `[SBER,GAZP]` - определенные тикеры
- `training.base_epochs` - количество эпох
- `training.verbose` - verbose режим

## Артефакты

Артефакты пишутся в **`stocks_dl_runs/`**:

| Подпапка | Содержимое |
|----------|------------|
| `search/` | Результаты работы экспериментов |
| `prd/` | Результаты запуска модели по лучшим гиперпараметрам |
| `demo/` | Результаты демонстрации работы модели |
| `analysis/{ticker}/` | Результаты анализа ошибок модели |
