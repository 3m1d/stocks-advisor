import logging
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import NewsArticleRepository
from app.core.processors.news_parsing import NEWS_PARSERS
from app.core.processors.news_parsing.base import ParsedNewsArticle

logger = logging.getLogger(__name__)


class NewsParserProcessor:
    """Processor for parsing news and saving to database."""

    def __init__(self, session: AsyncSession, batch_size: int = 1_000):
        self.session = session
        self.repo = NewsArticleRepository(session)
        self.batch_size = batch_size

    async def _save_articles(self, articles: list[ParsedNewsArticle]) -> int:
        saved_count = 0
        for offset in range(0, len(articles), self.batch_size):
            batch = [a.to_db_model() for a in articles[offset : offset + self.batch_size]]
            count = await self.repo.bulk_add(batch, batch_size=self.batch_size)
            saved_count += count
            logger.info(f'Saved batch at offset {offset}: {count} new articles')
        return saved_count

    async def parse(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
    ) -> tuple[int, int]:
        """Parse news for a date range and insert into database, one source at a time."""
        start = start_date.date() if isinstance(start_date, datetime) else start_date
        end = end_date.date() if isinstance(end_date, datetime) else end_date

        parsed_count = 0
        saved_count = 0

        for parser_cls in NEWS_PARSERS.values():
            source = parser_cls.source
            logger.info(f'Parsing news from {source} for {start} to {end}')
            articles = await parser_cls().parse(start, end)
            source_parsed = len(articles)
            source_saved = await self._save_articles(articles)

            parsed_count += source_parsed
            saved_count += source_saved
            logger.info(
                f'{source}: parsed {source_parsed}, saved {source_saved} new articles',
            )

        logger.info(f'Records parsed: {parsed_count}; Records saved: {saved_count}')
        return parsed_count, saved_count
