import mlflow

from app.config import get_settings


def configure_mlflow(experiment_name: str | None = None) -> None:
    """Настраивает MLflow client"""
    settings = get_settings().mlflow
    experiment = experiment_name or settings.default_experiment

    mlflow.set_tracking_uri(settings.tracking_uri)
    mlflow.set_experiment(experiment)
