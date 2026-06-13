import asyncio
import logging
from datetime import date, datetime, time as dt_time

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import NewsArticleRepository, get_db_session, news_articles_to_dataframe
from app.core.database.db_models.news_article import NewsSource
from app.core.database.db_models.news_article_enrichment import NewsArticleEnrichment, NewsSentiment
from app.core.processors.news_process import NewsProcessor
from app.utils.timing import format_duration, log_timed, timed

logger = logging.getLogger(__name__)


def _to_datetime(value: datetime | date | None, *, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if end_of_day:
        return datetime.combine(value, dt_time.max)
    return datetime.combine(value, dt_time.min)


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
                sentiment_score=float(row.sentiment_score),
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
        chunk_size: int = 5_000,
        db_batch_size: int = 1_000,
        use_gpu: bool = False,
        processor: NewsProcessor | None = None,
    ):
        if chunk_size <= 0:
            raise ValueError('chunk_size must be greater than 0')
        if db_batch_size <= 0:
            raise ValueError('db_batch_size must be greater than 0')

        self.chunk_size = chunk_size
        self.db_batch_size = db_batch_size
        self._processor = processor
        self._use_gpu = use_gpu

    def _get_processor(self) -> NewsProcessor:
        if self._processor is None:
            self._processor = NewsProcessor(use_gpu=self._use_gpu)
        return self._processor

    async def process(
        self,
        published_from: datetime | date | None = None,
        published_to: datetime | date | None = None,
        source: NewsSource | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> tuple[int, int]:
        if session is not None:
            return await self._process(session, published_from, published_to, source)

        async with get_db_session() as owned_session:
            return await self._process(owned_session, published_from, published_to, source)

    async def _process(
        self,
        session: AsyncSession,
        published_from: datetime | date | None,
        published_to: datetime | date | None,
        source: NewsSource | None,
    ) -> tuple[int, int]:
        published_from_dt = _to_datetime(published_from)
        published_to_dt = _to_datetime(published_to, end_of_day=True)

        processed_count = 0
        saved_count = 0
        offset = 0

        repo = NewsArticleRepository(session)

        total_count = await repo.count(
            published_from=published_from_dt,
            published_to=published_to_dt,
            source=source,
        )
        if total_count == 0:
            logger.info(
                'No articles to process (source=%s, from=%s, to=%s)',
                source,
                published_from_dt,
                published_to_dt,
            )
            return 0, 0

        processor = self._get_processor()
        total_chunks = (total_count + self.chunk_size - 1) // self.chunk_size
        logger.info(
            'Found %s articles to process in %s chunks (source=%s, from=%s, to=%s, chunk_size=%s)',
            total_count,
            total_chunks,
            source,
            published_from_dt,
            published_to_dt,
            self.chunk_size,
        )

        chunk_number = 0
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

            chunk_number += 1
            processed_so_far = offset + len(articles)
            logger.info(
                'Processing chunk %s/%s: %s articles (%s/%s total, source=%s, from=%s, to=%s)',
                chunk_number,
                total_chunks,
                len(articles),
                processed_so_far,
                total_count,
                source,
                published_from_dt,
                published_to_dt,
            )

            df = news_articles_to_dataframe(articles)
            with timed() as chunk:
                with log_timed(f'NLP ({len(articles)} articles)', logger=logger, count=len(articles)) as nlp:
                    enriched_df = await asyncio.to_thread(processor.process_news, df)

                with log_timed(
                    f'DB save ({len(articles)} articles)', logger=logger, count=len(articles)
                ) as db_save:
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
                'Chunk %s/%s done: processed %s, saved %s enrichments (%s/%s total) in %s (nlp=%s, db_save=%s)',
                chunk_number,
                total_chunks,
                len(articles),
                batch_saved,
                processed_count,
                total_count,
                format_duration(chunk.seconds),
                format_duration(nlp.seconds),
                format_duration(db_save.seconds),
            )

            if len(articles) < self.chunk_size:
                break

        logger.info('Processing finished: processed %s articles, saved %s enrichments', processed_count, saved_count)
        return processed_count, saved_count
