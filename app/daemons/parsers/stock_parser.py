import asyncio
import logging
from datetime import datetime

from app.core.clients.moex import Boards, Engines, Interval, Markets, MOEXClient, Ticker
from app.core.database import get_db_session
from app.core.database.repositories import StockPriceRepository
from app.daemons.base import BaseDaemon

logger = logging.getLogger(__name__)


class StockParserDaemon(BaseDaemon):
    """Daemon for parsing MOEX stock data."""

    def __init__(self, start_dt: datetime, end_dt: datetime):
        super().__init__()
        self.start_dt = start_dt
        self.end_dt = end_dt

    async def _parse(self) -> int:
        """Parse MOEX stock data for a datetime range and insert into database."""
        client = MOEXClient()
        tickers = list(Ticker)

        logger.info(f'Parsing stocks from {self.start_dt} to {self.end_dt}')

        data = await client.get_data(
            tickers=tickers,
            engine=Engines.STOCK,
            market=Markets.SHARES,
            board=Boards.TQBR,
            start_date=self.start_dt,
            end_date=self.end_dt,
            interval=Interval.HOUR_1,
        )

        total_count = 0
        async with get_db_session() as session:
            repo = StockPriceRepository(session)

            for ticker, df in data.items():
                if df.empty:
                    logger.debug(f'No data for {ticker}')
                    continue

                records = df.to_dict('records')
                count = await repo.bulk_upsert(records)
                total_count += count
                logger.info(f'Processed {count} records for {ticker}')

        logger.info(f'Total records processed: {total_count}')
        return total_count

    def run(self) -> None:
        asyncio.run(self._parse())


def _parse_datetime(value: str) -> datetime:
    """Parse datetime with flexible format."""
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f'Invalid datetime format: {value}')


def main():
    """CLI entrypoint for stock parser daemon."""
    import argparse

    parser = argparse.ArgumentParser(description='Parse MOEX stock data')
    parser.add_argument('--start', type=str, required=True, help='Start datetime (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--end', type=str, required=True, help='End datetime (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)')

    args = parser.parse_args()

    start_dt = _parse_datetime(args.start)
    end_dt = _parse_datetime(args.end)

    daemon = StockParserDaemon(start_dt, end_dt)
    daemon.run()


if __name__ == '__main__':
    main()
