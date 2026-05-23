import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clients.moex import Interval
from app.core.database import AssetCandleRepository
from app.core.processors.stocks_parser import StocksParser

logger = logging.getLogger(__name__)


class AssetParserProcessor:
    """Processor for parsing MOEX stock data."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AssetCandleRepository(session)

    async def parse(self, start_dt: datetime, end_dt: datetime) -> tuple[int, int]:
        """Parse MOEX stock data for a datetime range and insert into database."""
        parser = StocksParser(start_dt, end_dt, interval=Interval.HOUR_1)
        data = await parser.parse()

        saved_count = 0
        parsed_count = 0
        for ticker, df in data.items():
            if df.empty:
                logger.debug(f'No data for {ticker}')
                continue

            records = df.to_dict('records')
            parsed_count += len(records)

            count = await self.repo.bulk_upsert(records)
            saved_count += count

            logger.info(f'Processed {count} records for {ticker}')

        logger.info(f'Records parsed: {parsed_count}; Records saved: {saved_count}')
        return parsed_count, saved_count
