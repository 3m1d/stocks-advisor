"""CLI for DL experiments: search, PRD retrain, error analysis."""

from __future__ import annotations

import asyncio
from pathlib import Path

import hydra
import mlflow
import pandas as pd
from omegaconf import DictConfig

from .constants import TARGET_COLUMN
from .data_pipeline import (
    attach_tonality,
    build_features_by_ticker,
    load_candles_by_ticker,
    load_enrichments,
)
from .env_setup import configure_environment
from .error_analysis import run_error_analysis
from .experiment_runner import (
    load_summary_from_mlflow,
    run_prd,
    run_search,
    select_best_row,
)
from .inference import find_prd_run
from .temporal_dataset import split_train_test, split_train_val

PACKAGE_DIR = Path(__file__).resolve().parent


async def load_features(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    candles = await load_candles_by_ticker()
    enrichments = await load_enrichments()
    features = build_features_by_ticker(candles)
    features = attach_tonality(features, enrichments, tickers=[ticker])
    return features[ticker].copy(), enrichments


@hydra.main(version_base=None, config_path='conf', config_name='config')
def main(cfg: DictConfig) -> None:
    configure_environment(cfg.environment, cfg.experiment_name)
    mlflow.set_experiment(cfg.experiment_name)

    features_df, enrichments_df = asyncio.run(load_features(cfg.ticker))
    mode = cfg.mode

    if mode == 'search':
        summary_df = run_search(
            features_df=features_df,
            ticker=cfg.ticker,
            experiment_name=cfg.experiment_name,
            test_size=cfg.data.test_size,
            val_size=cfg.data.val_size,
            seed=cfg.seed,
            batch_size=cfg.training.batch_size,
            weight_decay=cfg.training.weight_decay,
            num_epochs=cfg.training.base_epochs,
            show_plots=cfg.training.show_plots,
        )
        print(summary_df.head(10))
        return

    if mode == 'prd':
        summary_path = PACKAGE_DIR / f'{cfg.ticker.lower()}_search_summary.csv'
        if summary_path.exists():
            summary_df = pd.read_csv(summary_path)
        else:
            print('Loading search summary from MLflow...')
            summary_df = load_summary_from_mlflow(cfg.experiment_name, cfg.ticker)
        prd_summary, prd_run_id, _, _, _ = run_prd(
            features_df=features_df,
            summary_df=summary_df,
            experiment_name=cfg.experiment_name,
            test_size=cfg.data.test_size,
            val_size=cfg.data.val_size,
            final_val_size=cfg.data.final_val_size,
            seed=cfg.seed,
            show_plots=cfg.training.show_plots,
        )
        print('PRD run_id:', prd_run_id)
        print('Best search:', select_best_row(summary_df)['run_name'])
        print(prd_summary)
        return

    if mode == 'analysis':
        prd_run_id = cfg.prd_run_id
        if not prd_run_id:
            prd_run_id, prd_summary = find_prd_run(cfg.ticker, cfg.experiment_name)
        else:
            _, prd_summary = find_prd_run(cfg.ticker, cfg.experiment_name, run_id=prd_run_id)

        train_df, val_df, test_df = split_train_test(
            features_df, TARGET_COLUMN, cfg.data.test_size, cfg.data.val_size
        )
        prd_source = pd.concat([train_df, val_df]).sort_values('begin').reset_index(drop=True)
        prd_train_df, prd_val_df = split_train_val(
            prd_source, TARGET_COLUMN, cfg.data.final_val_size
        )

        result = run_error_analysis(
            prd_run_id=prd_run_id,
            prd_run_summary=prd_summary,
            prd_train_df=prd_train_df,
            prd_val_df=prd_val_df,
            test_df=test_df,
            ticker=cfg.ticker,
            enrichments_df=enrichments_df,
            experiment_name=cfg.experiment_name,
        )
        print(result['error_summary_df'])
        print(result['robustness_df'])
        return

    raise ValueError(f'Unknown mode: {mode}. Use search, prd, or analysis.')


if __name__ == '__main__':
    main()
