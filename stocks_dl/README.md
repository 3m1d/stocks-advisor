# stocks_dl — LSTM pipeline (checkpoint 7)

## Layout

| Папка | Назначение |
|-------|------------|
| `cli/` | `dl_experiments`, `dl_demonstration` (Hydra entrypoints) |
| `conf/` | Hydra: `config.yaml`, `environment/`, `experiment/` |
| `data/` | PostgreSQL → features + tonality |
| `training/` | LSTM model, train loop, dataset/splits |
| `workflows/` | MLflow search/PRD, inference, error analysis |
| `viz/` | Plots for MLflow and notebooks |
| `artifacts/` | Download artifacts from MLflow runs |

## Prod (SSH-туннель)

1. Прокинуть порты (`app/README.md`): MLflow `:5050`, MinIO `:9050`, PostgreSQL `:15432`.
2. Создать `.env` из `.env.example`.
3. `make mlflow-smoke-test-prod`

## Hydra config

Главный файл: `conf/config.yaml`. Группы:

- `environment=prod|local` — `APP_CONFIG` / БД
- `experiment=lstm_checkpoint|sber_lstm_checkpoint` — имя MLflow experiment

### Тикеры

По умолчанию все пять: SBER, TCSG, GAZP, LKOH, ROSN.

```bash
# все тикеры из config
make dl-experiments-search

# один тикер
make dl-experiments-search-ticker TICKER=GAZP

# или напрямую
uv run python -m stocks_dl.cli.dl_experiments mode=search ticker=GAZP
uv run python -m stocks_dl.cli.dl_experiments mode=prd tickers=[SBER,GAZP]
uv run python -m stocks_dl.cli.dl_experiments mode=analysis tickers=all
```

`tickers=all` — то же, что `TICKERS_WITH_NEWS` в `data/pipeline.py`.

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

Пути к артефактам (шаблоны в `paths.*`):

- `{ticker}_search_summary.csv` → `stocks_dl/`
- `demo_{ticker}_test.csv`, `prd_demo_{ticker}_predictions.csv`

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
