"""CLI: load PRD model from MLflow and run test inference (multi-ticker via Hydra)."""

from __future__ import annotations

import hydra
import matplotlib.pyplot as plt
from omegaconf import DictConfig

from stocks_dl.cli.config_helpers import data_cfg, pkg_path, resolve_tickers, training_cfg
from stocks_dl.data.pipeline import load_features_multi
from stocks_dl.env_setup import configure_environment
from stocks_dl.paths import PKG_ROOT
from stocks_dl.workflows.inference import run_demo_inference

HYDRA_CONFIG_PATH = str(PKG_ROOT / 'conf')


@hydra.main(version_base=None, config_path=HYDRA_CONFIG_PATH, config_name='config')
def main(cfg: DictConfig) -> None:
    tickers = resolve_tickers(cfg)
    data = data_cfg(cfg)
    train = training_cfg(cfg)

    configure_environment(
        cfg.environment,
        cfg.experiment_name,
        suppress_mlflow_urls=train.get('suppress_mlflow_urls', True),
    )

    print(f'Demo inference | tickers: {tickers} | experiment: {cfg.experiment_name}')
    features_by_ticker, _ = load_features_multi(
        tickers,
        enrichments_limit=data.get('enrichments_limit'),
    )

    for ticker in tickers:
        features_df = features_by_ticker[ticker]
        demo_csv = pkg_path(cfg.paths.demo_csv_template, ticker)
        output_path = pkg_path(cfg.paths.demo_output_template, ticker)

        print(f'\n=== [{ticker}] demo ===')
        result = run_demo_inference(
            features_df=features_df,
            output_path=output_path,
            ticker=ticker,
            experiment_name=cfg.experiment_name,
            demo_csv=demo_csv if demo_csv.exists() else None,
            prd_run_id=cfg.prd_run_id,
            test_size=data['test_size'],
            val_size=data['val_size'],
            final_val_size=data['final_val_size'],
        )

        print('PRD run_id:', result['run_id'])
        print('Metrics:', result['metrics'])
        print('Saved:', result['output_path'])

        if not cfg.demo.get('plot', True):
            continue

        df = result['predictions_df']
        plt.figure(figsize=(10, 4))
        plt.plot(df['target_price_change'].values, label='target')
        plt.plot(df['predict'].values, label='predict')
        plt.legend()
        plt.title(f'{ticker} PRD demo predictions')
        plot_path = output_path.with_suffix('.png')
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        plt.close()
        print('Plot:', plot_path)

        for _, row in df.head(3).iterrows():
            direction = 'up' if row['predict'] > 0 else 'down' if row['predict'] < 0 else 'flat'
            print(
                f'  {row["begin"]}: predict={row["predict"]:.3f}% ({direction}), '
                f'target={row.get("target_price_change", float("nan")):.3f}%'
            )


if __name__ == '__main__':
    main()
