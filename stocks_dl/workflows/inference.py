"""Load PRD model from MLflow and run sequence inference."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import mlflow
import mlflow.pytorch
import numpy as np
import pandas as pd
import torch
from mlflow.tracking import MlflowClient

from stocks_dl.constants import TARGET_COLUMN
from stocks_dl.training.dataset import (
    build_predictions_df,
    evaluate_model,
    make_loaders,
    make_test_loader,
    norm_stats_from_checkpoint,
    split_train_test,
    split_train_val,
)
from stocks_dl.workflows.experiment_runner import build_model, get_device


def find_prd_run(
    ticker: str = 'SBER',
    experiment_name: str | None = None,
    run_id: str | None = None,
) -> tuple[str, dict]:
    if run_id:
        client = MlflowClient()
        run = client.get_run(run_id)
        params = run.data.params
        metrics = run.data.metrics
        summary = {
            'run_id': run_id,
            'sequence_length': int(params.get('sequence_length', 16)),
            'batch_size': int(params.get('batch_size', 8)),
            'hidden_size': int(params.get('hidden_size', 8)),
            'num_layers': int(params.get('num_layers', 1)),
            'dropout': float(params.get('dropout', 0.1)),
            'seed': int(params.get('seed', 42)),
            'test_direction_accuracy': metrics.get('test_direction_accuracy'),
        }
        return run_id, summary

    filter_parts = [f"tags.PRD = 'true'", f"tags.ticker = '{ticker}'"]
    if experiment_name:
        exp = mlflow.get_experiment_by_name(experiment_name)
        if exp is None:
            raise RuntimeError(f'Experiment not found: {experiment_name}')
        experiment_ids = [exp.experiment_id]
    else:
        experiment_ids = None

    runs = mlflow.search_runs(
        experiment_ids=experiment_ids,
        filter_string=' AND '.join(filter_parts),
        order_by=['attributes.start_time DESC'],
        max_results=10,
    )
    if runs.empty:
        runs = mlflow.search_runs(
            experiment_ids=experiment_ids,
            filter_string=f"tags.stage = 'prd' AND tags.ticker = '{ticker}'",
            order_by=['attributes.start_time DESC'],
            max_results=10,
        )
    if runs.empty:
        raise RuntimeError(f'PRD run not found for ticker={ticker}')

    row = runs.iloc[0]
    run_id = row['run_id']
    summary = {
        'run_id': run_id,
        'sequence_length': int(row.get('params.sequence_length', 16)),
        'batch_size': int(row.get('params.batch_size', 8)),
        'hidden_size': int(row.get('params.hidden_size', 8)),
        'num_layers': int(row.get('params.num_layers', 1)),
        'dropout': float(row.get('params.dropout', 0.1)),
        'seed': int(row.get('params.seed', 42)),
    }
    return run_id, summary


def load_model_from_checkpoint(checkpoint_path: Path):
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
    model = build_model(checkpoint['input_size'], checkpoint)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(get_device())
    model.eval()
    return model, checkpoint


def load_prd_model(run_id: str):
    client = MlflowClient()
    try:
        local_ckpt = client.download_artifacts(run_id, 'checkpoint.pt')
        ckpt_path = Path(local_ckpt)
        if ckpt_path.is_dir():
            candidates = list(ckpt_path.glob('checkpoint.pt'))
            ckpt_path = candidates[0] if candidates else ckpt_path / 'checkpoint.pt'
        return load_model_from_checkpoint(Path(ckpt_path))
    except Exception:
        model = mlflow.pytorch.load_model(f'runs:/{run_id}/model')
        model.to(get_device())
        model.eval()
        return model, {}


def prepare_test_window(
    test_df: pd.DataFrame,
    sequence_length: int,
    last_days: int,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Keep enough test rows for LSTM context; return cutoff for the last N calendar days."""
    df = test_df.sort_values('begin').reset_index(drop=True)
    df['begin'] = pd.to_datetime(df['begin'])
    cutoff = df['begin'].max() - pd.Timedelta(days=last_days)
    mask = df['begin'] > cutoff
    if not mask.any():
        return df, cutoff
    first_idx = int(np.flatnonzero(mask.to_numpy())[0])
    start_idx = max(0, first_idx - (sequence_length - 1))
    return df.iloc[start_idx:].copy(), cutoff


def filter_predictions_last_days(
    predictions_df: pd.DataFrame,
    cutoff: pd.Timestamp,
) -> pd.DataFrame:
    out = predictions_df.copy()
    out['begin'] = pd.to_datetime(out['begin'])
    return out.loc[out['begin'] > cutoff].reset_index(drop=True)


def predict_from_dataframes(
    model,
    test_df: pd.DataFrame,
    sequence_length: int,
    batch_size: int,
    *,
    checkpoint: dict | None = None,
    train_df: pd.DataFrame | None = None,
    val_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Run test inference. Uses checkpoint X_mean/X_std when available (PRD demo)."""
    norm = norm_stats_from_checkpoint(checkpoint) if checkpoint else None
    if norm is not None:
        feature_names, X_mean, X_std = norm
        test_loader = make_test_loader(
            test_df,
            sequence_length,
            batch_size,
            feature_names=feature_names,
            X_mean=X_mean,
            X_std=X_std,
        )
    else:
        if train_df is None or val_df is None:
            raise ValueError(
                'PRD checkpoint has no feature_names/X_mean/X_std; '
                'pass train_df and val_df or re-run PRD to log checkpoint.pt.'
            )
        _, _, _, _, _, test_loader = make_loaders(
            train_df, val_df, test_df, sequence_length, batch_size
        )
    metrics, y_true, y_pred = evaluate_model(model, test_loader)
    predictions_df = build_predictions_df(test_df, y_true, y_pred, sequence_length)
    return predictions_df, metrics


def predict_test_csv(
    demo_csv: Path | str,
    features_df: pd.DataFrame,
    prd_run_id: str | None = None,
    prd_summary: dict | None = None,
    ticker: str = 'SBER',
    experiment_name: str | None = None,
    test_size: float = 0.2,
    val_size: float = 0.2,
    final_val_size: float = 0.15,
) -> pd.DataFrame:
    if prd_run_id is None or prd_summary is None:
        prd_run_id, prd_summary = find_prd_run(ticker, experiment_name)

    model, checkpoint = load_prd_model(prd_run_id)
    seq_len = int(prd_summary['sequence_length'])
    batch_size = int(prd_summary['batch_size'])
    test_df = _resolve_test_df(
        features_df, demo_csv, test_size=test_size, val_size=val_size
    )
    train_df, val_df = _prd_train_val_fallback(
        features_df, checkpoint, test_size=test_size, val_size=val_size, final_val_size=final_val_size
    )
    predictions_df, _ = predict_from_dataframes(
        model,
        test_df,
        seq_len,
        batch_size,
        checkpoint=checkpoint,
        train_df=train_df,
        val_df=val_df,
    )
    return predictions_df


def _resolve_test_df(
    features_df: pd.DataFrame,
    demo_csv: Path | str | None,
    *,
    test_size: float,
    val_size: float,
) -> pd.DataFrame:
    if demo_csv and Path(demo_csv).exists():
        test_df = pd.read_csv(demo_csv)
        if 'begin' in test_df.columns:
            test_df['begin'] = pd.to_datetime(test_df['begin'])
        return test_df
    _, _, test_df = split_train_test(
        features_df.copy(), target_column=TARGET_COLUMN, test_size=test_size, val_size=val_size
    )
    return test_df


def _prd_train_val_fallback(
    features_df: pd.DataFrame,
    checkpoint: dict,
    *,
    test_size: float,
    val_size: float,
    final_val_size: float,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Only needed when checkpoint lacks saved normalization stats."""
    if norm_stats_from_checkpoint(checkpoint):
        return None, None
    train_df, val_df, _ = split_train_test(
        features_df.copy(), target_column=TARGET_COLUMN, test_size=test_size, val_size=val_size
    )
    prd_source = pd.concat([train_df, val_df]).sort_values('begin').reset_index(drop=True)
    return split_train_val(prd_source, TARGET_COLUMN, val_size=final_val_size)


def run_demo_inference(
    features_df: pd.DataFrame,
    output_path: Path | str,
    ticker: str = 'SBER',
    experiment_name: str | None = None,
    demo_csv: Path | str | None = None,
    prd_run_id: str | None = None,
    test_size: float = 0.2,
    val_size: float = 0.2,
    final_val_size: float = 0.15,
) -> dict[str, Any]:
    prd_run_id, prd_summary = find_prd_run(ticker, experiment_name, prd_run_id)
    model, checkpoint = load_prd_model(prd_run_id)
    seq_len = int(prd_summary['sequence_length'])
    batch_size = int(prd_summary['batch_size'])

    test_df = _resolve_test_df(features_df, demo_csv, test_size=test_size, val_size=val_size)
    train_df, val_df = _prd_train_val_fallback(
        features_df, checkpoint, test_size=test_size, val_size=val_size, final_val_size=final_val_size
    )

    predictions_df, metrics = predict_from_dataframes(
        model,
        test_df,
        seq_len,
        batch_size,
        checkpoint=checkpoint,
        train_df=train_df,
        val_df=val_df,
    )
    out = Path(output_path)
    predictions_df.to_csv(out, index=False)
    return {
        'run_id': prd_run_id,
        'summary': prd_summary,
        'metrics': metrics,
        'predictions_df': predictions_df,
        'output_path': str(out),
        'checkpoint_loaded': bool(checkpoint),
    }
