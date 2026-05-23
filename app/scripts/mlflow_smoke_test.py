from datetime import UTC, datetime

import click
import mlflow

from app.config import get_settings
from app.mlflow import configure_mlflow


@click.command()
@click.option('--experiment', default='test', help='Experiment name, default "test"')
def main(experiment: str | None) -> None:
    """Тестируем интеграцию с MLFlow"""
    settings = get_settings().mlflow
    configure_mlflow(experiment)

    tracking_uri = mlflow.get_tracking_uri()
    click.echo(f'Tracking URI: {tracking_uri}')

    run_name = f'smoke-test-{datetime.now(UTC).strftime("%Y%m%d-%H%M%S")}'
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_param('source', 'mlflow_smoke_test')
        mlflow.log_metric('ping', 1.0)
        mlflow.log_dict({'status': 'ok'}, 'smoke.json')

    click.echo(f'Run ID: {run.info.run_id}')
    click.echo(f'Experiment: {experiment or settings.default_experiment}')
    click.echo('Smoke test passed.')


if __name__ == '__main__':
    main()
