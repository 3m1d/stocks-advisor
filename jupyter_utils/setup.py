import os
import sys
from pathlib import Path
from typing import Literal

import mlflow
from dotenv import load_dotenv


def find_repo_root() -> Path:
    path = Path.cwd().resolve()
    for candidate in [path, *path.parents]:
        if (candidate / 'pyproject.toml').exists():
            return candidate
    raise RuntimeError('Could not find repo root (pyproject.toml). Open this notebook from the repo.')


def setup_jupyter_notebook(environment: Literal['local', 'prod'], experiment: str | None = None):
    config_by_env = {
        'local': 'config_local.toml',
        'prod': 'config.toml',
    }

    if environment not in config_by_env:
        raise ValueError(f'ENV must be one of {list(config_by_env)}; got {environment!r}')

    REPO_ROOT = find_repo_root()
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    os.chdir(REPO_ROOT)

    load_dotenv(REPO_ROOT / '.env')

    os.environ['APP_CONFIG'] = config_by_env[environment]

    from app.config.settings import get_settings

    get_settings.cache_clear()

    settings = get_settings().mlflow

    from app.mlflow import configure_mlflow

    configure_mlflow(experiment)

    resolved_experiment = experiment or settings.default_experiment
    database_config = get_settings().database
    print(f'Environment: {environment}')
    print(f'APP_CONFIG: {os.environ["APP_CONFIG"]}')
    print(f'Tracking URI: {mlflow.get_tracking_uri()}')
    print(f'S3 endpoint: {settings.s3_endpoint_url}')
    print(f'Experiment: {resolved_experiment}')
    print(f'Database: {database_config.host}:{database_config.port}/{database_config.name}')
