from __future__ import annotations

import mlflow
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from mlflow.tracking import MlflowClient

from stocks_dl.constants import CATBOOST_EXPERIMENT_NAME, TARGET_COLUMN


def find_catboost_run(
    ticker: str = 'SBER',
    experiment_name: str | None = CATBOOST_EXPERIMENT_NAME,
    run_id: str | None = None,
) -> tuple[str, dict]:
    """Находит production CatBoost run: PRD-тег или лучший search по val_direction_accuracy."""
    if run_id:
        client = MlflowClient()
        run = client.get_run(run_id)
        return run_id, _summary_from_run(run.data.params, run.data.metrics, run_id)

    experiment_ids = _experiment_ids(experiment_name)
    filter_parts = [f"tags.PRD = 'true'", f"tags.ticker = '{ticker}'"]
    runs = mlflow.search_runs(
        experiment_ids=experiment_ids,
        filter_string=' AND '.join(filter_parts),
        order_by=['attributes.start_time DESC'],
        max_results=1,
    )
    if runs.empty:
        runs = mlflow.search_runs(
            experiment_ids=experiment_ids,
            filter_string=f"tags.stage = 'prd' AND tags.ticker = '{ticker}'",
            order_by=['attributes.start_time DESC'],
            max_results=1,
        )
    if runs.empty:
        runs = mlflow.search_runs(
            experiment_ids=experiment_ids,
            filter_string=f"tags.ticker = '{ticker}'",
            order_by=[
                'metrics.val_direction_accuracy DESC',
                'metrics.val_r2 DESC',
                'metrics.val_rmse ASC',
            ],
            max_results=1,
        )
    if runs.empty:
        raise RuntimeError(f'CatBoost run not found for ticker={ticker}')

    row = runs.iloc[0]
    run_id = row['run_id']
    summary = {
        'run_id': run_id,
        'variant': row.get('params.variant'),
        'feature_count': int(row.get('params.feature_count', 0) or 0),
        'val_direction_accuracy': row.get('metrics.val_direction_accuracy'),
        'test_direction_accuracy': row.get('metrics.test_direction_accuracy'),
    }
    return run_id, summary


def load_catboost_model(run_id: str) -> CatBoostRegressor:
    return mlflow.catboost.load_model(f'runs:/{run_id}/model')


def predict_catboost_latest(model: CatBoostRegressor, features_df: pd.DataFrame) -> float:
    """Прогноз изменения цены (%) на последней доступной точке."""
    if features_df.empty:
        raise ValueError('features_df is empty')

    feature_cols = list(model.feature_names_)
    if not feature_cols:
        feature_cols = [column for column in features_df.columns if column not in ('begin', TARGET_COLUMN)]

    latest_row = features_df.sort_values('begin').iloc[-1:]
    features = latest_row[feature_cols].replace([np.inf, -np.inf], np.nan)
    prediction = model.predict(features)
    return float(np.asarray(prediction).reshape(-1)[0])


def _experiment_ids(experiment_name: str | None) -> list[str] | None:
    if not experiment_name:
        return None
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise RuntimeError(f'Experiment not found: {experiment_name}')
    return [experiment.experiment_id]


def _summary_from_run(params: dict, metrics: dict, run_id: str) -> dict:
    return {
        'run_id': run_id,
        'variant': params.get('variant'),
        'feature_count': int(params.get('feature_count', 0) or 0),
        'val_direction_accuracy': metrics.get('val_direction_accuracy'),
        'test_direction_accuracy': metrics.get('test_direction_accuracy'),
    }
