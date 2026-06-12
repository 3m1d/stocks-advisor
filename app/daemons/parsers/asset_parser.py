import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.processors import AssetParserProcessor
from app.daemons.base import BaseDaemon
from app.daemons.cli_utils import add_date_range_args, parse_date, parse_datetime
from app.daemons.incremental import IncrementalDataKind, resolve_incremental_datetime_range

logger = logging.getLogger(__name__)


class AssetParserDaemon(BaseDaemon):
    """Daemon for parsing MOEX stock data."""

    def __init__(self, start_dt: datetime, end_dt: datetime):
        super().__init__()
        self.start_dt = start_dt
        self.end_dt = end_dt

    async def execute(self, session: AsyncSession) -> None:
        processor = AssetParserProcessor(session)
        await processor.parse(self.start_dt, self.end_dt)


async def _resolve_range(args) -> tuple[datetime, datetime] | None:
    if args.incremental:
        end_date = parse_date(args.end) if args.end else None
        return await resolve_incremental_datetime_range(IncrementalDataKind.ASSET_CANDLE, end=end_date)

    if not args.start or not args.end:
        raise SystemExit('--start and --end are required unless --incremental is set')

    return parse_datetime(args.start), parse_datetime(args.end)


def main():
    """CLI entrypoint for asset parser daemon."""
    import argparse

    parser = argparse.ArgumentParser(description='Parse MOEX stock data')
    add_date_range_args(parser)
    args = parser.parse_args()

    date_range = asyncio.run(_resolve_range(args))
    if date_range is None:
        logger.info('Asset parser: nothing to do')
        return

    start_dt, end_dt = date_range
    logger.info('Asset parser range: %s -> %s', start_dt, end_dt)
    AssetParserDaemon(start_dt, end_dt).run()


if __name__ == '__main__':
    main()
