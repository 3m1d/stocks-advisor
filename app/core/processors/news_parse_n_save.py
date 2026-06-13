import asyncio
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings, setup_logging
from app.core.database import NewsArticleRepository, get_db_session
from app.core.database.db_models.news_article import NewsSource
from app.core.processors.news_parsing import NEWS_PARSERS
from app.core.processors.news_parsing.base import ParsedNewsArticle, date_range_batches

logger = logging.getLogger(__name__)


async def _save_articles(
    session: AsyncSession,
    articles: list[ParsedNewsArticle],
    *,
    db_batch_size: int,
) -> int:
    repo = NewsArticleRepository(session)
    saved_count = 0
    for offset in range(0, len(articles), db_batch_size):
        batch = [a.to_db_model() for a in articles[offset : offset + db_batch_size]]
        count = await repo.bulk_add(batch, batch_size=db_batch_size)
        saved_count += count
        logger.info('Saved batch at offset %s: %s new articles', offset, count)
    return saved_count


async def parse_source(
    source: NewsSource,
    start: date,
    end: date,
    *,
    db_batch_size: int = 1_000,
    date_batch_days: int = 5,
) -> tuple[int, int]:
    """Parse and save articles for a single news source."""
    parser_cls = NEWS_PARSERS[source]
    parsed_count = 0
    saved_count = 0

    async with get_db_session() as session:
        for batch_start, batch_end in date_range_batches(start, end, date_batch_days):
            logger.info('Parsing %s for %s to %s', source, batch_start, batch_end)
            articles = await parser_cls().parse(batch_start, batch_end)
            batch_parsed = len(articles)
            batch_saved = await _save_articles(session, articles, db_batch_size=db_batch_size)

            parsed_count += batch_parsed
            saved_count += batch_saved
            logger.info(
                '%s [%s..%s]: parsed %s, saved %s new articles',
                source,
                batch_start,
                batch_end,
                batch_parsed,
                batch_saved,
            )

    logger.info('%s: parsed %s, saved %s new articles', source, parsed_count, saved_count)
    return parsed_count, saved_count


def _parse_source_worker(
    source_name: str,
    start_iso: str,
    end_iso: str,
    db_batch_size: int,
    date_batch_days: int,
) -> tuple[str, int, int]:
    """Entry point for per-source subprocess workers."""
    settings = get_settings()
    setup_logging(settings)

    source = NewsSource(source_name)
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    parsed_count, saved_count = asyncio.run(
        parse_source(
            source,
            start,
            end,
            db_batch_size=db_batch_size,
            date_batch_days=date_batch_days,
        ),
    )
    return source_name, parsed_count, saved_count


class NewsParserProcessor:
    """Processor for parsing news and saving to database."""

    def __init__(
        self,
        *,
        batch_size: int = 1_000,
        date_batch_days: int = 5,
        max_workers: int | None = None,
    ):
        self.db_batch_size = batch_size
        self.date_batch_days = date_batch_days
        self.max_workers = max_workers or len(NEWS_PARSERS)

    async def parse(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
    ) -> tuple[int, int]:
        """Parse news for a date range; each source runs in its own subprocess."""
        start = start_date.date() if isinstance(start_date, datetime) else start_date
        end = end_date.date() if isinstance(end_date, datetime) else end_date

        parsed_count = 0
        saved_count = 0
        loop = asyncio.get_running_loop()
        mp_context = multiprocessing.get_context('spawn')

        with ProcessPoolExecutor(max_workers=self.max_workers, mp_context=mp_context) as executor:
            futures = [
                loop.run_in_executor(
                    executor,
                    _parse_source_worker,
                    source.value,
                    start.isoformat(),
                    end.isoformat(),
                    self.db_batch_size,
                    self.date_batch_days,
                )
                for source in NEWS_PARSERS
            ]
            results = await asyncio.gather(*futures)

        for source_name, source_parsed, source_saved in results:
            parsed_count += source_parsed
            saved_count += source_saved
            logger.info(
                'Subprocess %s finished: parsed %s, saved %s new articles',
                source_name,
                source_parsed,
                source_saved,
            )

        logger.info('Records parsed: %s; Records saved: %s', parsed_count, saved_count)
        return parsed_count, saved_count
