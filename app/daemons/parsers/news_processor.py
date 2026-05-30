from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.db_models.news_article import NewsSource
from app.core.processors import NewsProcessAndSaveProcessor
from app.daemons.base import BaseDaemon


class NewsProcessorDaemon(BaseDaemon):
    """Daemon for processing news data."""

    def __init__(self, start_dt: datetime, end_dt: datetime, source: NewsSource):
        super().__init__()
        self.start_dt = start_dt
        self.end_dt = end_dt
        self.source = source

    async def execute(self, session: AsyncSession) -> None:
        processor = NewsProcessAndSaveProcessor()
        await processor.process(self.start_dt, self.end_dt, source=self.source)


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
    parser.add_argument('--source', type=str, required=True, help='Source (interfax, kommersant, vedomosti)')

    args = parser.parse_args()

    start_dt = _parse_datetime(args.start)
    end_dt = _parse_datetime(args.end)
    source = NewsSource(args.source)
    daemon = NewsProcessorDaemon(start_dt, end_dt, source)
    daemon.run()


if __name__ == '__main__':
    main()
