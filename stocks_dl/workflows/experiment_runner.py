from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from itertools import product
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import pandas as pd
import torch
from torch import optim

from stocks_dl.constants import DEFAULT_EXPERIMENT_NAME, DEFAULT_SEED, DEFAULT_TICKER, TARGET_COLUMN
from stocks_dl.data.pipeline import build_data_provenance
from stocks_dl.paths import runs_artifact_path
from stocks_dl.training.dataset import (
    build_predictions_df,
    evaluate_model,
    make_loaders,
    set_seed,
    split_train_test,
    split_train_val,
)
from stocks_dl.training.model import StockLSTMRegressor
from stocks_dl.training.train import train
from stocks_dl.viz.plotting import save_learning_curves, save_prediction_plot

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def get_device() -> torch.device:
    return DEVICE


def build_model(input_size: int, cfg: dict) -> StockLSTMRegressor:
    return StockLSTMRegressor(
        input_size=input_size,
        hidden_size=cfg['hidden_size'],
        num_layers=cfg['num_layers'],
        dropout=cfg['dropout'],
    ).to(DEVICE)


def build_hyperparameter_grid(
    ticker: str,
    seed: int,
    batch_size: int,
    weight_decay: float,
    num_epochs: int,
    run_name_prefix: str | None = None,
) -> list[dict]:
    prefix = run_name_prefix or f'{ticker.lower()}_exp'
    configs = []
    depth_grid_main = list(product([5, 7, 9, 12, 16], [8, 16, 32, 64], [1, 2]))
    depth_grid_deep = list(product([7, 9], [16, 32, 64, 96, 128], [3]))
    full_grid = depth_grid_main + depth_grid_deep
    for idx, (sequence_length, hidden_size, num_layers) in enumerate(full_grid, start=1):
        if num_layers == 1:
            dropout = 0.10 if hidden_size <= 32 else 0.15
            learning_rate = 6e-4 if hidden_size <= 32 else 4e-4
        elif num_layers == 2:
            dropout = 0.25 if hidden_size <= 32 else 0.30
            learning_rate = 4e-4 if hidden_size <= 32 else 3e-4
        else:
            dropout = 0.35 if hidden_size <= 64 else 0.40
            learning_rate = 3e-4 if hidden_size <= 64 else 2e-4
        configs.append(
            {
                'run_name': f'{prefix}_{idx:02d}',
                'ticker': ticker,
                'seed': seed,
                'sequence_length': sequence_length,
                'hidden_size': hidden_size,
                'num_layers': num_layers,
                'dropout': dropout,
                'learning_rate': learning_rate,
                'batch_size': batch_size,
                'weight_decay': weight_decay,
                'num_epochs': num_epochs,
            }
        )
    return configs


def select_best_row(summary_df: pd.DataFrame) -> pd.Series:
    return summary_df.sort_values(
        ['val_direction_accuracy', 'val_r2', 'val_rmse'],
        ascending=[False, False, True],
    ).iloc[0]


def run_experiment(
    cfg: dict,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    stage: str = 'search',
    log_model: bool = False,
    show_plots: bool = False,
    verbose: bool = False,
    data_provenance: dict | None = None,
    full_df: pd.DataFrame | None = None,
) -> tuple[dict, str]:
    set_seed(cfg.get('seed', DEFAULT_SEED))
    train_dataset, val_dataset, test_dataset, train_loader, val_loader, test_loader = make_loaders(
        train_df, val_df, test_df, cfg['sequence_length'], cfg['batch_size']
    )
    model = build_model(train_dataset.num_features, cfg)
    optimizer = optim.Adam(model.parameters(), lr=cfg['learning_rate'], weight_decay=cfg['weight_decay'])

    with tempfile.TemporaryDirectory() as tmpdir, mlflow.start_run(run_name=cfg['run_name']) as run:
        tmpdir = Path(tmpdir)
        tags = {
            'ticker': cfg['ticker'],
            'stage': stage,
            'model_family': 'LSTM',
            'target': TARGET_COLUMN,
            'seed': str(cfg['seed']),
        }
        if stage == 'prd':
            tags['PRD'] = 'true'
        mlflow.set_tags(tags)

        for key in (
            'sequence_length',
            'hidden_size',
            'num_layers',
            'dropout',
            'learning_rate',
            'batch_size',
            'num_epochs',
            'weight_decay',
            'seed',
        ):
            mlflow.log_param(key, cfg[key])

        mlflow.log_dict(cfg, 'config.json')
        if data_provenance is not None:
            mlflow.log_dict(data_provenance, 'data_provenance.json')

        train_losses, val_losses, val_history = train(
            model=model,
            optimizer=optimizer,
            scheduler=None,
            train_loader=train_loader,
            val_loader=val_loader,
            num_epochs=cfg['num_epochs'],
            show_plots=show_plots,
            verbose=verbose,
        )
        train_metrics, _, _ = evaluate_model(model, train_loader)
        val_metrics, _, _ = evaluate_model(model, val_loader)
        test_metrics, test_targets, test_preds = evaluate_model(model, test_loader)

        history_df = pd.DataFrame(
            {
                'epoch': np.arange(1, len(train_losses) + 1),
                'train_loss': train_losses,
                'val_loss': val_losses,
                'val_mae': val_history['mae'],
                'val_rmse': val_history['rmse'],
                'val_r2': val_history['r2'],
                'val_direction_accuracy': val_history['direction_accuracy'],
            }
        )
        history_df.to_csv(tmpdir / 'history.csv', index=False)
        save_learning_curves(train_losses, val_losses, val_history, tmpdir / 'learning_curves.png')

        predictions_df = build_predictions_df(test_df, test_targets, test_preds, cfg['sequence_length'])
        predictions_df.to_csv(tmpdir / 'test_predictions.csv', index=False)
        save_prediction_plot(predictions_df, tmpdir / 'predictions.png', f'{cfg["ticker"]} predictions')

        if stage == 'prd':
            demo_name = f'demo_{cfg["ticker"].lower()}_test.csv'
            test_df.to_csv(tmpdir / demo_name, index=False)
            test_df.to_csv(
                runs_artifact_path('prd', demo_name),
                index=False,
            )

        summary = {
            'run_id': run.info.run_id,
            'run_name': cfg['run_name'],
            'ticker': cfg['ticker'],
            'sequence_length': cfg['sequence_length'],
            'hidden_size': cfg['hidden_size'],
            'num_layers': cfg['num_layers'],
            'dropout': cfg['dropout'],
            'learning_rate': cfg['learning_rate'],
            'batch_size': cfg['batch_size'],
            'num_epochs': cfg['num_epochs'],
            'seed': cfg['seed'],
            'train_mae': float(train_metrics['mae']),
            'train_rmse': float(train_metrics['rmse']),
            'train_r2': float(train_metrics['r2']),
            'train_direction_accuracy': float(train_metrics['direction_accuracy']),
            'val_mae': float(val_metrics['mae']),
            'val_rmse': float(val_metrics['rmse']),
            'val_r2': float(val_metrics['r2']),
            'val_direction_accuracy': float(val_metrics['direction_accuracy']),
            'test_mae': float(test_metrics['mae']),
            'test_rmse': float(test_metrics['rmse']),
            'test_r2': float(test_metrics['r2']),
            'test_direction_accuracy': float(test_metrics['direction_accuracy']),
            'config_json': json.dumps(cfg, ensure_ascii=False),
        }
        mlflow.log_metrics(
            {k: v for k, v in summary.items() if isinstance(v, (int, float, np.floating)) and k != 'seed'}
        )
        mlflow.log_artifacts(str(tmpdir))

        if log_model:
            checkpoint = {
                'model_state_dict': deepcopy(model).cpu().state_dict(),
                'input_size': train_dataset.num_features,
                'hidden_size': cfg['hidden_size'],
                'num_layers': cfg['num_layers'],
                'dropout': cfg['dropout'],
                'sequence_length': cfg['sequence_length'],
                'feature_names': train_dataset.feature_names,
                'X_mean': train_dataset.X_mean.tolist(),
                'X_std': train_dataset.X_std.tolist(),
                'summary': summary,
            }
            torch.save(checkpoint, tmpdir / 'checkpoint.pt')
            mlflow.pytorch.log_model(deepcopy(model).cpu(), 'model')
            mlflow.log_artifact(str(tmpdir / 'checkpoint.pt'))

        if not verbose and not show_plots:
            print(
                f'[{cfg["run_name"]}] val_dir_acc={summary["val_direction_accuracy"]:.4f} '
                f'test_dir_acc={summary["test_direction_accuracy"]:.4f}'
            )

        return summary, run.info.run_id


def run_search(
    features_df: pd.DataFrame,
    ticker: str,
    experiment_name: str,
    test_size: float,
    val_size: float,
    seed: int,
    batch_size: int,
    weight_decay: float,
    num_epochs: int,
    show_plots: bool = False,
    verbose: bool = False,
) -> pd.DataFrame:
    mlflow.set_experiment(experiment_name)
    train_df, val_df, test_df = split_train_test(
        features_df.copy(), target_column=TARGET_COLUMN, test_size=test_size, val_size=val_size
    )
    configs = build_hyperparameter_grid(ticker, seed, batch_size, weight_decay, num_epochs)
    rows = []
    total = len(configs)
    for idx, cfg in enumerate(configs, start=1):
        if not verbose and not show_plots:
            print(f'Search {idx}/{total}: {cfg["run_name"]}', flush=True)
        summary, _ = run_experiment(
            cfg=cfg,
            train_df=train_df,
            val_df=val_df,
            test_df=test_df,
            stage='search',
            log_model=False,
            show_plots=show_plots,
            verbose=verbose,
        )
        rows.append(summary)
    summary_df = (
        pd.DataFrame(rows)
        .sort_values(['val_direction_accuracy', 'val_r2', 'val_rmse'], ascending=[False, False, True])
        .reset_index(drop=True)
    )
    out_csv = runs_artifact_path('search', f'{ticker.lower()}_search_summary.csv')
    summary_df.to_csv(out_csv, index=False)
    return summary_df


def run_prd(
    features_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    experiment_name: str,
    test_size: float,
    val_size: float,
    final_val_size: float,
    seed: int,
    show_plots: bool = False,
    verbose: bool = False,
) -> tuple[dict, str, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    mlflow.set_experiment(experiment_name)
    train_df, val_df, test_df = split_train_test(
        features_df.copy(), target_column=TARGET_COLUMN, test_size=test_size, val_size=val_size
    )
    best_row = select_best_row(summary_df)
    best_cfg = json.loads(best_row['config_json'])
    prd_source_df = pd.concat([train_df, val_df]).sort_values('begin').reset_index(drop=True)
    prd_train_df, prd_val_df = split_train_val(prd_source_df, TARGET_COLUMN, val_size=final_val_size)
    provenance = build_data_provenance(
        best_cfg['ticker'],
        features_df,
        prd_train_df,
        prd_val_df,
        test_df,
        test_size,
        val_size,
        final_val_size,
    )
    provenance['best_search_run_id'] = best_row['run_id']
    provenance['best_search_val_direction_accuracy'] = float(best_row['val_direction_accuracy'])
    provenance['selection_criteria'] = 'val_direction_accuracy, val_r2, val_rmse'

    prd_cfg = {
        **best_cfg,
        'num_epochs': best_cfg['num_epochs'],
        'run_name': f'{best_cfg["ticker"].lower()}_prd_{best_row["run_name"]}',
    }
    prd_summary, prd_run_id = run_experiment(
        cfg=prd_cfg,
        train_df=prd_train_df,
        val_df=prd_val_df,
        test_df=test_df,
        stage='prd',
        log_model=True,
        show_plots=show_plots,
        verbose=verbose,
        data_provenance=provenance,
        full_df=features_df,
    )
    prd_summary['best_search_run_id'] = best_row['run_id']
    prd_summary['best_search_val_direction_accuracy'] = float(best_row['val_direction_accuracy'])
    prd_summary['best_search_val_r2'] = float(best_row['val_r2'])
    prd_summary['best_search_val_rmse'] = float(best_row['val_rmse'])
    prd_summary['best_search_val_mae'] = float(best_row['val_mae'])
    return prd_summary, prd_run_id, prd_train_df, prd_val_df, test_df


def load_summary_from_mlflow(experiment_name: str, ticker: str) -> pd.DataFrame:
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise RuntimeError(f'Experiment not found: {experiment_name}')
    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string=f"tags.stage = 'search' AND tags.ticker = '{ticker}'",
        max_results=500,
    )
    if runs.empty:
        raise RuntimeError(f'No search runs for ticker {ticker}')
    rows = []
    for _, row in runs.iterrows():
        rows.append(
            {
                'run_id': row['run_id'],
                'run_name': row.get('tags.mlflow.runName', row['run_id']),
                'val_direction_accuracy': row.get('metrics.val_direction_accuracy'),
                'val_r2': row.get('metrics.val_r2'),
                'val_rmse': row.get('metrics.val_rmse'),
                'val_mae': row.get('metrics.val_mae'),
                'config_json': json.dumps(
                    {
                        'run_name': row.get('tags.mlflow.runName', ''),
                        'ticker': ticker,
                        'seed': int(row.get('params.seed', DEFAULT_SEED)),
                        'sequence_length': int(row['params.sequence_length']),
                        'hidden_size': int(row['params.hidden_size']),
                        'num_layers': int(row['params.num_layers']),
                        'dropout': float(row['params.dropout']),
                        'learning_rate': float(row['params.learning_rate']),
                        'batch_size': int(row['params.batch_size']),
                        'weight_decay': float(row['params.weight_decay']),
                        'num_epochs': int(row['params.num_epochs']),
                    }
                ),
            }
        )
    return pd.DataFrame(rows)
