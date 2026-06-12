import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.db_models.news_article import NewsSource
from app.core.processors import NewsProcessAndSaveProcessor
from app.daemons.base import BaseDaemon
from app.daemons.cli_utils import add_date_range_args, parse_date, parse_datetime
from app.daemons.incremental import IncrementalDataKind, resolve_incremental_datetime_range

logger = logging.getLogger(__name__)


class NewsProcessorDaemon(BaseDaemon):
    """Daemon for processing news data."""

    def __init__(
        self,
        start_dt: datetime,
        end_dt: datetime,
        source: NewsSource | None = None,
        *,
        use_gpu: bool = False,
    ):
        super().__init__()
        self.start_dt = start_dt
        self.end_dt = end_dt
        self.source = source
        self.use_gpu = use_gpu

    async def execute(self, session: AsyncSession) -> None:
        processor = NewsProcessAndSaveProcessor(use_gpu=self.use_gpu)
        await processor.process(self.start_dt, self.end_dt, source=self.source)


async def _resolve_range(args, source: NewsSource | None) -> tuple[datetime, datetime] | None:
    if args.incremental:
        end_date = parse_date(args.end) if args.end else None
        return await resolve_incremental_datetime_range(
            IncrementalDataKind.NEWS_ENRICHMENT,
            end=end_date,
            source=source,
        )

    if not args.start or not args.end:
        raise SystemExit('--start and --end are required unless --incremental is set')

    return parse_datetime(args.start), parse_datetime(args.end)


def main():
    """CLI entrypoint for news processor daemon."""
    import argparse

    parser = argparse.ArgumentParser(description='Process news data')
    add_date_range_args(parser)
    parser.add_argument(
        '--source',
        type=str,
        required=False,
        help='Source (interfax, kommersant, vedomosti). If omitted, all sources are processed.',
    )
    parser.add_argument(
        '--gpu',
        action='store_true',
        help='Run sentiment model on GPU (falls back to CPU if CUDA is unavailable).',
    )

    args = parser.parse_args()
    source = NewsSource(args.source) if args.source else None

    date_range = asyncio.run(_resolve_range(args, source))
    if date_range is None:
        logger.info('News processor: nothing to do')
        return

    start_dt, end_dt = date_range
    logger.info('News processor range: %s -> %s', start_dt, end_dt)
    NewsProcessorDaemon(start_dt, end_dt, source, use_gpu=args.gpu).run()


if __name__ == '__main__':
    main()
