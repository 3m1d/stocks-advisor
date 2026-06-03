# stocks_dl — LSTM pipeline (checkpoint 7)

## Layout

| Папка | Назначение |
|-------|------------|
| `cli/` | `dl_experiments`, `dl_demonstration` (Hydra entrypoints) |
| `data/` | PostgreSQL → features + tonality |
| `training/` | LSTM model, train loop, dataset/splits |
| `workflows/` | MLflow search/PRD, inference, error analysis |
| `viz/` | Plots for MLflow and notebooks |
| `artifacts/` | Download artifacts from MLflow runs |
| `conf/` | Hydra `config.yaml` |

## Prod (SSH-туннель)

1. Прокинуть порты (`app/README.md`): MLflow `:5050`, MinIO `:9050`, PostgreSQL `:15432`.
2. Создать `.env` из `.env.example`.
3. `make mlflow-smoke-test-prod`

## CLI (Hydra)

```bash
make dl-experiments-search
make dl-experiments-prd
make dl-experiments-analysis
make dl-demonstration
```

Переопределение: `uv run python -m stocks_dl.cli.dl_experiments mode=prd ticker=SBER prd_run_id=<uuid>`

Запуск из **корня репо**: `python -m stocks_dl.cli.<script>`, импорты `from stocks_dl.workflows.inference import ...`.

## Notebooks

`notebooks/dl_checkpoint/` — `DL_Experiments.ipynb`, `DL_Demonstration.ipynb`.
