import os

import mlflow

from app.config import get_settings


def configure_mlflow(experiment_name: str | None = None) -> None:
    """Настраивает MLflow client: tracking URI, experiment, S3 credentials для boto3."""
    settings = get_settings().mlflow
    experiment = experiment_name or settings.default_experiment

    # boto3 и MLflow auth читают os.environ, не pydantic settings
    os.environ['AWS_ACCESS_KEY_ID'] = settings.aws_access_key_id
    os.environ['AWS_SECRET_ACCESS_KEY'] = settings.aws_secret_access_key
    os.environ['MLFLOW_S3_ENDPOINT_URL'] = settings.s3_endpoint_url
    os.environ['AWS_DEFAULT_REGION'] = settings.aws_region

    if settings.tracking_username:
        os.environ['MLFLOW_TRACKING_USERNAME'] = settings.tracking_username
    if settings.tracking_password:
        os.environ['MLFLOW_TRACKING_PASSWORD'] = settings.tracking_password

    mlflow.set_tracking_uri(settings.tracking_uri)
    mlflow.set_experiment(experiment)
