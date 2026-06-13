import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.processors import NewsParserProcessor
from app.daemons.base import BaseDaemon
from app.daemons.cli_utils import add_date_range_args, parse_date, parse_datetime
from app.daemons.incremental import IncrementalDataKind, resolve_incremental_datetime_range

logger = logging.getLogger(__name__)


class NewsParserDaemon(BaseDaemon):
    """Daemon for parsing news data."""

    def __init__(self, start_dt: datetime, end_dt: datetime):
        super().__init__()
        self.start_dt = start_dt
        self.end_dt = end_dt

    async def execute(self, session: AsyncSession) -> None:
        await self.run_async()

    async def run_async(self) -> None:
        # Each news source runs in a spawned subprocess with its own DB engine/session.
        processor = NewsParserProcessor()
        await processor.parse(self.start_dt, self.end_dt)


async def _resolve_range(args) -> tuple[datetime, datetime] | None:
    if args.incremental:
        end_date = parse_date(args.end) if args.end else None
        return await resolve_incremental_datetime_range(IncrementalDataKind.NEWS_ARTICLE, end=end_date)

    if not args.start or not args.end:
        raise SystemExit('--start and --end are required unless --incremental is set')

    return parse_datetime(args.start), parse_datetime(args.end)


async def _main(args) -> None:
    date_range = await _resolve_range(args)
    if date_range is None:
        logger.info('News parser: nothing to do')
        return

    start_dt, end_dt = date_range
    logger.info('News parser range: %s -> %s', start_dt, end_dt)
    await NewsParserDaemon(start_dt, end_dt).run_async()


def main():
    """CLI entrypoint for news parser daemon."""
    import argparse

    parser = argparse.ArgumentParser(description='Parse news data')
    add_date_range_args(parser)
    args = parser.parse_args()
    asyncio.run(_main(args))


if __name__ == '__main__':
    main()
