"""Load market data, build features and tonality merges."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

import numpy as np
import pandas as pd

from stocks_dl.constants import TARGET_COLUMN

TICKERS_WITH_NEWS = ['SBER', 'TCSG', 'GAZP', 'LKOH', 'ROSN']
NEWS_HORIZONS_HOURS = [2, 24, 72, 168]
ENRICHMENTS_LIMIT = 1_000_000

T = TypeVar('T')


def run_async_safe(coro: Coroutine[Any, Any, T]) -> T:
    """Run async code from sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Jupyter/IPython: reuse the active loop
    import nest_asyncio

    nest_asyncio.apply()
    return loop.run_until_complete(coro)


def merge_tonality_with_prices(
    ticker: str,
    price_data: pd.DataFrame,
    tonality_data: pd.DataFrame,
    horizons_hours: list[int],
    sector_to_ticker: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    if sector_to_ticker is None:
        sector_to_ticker = {
            'MOEXFN': ['SBER', 'VTBR', 'TCSG'],
            'MOEXOG': ['GAZP', 'LKOH', 'ROSN', 'TATN'],
            'MOEXIT': ['YDEX'],
            'MOEXMM': ['GMKN'],
        }

    result = price_data.copy()
    tonality_copy = tonality_data.copy()
    result['begin'] = pd.to_datetime(result['begin'])
    tonality_copy['date'] = pd.to_datetime(tonality_copy['date'])

    def parse_ticker_list(x) -> list[str]:
        if x is None:
            return []
        if isinstance(x, (list, tuple, set, np.ndarray, pd.Series)):
            return [str(t).upper().strip() for t in x if str(t).strip()]
        if isinstance(x, str):
            s = x.strip('[]').strip()
            if not s:
                return []
            return [t.upper().strip().strip('\'"') for t in s.split(',') if t.strip()]
        try:
            if pd.isna(x):
                return []
        except Exception:
            pass
        sx = str(x).strip()
        if not sx or sx == '[]':
            return []
        return [t.upper().strip().strip('\'"') for t in sx.split(',') if t.strip()]

    sentiment_map = {'positive': 1, 'neutral': 0, 'negative': -1}

    if 'tickers' in tonality_copy.columns:
        tonality_copy['tickers_list'] = tonality_copy['tickers'].apply(parse_ticker_list)
    else:
        tonality_copy['tickers_list'] = [[] for _ in range(len(tonality_copy))]
    if 'sentiment' in tonality_copy.columns:
        tonality_copy['sentiment_value'] = tonality_copy['sentiment'].map(sentiment_map)
    else:
        tonality_copy['sentiment_value'] = pd.Series([pd.NA] * len(tonality_copy))

    def is_news_for_ticker(row, target_ticker: str) -> bool:
        target = target_ticker.upper()
        if target in row['tickers_list']:
            return True
        sector = str(row.get('sector', '')).upper()
        return target in [t.upper() for t in sector_to_ticker.get(sector, [])]

    news_for_ticker = tonality_copy[tonality_copy.apply(lambda row: is_news_for_ticker(row, ticker), axis=1)].copy()

    if len(news_for_ticker) == 0:
        for h in horizons_hours:
            col = 'sentiment' if h == 2 else f'sentiment_{h}h'
            result[col] = np.nan
        return result

    for h in horizons_hours:
        col = 'sentiment' if h == 2 else f'sentiment_{h}h'
        result[col] = np.nan

    unique_times = sorted(result['begin'].unique())
    for current_time in unique_times:
        for h in horizons_hours:
            window_start = current_time - pd.Timedelta(hours=h)
            mask_news = (news_for_ticker['date'] > window_start) & (news_for_ticker['date'] <= current_time)
            window_news = news_for_ticker.loc[mask_news, 'sentiment_value'].dropna()
            if len(window_news) > 0:
                col = 'sentiment' if h == 2 else f'sentiment_{h}h'
                result.loc[result['begin'] == current_time, col] = window_news.mean()

    return result


async def load_candles_by_ticker() -> dict[str, pd.DataFrame]:
    from app.core.database import AssetCandleRepository, get_db_session

    async with get_db_session() as session:
        repo = AssetCandleRepository(session)
        return await repo.get_dataframe_by_ticker()


async def load_enrichments(limit: int | None = None) -> pd.DataFrame:
    from app.core.database import NewsArticleRepository, get_db_session

    row_limit = ENRICHMENTS_LIMIT if limit is None else limit
    async with get_db_session() as session:
        repo = NewsArticleRepository(session)
        enrichments_df = await repo.get_all_enrichments_as_dataframe(limit=row_limit)
    enrichments_df.rename(columns={'published_at': 'date'}, inplace=True)
    return enrichments_df


def build_features_by_ticker(candles_by_ticker: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    from app.core.processors.feature_generator import FeatureGenerator

    features_by_ticker: dict[str, pd.DataFrame] = {}
    fg = FeatureGenerator()
    for ticker, df in candles_by_ticker.items():
        features_by_ticker[ticker] = fg.process(
            df=df,
            include_original=False,
            add_targets=True,
            clean=True,
        ).drop(['target_class'], axis=1)
    return features_by_ticker


def attach_tonality(
    features_by_ticker: dict[str, pd.DataFrame],
    enrichments_df: pd.DataFrame,
    tickers: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    tickers = tickers or TICKERS_WITH_NEWS
    for ticker in tickers:
        if ticker not in features_by_ticker:
            continue
        features_by_ticker[ticker] = merge_tonality_with_prices(
            ticker, features_by_ticker[ticker], enrichments_df, horizons_hours=NEWS_HORIZONS_HOURS
        )
        features_by_ticker[ticker] = features_by_ticker[ticker].fillna(0)
    return features_by_ticker


async def load_features_bundle(
    ticker: str,
    *,
    enrichments_limit: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bundle = await load_features_bundle_multi([ticker], enrichments_limit=enrichments_limit)
    return bundle[ticker], bundle['_enrichments']


async def load_features_bundle_multi(
    tickers: list[str],
    *,
    enrichments_limit: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Load candles once, build features, attach tonality for all requested tickers."""
    candles = await load_candles_by_ticker()
    enrichments = await load_enrichments(limit=enrichments_limit)
    features = build_features_by_ticker(candles)
    features = attach_tonality(features, enrichments, tickers=tickers)
    out: dict[str, pd.DataFrame] = {'_enrichments': enrichments}
    for ticker in tickers:
        if ticker not in features:
            raise KeyError(f'No feature frame for ticker {ticker}')
        out[ticker] = features[ticker].copy()
    return out


def load_features_and_enrichments(
    ticker: str,
    *,
    enrichments_limit: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return run_async_safe(load_features_bundle(ticker, enrichments_limit=enrichments_limit))


def load_features_multi(
    tickers: list[str],
    *,
    enrichments_limit: int | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Sync helper: {ticker: features_df}, enrichments_df."""
    bundle = run_async_safe(
        load_features_bundle_multi(tickers, enrichments_limit=enrichments_limit)
    )
    enrichments = bundle.pop('_enrichments')
    return bundle, enrichments


def build_data_provenance(
    ticker: str,
    full_df: pd.DataFrame,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    test_size: float,
    val_size: float,
    final_val_size: float | None = None,
) -> dict[str, Any]:
    begin = pd.to_datetime(full_df['begin'])
    return {
        'ticker': ticker,
        'target_column': TARGET_COLUMN,
        'data_source': 'PostgreSQL: AssetCandleRepository + NewsArticleRepository enrichments',
        'feature_pipeline': 'FeatureGenerator + merge_tonality_with_prices',
        'row_count_total': int(len(full_df)),
        'row_count_train': int(len(train_df)),
        'row_count_val': int(len(val_df)),
        'row_count_test': int(len(test_df)),
        'date_min': str(begin.min()),
        'date_max': str(begin.max()),
        'split_policy': {
            'test_size': test_size,
            'val_size': val_size,
            'final_val_size': final_val_size,
            'method': 'chronological',
        },
    }
