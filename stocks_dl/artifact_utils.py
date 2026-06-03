"""Download and locate MLflow run artifacts."""

from __future__ import annotations

from pathlib import Path

import mlflow


def find_analysis_run(
    prd_run_id: str,
    ticker: str,
    experiment_name: str | None = None,
) -> str | None:
    """Return latest analysis run linked to the given PRD run, if any."""
    experiment_ids = None
    if experiment_name:
        exp = mlflow.get_experiment_by_name(experiment_name)
        if exp is not None:
            experiment_ids = [exp.experiment_id]

    for filter_string in (
        f"tags.source_prd_run_id = '{prd_run_id}'",
        f"tags.stage = 'analysis' AND tags.ticker = '{ticker}'",
    ):
        runs = mlflow.search_runs(
            experiment_ids=experiment_ids,
            filter_string=filter_string,
            order_by=['attributes.start_time DESC'],
            max_results=5,
        )
        if not runs.empty:
            return runs.iloc[0]['run_id']
    return None


def download_artifact_file(run_id: str, artifact_path: str) -> Path | None:
    """Download a single artifact path from a run; return local file path."""
    from mlflow import artifacts

    try:
        local = artifacts.download_artifacts(run_id=run_id, artifact_path=artifact_path)
    except Exception:
        return None
    path = Path(local)
    if path.is_dir():
        for pattern in ('*.png', '*.jpg', '*.jpeg'):
            candidates = sorted(path.glob(pattern))
            if candidates:
                return candidates[0]
        return None
    return path if path.is_file() else None
