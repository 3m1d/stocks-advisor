import asyncio
from datetime import datetime

from app.core.database import get_db_session
from app.core.processors import AssetParserProcessor
from app.daemons.base import BaseDaemon


class StockParserDaemon(BaseDaemon):
    """Daemon for parsing MOEX stock data."""

    def __init__(self, start_dt: datetime, end_dt: datetime):
        super().__init__()
        self.start_dt = start_dt
        self.end_dt = end_dt

    async def _run_async(self) -> int:
        async with get_db_session() as session:
            processor = AssetParserProcessor(session)
            return await processor.parse(self.start_dt, self.end_dt)

    def run(self) -> None:
        asyncio.run(self._run_async())


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
