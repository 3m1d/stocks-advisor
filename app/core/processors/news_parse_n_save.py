import logging
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import NewsArticleRepository
from app.core.processors.news_parsing import parse_all_news

logger = logging.getLogger(__name__)


class NewsParserProcessor:
    """Processor for parsing news and saving to database."""

    def __init__(self, session: AsyncSession, batch_size: int = 1_000):
        self.session = session
        self.repo = NewsArticleRepository(session)
        self.batch_size = batch_size

    async def parse(
        self,
        start_date: date | datetime,
        end_date: date | datetime,
    ) -> tuple[int, int]:
        """Parse news for a date range and insert into database in batches."""
        start = start_date.date() if isinstance(start_date, datetime) else start_date
        end = end_date.date() if isinstance(end_date, datetime) else end_date
        parsed = await parse_all_news(start, end)
        parsed_count = len(parsed)

        saved_count = 0
        for offset in range(0, parsed_count, self.batch_size):
            batch = [a.to_db_model() for a in parsed[offset : offset + self.batch_size]]
            count = await self.repo.bulk_add(batch, batch_size=self.batch_size)
            saved_count += count
            logger.info(f'Saved batch at offset {offset}: {count} new articles')

        logger.info(f'Records parsed: {parsed_count}; Records saved: {saved_count}')
        return parsed_count, saved_count
