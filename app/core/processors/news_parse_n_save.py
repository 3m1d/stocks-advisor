import logging
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import NewsArticleRepository
from app.core.processors.news_parsing import NEWS_PARSERS
from app.core.processors.news_parsing.base import ParsedNewsArticle, date_range_batches

logger = logging.getLogger(__name__)


class NewsParserProcessor:
    """Processor for parsing news and saving to database."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        batch_size: int = 1_000,
        date_batch_days: int = 30,
    ):
        self.session = session
        self.repo = NewsArticleRepository(session)
        self.db_batch_size = batch_size
        self.date_batch_days = date_batch_days

    async def _save_articles(self, articles: list[ParsedNewsArticle]) -> int:
        saved_count = 0
        for offset in range(0, len(articles), self.db_batch_size):
            batch = [a.to_db_model() for a in articles[offset : offset + self.db_batch_size]]
            count = await self.repo.bulk_add(batch, batch_size=self.db_batch_size)
            saved_count += count
            logger.info(f'Saved batch at offset {offset}: {count} new articles')
        return saved_count

    async def parse(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
    ) -> tuple[int, int]:
        """Parse news for a date range and insert into database, one source and time window at a time."""
        start = start_date.date() if isinstance(start_date, datetime) else start_date
        end = end_date.date() if isinstance(end_date, datetime) else end_date

        parsed_count = 0
        saved_count = 0

        for parser_cls in NEWS_PARSERS.values():
            source = parser_cls.source
            source_parsed = 0
            source_saved = 0

            for batch_start, batch_end in date_range_batches(start, end, self.date_batch_days):
                logger.info(f'Parsing {source} for {batch_start} to {batch_end}')
                articles = await parser_cls().parse(batch_start, batch_end)
                batch_parsed = len(articles)
                batch_saved = await self._save_articles(articles)

                source_parsed += batch_parsed
                source_saved += batch_saved
                parsed_count += batch_parsed
                saved_count += batch_saved
                logger.info(
                    f'{source} [{batch_start}..{batch_end}]: parsed {batch_parsed}, saved {batch_saved} new articles',
                )

            logger.info(f'{source}: parsed {source_parsed}, saved {source_saved} new articles')

        logger.info(f'Records parsed: {parsed_count}; Records saved: {saved_count}')
        return parsed_count, saved_count
