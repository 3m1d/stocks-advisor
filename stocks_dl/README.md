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

### Запуск экспериментов

Базовая команда:

```bash
uv run python -m stocks_dl.cli.dl_experiments
```

Можно переопределить

```bash
# все тикеры из config
make dl-experiments-search
# Либо так: make dl-experiments-search tickers=all

# один тикер
make dl-experiments-search-ticker TICKER=GAZP

# выбор определенного тикера, с определенной стадией
uv run python -m stocks_dl.cli.dl_experiments mode=search ticker=GAZP # Перебор гиперпараметров для тикера GAZP
uv run python -m stocks_dl.cli.dl_experiments mode=prd tickers=[SBER,GAZP] # Обучение модели по лучшим гиперпараметрам, тикеры SBER,GAZP
uv run python -m stocks_dl.cli.dl_experiments mode=analysis tickers=all # Анализ ошибок модели, для всех тикеров
```

### Переопределения

```bash
uv run python -m stocks_dl.cli.dl_experiments \
  mode=prd \
  experiment=lstm_checkpoint \
  ticker=GAZP \
  training.base_epochs=12 \
  data.enrichments_limit=500000 \
  training.verbose=true
```

Артефакты пишутся в **`stocks_dl_runs/`** (корень репо, не в пакет `stocks_dl/`):

| Подпапка | Содержимое |
|----------|------------|
| `search/` | `{ticker}_search_summary.csv` |
| `prd/` | `demo_{ticker}_test.csv` (снимок test при PRD) |
| `demo/` | `prd_demo_{ticker}_predictions.csv` + `.png` |
| `analysis/{ticker}/` | `prd_predictions.png` (локальная копия из analysis) |

Переопределение корня: `paths.runs_dir=my_outputs`

Hydra пишет метаданные run в `outputs/dl/<mode>/<timestamp>/` (рабочая директория — корень репо, `hydra.job.chdir: false`).

## CLI (Makefile)

```bash
make dl-experiments-search      # grid search, все тикеры
make dl-experiments-prd         # PRD по каждому тикеру
make dl-experiments-analysis
make dl-demonstration
```

## Notebooks

`notebooks/dl_checkpoint/` — `DL_Experiments.ipynb`, `DL_Demonstration.ipynb`.

Запуск из **корня репо**: `python -m stocks_dl.cli.<script>`.
