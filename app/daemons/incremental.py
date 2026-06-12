from __future__ import annotations

import logging
from datetime import date, datetime, time as dt_time, timedelta
from enum import Enum

from app.core.database import get_db_session
from app.core.database.db_models.news_article import NewsSource
from app.core.database.repositories.asset_candle import AssetCandleRepository
from app.core.database.repositories.news_article import NewsArticleRepository

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS = 60


class IncrementalDataKind(Enum):
    ASSET_CANDLE = 'asset_candle'
    NEWS_ARTICLE = 'news_article'
    NEWS_ENRICHMENT = 'news_enrichment'


async def resolve_incremental_datetime_range(
    kind: IncrementalDataKind,
    *,
    end: date | None = None,
    source: NewsSource | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> tuple[datetime, datetime] | None:
    """Return [start, end] datetimes for incremental catch-up, or None if already up to date."""
    end_date = end or date.today()

    async with get_db_session() as session:
        if kind == IncrementalDataKind.ASSET_CANDLE:
            latest = await AssetCandleRepository(session).get_latest_begin_date()
        elif kind == IncrementalDataKind.NEWS_ARTICLE:
            latest = await NewsArticleRepository(session).get_latest_published_date(source=source)
        elif kind == IncrementalDataKind.NEWS_ENRICHMENT:
            latest = await NewsArticleRepository(session).get_latest_enriched_published_date(source=source)
        else:
            raise ValueError(f'Unsupported incremental kind: {kind!r}')

    if latest is None:
        start_date = end_date - timedelta(days=lookback_days)
        logger.info('No existing %s data; using %s-day lookback from %s', kind.value, lookback_days, start_date)
    else:
        start_date = latest + timedelta(days=1)
        logger.info('Latest %s date is %s; catching up from %s', kind.value, latest, start_date)

    if start_date > end_date:
        logger.info('Already up to date through %s', end_date)
        return None

    start_dt = datetime.combine(start_date, dt_time.min)
    end_dt = datetime.combine(end_date, dt_time.max)
    return start_dt, end_dt
