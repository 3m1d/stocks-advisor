import asyncio
import logging
from datetime import date, datetime, time

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import NewsArticleRepository, get_db_session, news_articles_to_dataframe
from app.core.database.db_models.news_article import NewsSource
from app.core.database.db_models.news_article_enrichment import NewsArticleEnrichment, NewsSentiment
from app.core.processors.news_process import NewsProcessor

logger = logging.getLogger(__name__)


def _to_datetime(value: datetime | date | None, *, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if end_of_day:
        return datetime.combine(value, time.max)
    return datetime.combine(value, time.min)


def _dataframe_to_enrichments(df: pd.DataFrame) -> list[NewsArticleEnrichment]:
    enrichments: list[NewsArticleEnrichment] = []
    for row in df.itertuples(index=False):
        sector = row.sector if pd.notna(row.sector) else None
        enrichments.append(
            NewsArticleEnrichment(
                news_article_id=int(row.id),
                tickers=list(row.tickers),
                sector=sector,
                sentiment=NewsSentiment(row.text_sentiment),
            )
        )
    return enrichments


async def _save_enrichments(
    session: AsyncSession,
    enrichments: list[NewsArticleEnrichment],
    *,
    db_batch_size: int,
) -> int:
    repo = NewsArticleRepository(session)
    saved_count = 0
    for offset in range(0, len(enrichments), db_batch_size):
        batch = enrichments[offset : offset + db_batch_size]
        count = await repo.bulk_create_enrichments(batch, batch_size=db_batch_size)
        saved_count += count
        logger.info('Saved enrichment batch at offset %s: %s records', offset, count)
    return saved_count


class NewsProcessAndSaveProcessor:
    """Извлекает новости из БД, обрабатывает (тикеры, секторы, тональность) и сохраняет результат в БД"""

    def __init__(
        self,
        *,
        chunk_size: int = 100,
        db_batch_size: int = 1_000,
        processor: NewsProcessor | None = None,
    ):
        if chunk_size <= 0:
            raise ValueError('chunk_size must be greater than 0')
        if db_batch_size <= 0:
            raise ValueError('db_batch_size must be greater than 0')

        self.chunk_size = chunk_size
        self.db_batch_size = db_batch_size
        self.processor = processor or NewsProcessor()

    async def process(
        self,
        published_from: datetime | date | None = None,
        published_to: datetime | date | None = None,
        source: NewsSource | None = None,
    ) -> tuple[int, int]:
        published_from_dt = _to_datetime(published_from)
        published_to_dt = _to_datetime(published_to, end_of_day=True)

        processed_count = 0
        saved_count = 0
        offset = 0

        async with get_db_session() as session:
            repo = NewsArticleRepository(session)

            while True:
                articles = await repo.get_all(
                    limit=self.chunk_size,
                    offset=offset,
                    published_from=published_from_dt,
                    published_to=published_to_dt,
                    source=source,
                )
                if not articles:
                    break

                logger.info(
                    'Processing chunk at offset %s: %s articles (source=%s, from=%s, to=%s)',
                    offset,
                    len(articles),
                    source,
                    published_from_dt,
                    published_to_dt,
                )

                df = news_articles_to_dataframe(articles)
                enriched_df = await asyncio.to_thread(self.processor.process_news, df)
                enrichments = _dataframe_to_enrichments(enriched_df)
                batch_saved = await _save_enrichments(
                    session,
                    enrichments,
                    db_batch_size=self.db_batch_size,
                )

                processed_count += len(articles)
                saved_count += batch_saved
                offset += len(articles)

                logger.info(
                    'Chunk at offset %s: processed %s, saved %s enrichments',
                    offset - len(articles),
                    len(articles),
                    batch_saved,
                )

                if len(articles) < self.chunk_size:
                    break

        logger.info('Processing finished: processed %s articles, saved %s enrichments', processed_count, saved_count)
        return processed_count, saved_count
