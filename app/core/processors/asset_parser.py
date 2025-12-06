import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clients.moex import Boards, Engines, Interval, Markets, MOEXClient, Ticker
from app.core.database import AssetCandleRepository

logger = logging.getLogger(__name__)


class AssetParserProcessor:
    """Processor for parsing MOEX stock data."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.client = MOEXClient()
        self.repo = AssetCandleRepository(session)

    async def parse(self, start_dt: datetime, end_dt: datetime) -> int:
        """Parse MOEX stock data for a datetime range and insert into database."""
        tickers = list(Ticker)

        logger.info(f'Parsing stocks from {start_dt} to {end_dt}')

        data = await self.client.get_data(
            tickers=tickers,
            engine=Engines.STOCK,
            market=Markets.SHARES,
            board=Boards.TQBR,
            start_date=start_dt,
            end_date=end_dt,
            interval=Interval.HOUR_1,
        )

        total_count = 0
        for ticker, df in data.items():
            if df.empty:
                logger.debug(f'No data for {ticker}')
                continue

            records = df.to_dict('records')
            count = await self.repo.bulk_upsert(records)
            total_count += count
            logger.info(f'Processed {count} records for {ticker}')

        logger.info(f'Total records processed: {total_count}')
        return total_count
