"""Configure repo path, APP_CONFIG and MLflow for CLI/notebooks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

STOCKS_DL_DIR = Path(__file__).resolve().parent
REPO_ROOT = STOCKS_DL_DIR.parent


def suppress_mlflow_run_urls() -> None:
    os.environ['MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT'] = 'true'


def ensure_paths() -> Path:
    """Ensure repo root is importable (legacy notebooks) and return it."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return REPO_ROOT


def configure_environment(
    environment: str = 'prod',
    experiment_name: str | None = None,
    *,
    suppress_mlflow_urls: bool = True,
) -> None:
    ensure_paths()
    config_by_env = {
        'local': 'config_local.toml',
        'prod': 'config.toml',
    }
    if environment not in config_by_env:
        raise ValueError(f'environment must be one of {list(config_by_env)}; got {environment!r}')

    os.chdir(REPO_ROOT)
    load_dotenv(REPO_ROOT / '.env')
    os.environ['APP_CONFIG'] = config_by_env[environment]
    if suppress_mlflow_urls:
        suppress_mlflow_run_urls()

    from app.config.settings import get_settings

    get_settings.cache_clear()

    import mlflow

    from app.mlflow import configure_mlflow

    configure_mlflow(experiment_name)

    settings = get_settings().mlflow
    print(f'Environment: {environment}')
    print(f'Tracking URI: {mlflow.get_tracking_uri()}')
    print(f'S3 endpoint: {settings.s3_endpoint_url}')
    print(f'Experiment: {experiment_name or settings.default_experiment}')
