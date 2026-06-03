# MLflow DL pipeline (checkpoint 7)

## Модули

| Файл | Назначение |
|------|------------|
| `experiment_runner.py` | grid search, PRD run (тег `PRD=true`), логирование в MLflow |
| `error_analysis.py` | baseline, robustness, top errors, confusion matrix |
| `inference.py` | загрузка PRD-модели и sequence inference |
| `data_pipeline.py` | данные из PostgreSQL + tonality features |
| `dl_experiments.py` | CLI: `mode=search\|prd\|analysis` |
| `dl_demonstration.py` | CLI: демо-предикт |

## Prod (SSH-туннель)

1. Прокинуть порты (`app/README.md`): MLflow `:5050`, MinIO `:9050`, PostgreSQL `:15432`.
2. Создать `.env` из `.env.example`.
3. `make mlflow-smoke-test-prod`

## CLI (Hydra)

```bash
# Grid (~50 runs, долго)
make dl-experiments-search

# Финальная PRD-модель
make dl-experiments-prd

# Анализ ошибок
make dl-experiments-analysis

# Демо-предикт
make dl-demonstration
```

Переопределение: `uv run python -m stocks_dl.dl_experiments mode=prd ticker=SBER prd_run_id=<uuid>`

Запуск как у `app.daemons`: **из корня репо**, `python -m stocks_dl.<модуль>`, импорты `from stocks_dl....`. Отдельная регистрация пакета в `pyproject.toml` не нужна — достаточно `stocks_dl/__init__.py` и cwd = корень репо.

В ноутбуке: `sys.path.insert(0, REPO_ROOT)` (см. `DL_Demonstration.ipynb`), затем `from stocks_dl.inference import ...`.

## Notebooks

- `DL_Experiments.ipynb` — полный цикл (данные → search → PRD → analysis)
- `DL_Demonstration.ipynb` — только загрузка PRD и инференс
