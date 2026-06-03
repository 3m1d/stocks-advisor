"""CLI: load PRD model from MLflow and run test inference."""

from __future__ import annotations

import asyncio
from pathlib import Path

import hydra
import matplotlib.pyplot as plt
from omegaconf import DictConfig

from stocks_dl.data.pipeline import attach_tonality, build_features_by_ticker, load_candles_by_ticker, load_enrichments
from stocks_dl.env_setup import REPO_ROOT, configure_environment
from stocks_dl.paths import PKG_ROOT
from stocks_dl.workflows.inference import run_demo_inference

HYDRA_CONFIG_PATH = str(PKG_ROOT / 'conf')


async def load_features(ticker: str):
    candles = await load_candles_by_ticker()
    enrichments = await load_enrichments()
    features = build_features_by_ticker(candles)
    features = attach_tonality(features, enrichments, tickers=[ticker])
    return features[ticker].copy()


@hydra.main(version_base=None, config_path=HYDRA_CONFIG_PATH, config_name='config')
def main(cfg: DictConfig) -> None:
    configure_environment(cfg.environment, cfg.experiment_name)

    features_df = asyncio.run(load_features(cfg.ticker))
    demo_csv = Path(cfg.demo.csv_path)
    if not demo_csv.is_absolute():
        demo_csv = REPO_ROOT / demo_csv

    output_path = Path(cfg.demo.output_path)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path

    result = run_demo_inference(
        features_df=features_df,
        output_path=output_path,
        ticker=cfg.ticker,
        experiment_name=cfg.experiment_name,
        demo_csv=demo_csv if demo_csv.exists() else None,
        prd_run_id=cfg.prd_run_id,
        test_size=cfg.data.test_size,
        val_size=cfg.data.val_size,
        final_val_size=cfg.data.final_val_size,
    )

    print('PRD run_id:', result['run_id'])
    print('Metrics:', result['metrics'])
    print('Saved:', result['output_path'])

    df = result['predictions_df']
    plt.figure(figsize=(10, 4))
    plt.plot(df['target_price_change'].values, label='target')
    plt.plot(df['predict'].values, label='predict')
    plt.legend()
    plt.title(f'{cfg.ticker} PRD demo predictions')
    plot_path = output_path.with_suffix('.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print('Plot:', plot_path)

    sample = df.head(3)
    for _, row in sample.iterrows():
        direction = 'up' if row['predict'] > 0 else 'down' if row['predict'] < 0 else 'flat'
        print(
            f'  {row["begin"]}: predict={row["predict"]:.3f}% ({direction}), '
            f'target={row.get("target_price_change", float("nan")):.3f}%'
        )


if __name__ == '__main__':
    main()
