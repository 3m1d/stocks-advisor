from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.processors import NewsParserProcessor
from app.daemons.base import BaseDaemon


class NewsParserDaemon(BaseDaemon):
    """Daemon for parsing news data."""

    def __init__(self, start_dt: datetime, end_dt: datetime):
        super().__init__()
        self.start_dt = start_dt
        self.end_dt = end_dt

    async def execute(self, session: AsyncSession) -> None:
        processor = NewsParserProcessor(session)
        await processor.parse(self.start_dt, self.end_dt)


def _parse_datetime(value: str) -> datetime:
    """Parse datetime with flexible format."""
    for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f'Invalid datetime format: {value}')


def main():
    """CLI entrypoint for news parser daemon."""
    import argparse

    parser = argparse.ArgumentParser(description='Parse news data')
    parser.add_argument('--start', type=str, required=True, help='Start datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)')
    parser.add_argument('--end', type=str, required=True, help='End datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)')

    args = parser.parse_args()

    start_dt = _parse_datetime(args.start)
    end_dt = _parse_datetime(args.end)

    daemon = NewsParserDaemon(start_dt, end_dt)
    daemon.run()


if __name__ == '__main__':
    main()
