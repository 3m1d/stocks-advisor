"""CLI for DL experiments: search, PRD retrain, error analysis (multi-ticker via Hydra)."""

from __future__ import annotations

import hydra
import mlflow
import pandas as pd
from omegaconf import DictConfig

from stocks_dl.cli.config_helpers import artifact_path, data_cfg, resolve_tickers, training_cfg
from stocks_dl.constants import TARGET_COLUMN
from stocks_dl.data.pipeline import load_features_multi
from stocks_dl.env_setup import configure_environment
from stocks_dl.paths import PKG_ROOT
from stocks_dl.training.dataset import split_train_test, split_train_val
from stocks_dl.workflows.error_analysis import run_error_analysis
from stocks_dl.workflows.experiment_runner import (
    load_summary_from_mlflow,
    run_prd,
    run_search,
    select_best_row,
)
from stocks_dl.workflows.inference import find_prd_run

HYDRA_CONFIG_PATH = str(PKG_ROOT / 'conf')


def _summary_path(cfg: DictConfig, ticker: str) -> pd.DataFrame | None:
    path = artifact_path(cfg, cfg.paths.search_summary_template, ticker)
    if path.exists():
        return pd.read_csv(path)
    return None


def _run_search(cfg: DictConfig, ticker: str, features_df: pd.DataFrame) -> pd.DataFrame:
    data = data_cfg(cfg)
    train = training_cfg(cfg)
    print(f'\n=== [{ticker}] grid search ({cfg.experiment_name}) ===')
    return run_search(
        features_df=features_df,
        ticker=ticker,
        experiment_name=cfg.experiment_name,
        test_size=data['test_size'],
        val_size=data['val_size'],
        seed=cfg.seed,
        batch_size=train['batch_size'],
        weight_decay=train['weight_decay'],
        num_epochs=train['base_epochs'],
        show_plots=train['show_plots'],
        verbose=train['verbose'],
    )


def _run_prd(cfg: DictConfig, ticker: str, features_df: pd.DataFrame) -> None:
    data = data_cfg(cfg)
    train = training_cfg(cfg)
    summary_df = _summary_path(cfg, ticker)
    if summary_df is None:
        print(f'[{ticker}] Loading search summary from MLflow...')
        summary_df = load_summary_from_mlflow(cfg.experiment_name, ticker)
    print(f'\n=== [{ticker}] PRD train (best: {select_best_row(summary_df)["run_name"]}) ===')
    prd_summary, prd_run_id, _, _, _ = run_prd(
        features_df=features_df,
        summary_df=summary_df,
        experiment_name=cfg.experiment_name,
        test_size=data['test_size'],
        val_size=data['val_size'],
        final_val_size=data['final_val_size'],
        seed=cfg.seed,
        show_plots=train['show_plots'],
        verbose=train['verbose'],
    )
    print(f'[{ticker}] PRD run_id:', prd_run_id)
    print(prd_summary)


def _run_analysis(
    cfg: DictConfig,
    ticker: str,
    features_df: pd.DataFrame,
    enrichments_df: pd.DataFrame,
) -> None:
    data = data_cfg(cfg)
    prd_run_id = cfg.prd_run_id
    if not prd_run_id:
        prd_run_id, prd_summary = find_prd_run(ticker, cfg.experiment_name)
    else:
        _, prd_summary = find_prd_run(ticker, cfg.experiment_name, run_id=prd_run_id)

    train_df, val_df, test_df = split_train_test(
        features_df, TARGET_COLUMN, data['test_size'], data['val_size']
    )
    prd_source = pd.concat([train_df, val_df]).sort_values('begin').reset_index(drop=True)
    prd_train_df, prd_val_df = split_train_val(
        prd_source, TARGET_COLUMN, data['final_val_size']
    )

    print(f'\n=== [{ticker}] error analysis (PRD {prd_run_id}) ===')
    result = run_error_analysis(
        prd_run_id=prd_run_id,
        prd_run_summary=prd_summary,
        prd_train_df=prd_train_df,
        prd_val_df=prd_val_df,
        test_df=test_df,
        ticker=ticker,
        enrichments_df=enrichments_df,
        experiment_name=cfg.experiment_name,
    )
    print(result['error_summary_df'])
    print(result['robustness_df'])


@hydra.main(version_base=None, config_path=HYDRA_CONFIG_PATH, config_name='config')
def main(cfg: DictConfig) -> None:
    tickers = resolve_tickers(cfg)
    mode = cfg.mode
    train = training_cfg(cfg)
    data = data_cfg(cfg)

    configure_environment(
        cfg.environment,
        cfg.experiment_name,
        suppress_mlflow_urls=train.get('suppress_mlflow_urls', True),
    )
    mlflow.set_experiment(cfg.experiment_name)

    print(f'Mode: {mode} | tickers: {tickers} | experiment: {cfg.experiment_name}')
    features_by_ticker, enrichments_df = load_features_multi(
        tickers,
        enrichments_limit=data.get('enrichments_limit'),
    )

    if mode == 'search':
        for ticker in tickers:
            _run_search(cfg, ticker, features_by_ticker[ticker])
        return

    if mode == 'prd':
        for ticker in tickers:
            _run_prd(cfg, ticker, features_by_ticker[ticker])
        return

    if mode == 'analysis':
        for ticker in tickers:
            _run_analysis(cfg, ticker, features_by_ticker[ticker], enrichments_df)
        return

    raise ValueError(f'Unknown mode: {mode}. Use search, prd, or analysis.')


if __name__ == '__main__':
    main()
