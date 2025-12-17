from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.db_models.asset_candle import AssetCandle


class AssetCandleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_upsert(self, records: list[dict[str, Any]], batch_size: int = 10_000) -> int:
        """Insert stock price records, skip duplicates."""
        if not records:
            return 0

        result_count = 0
        for i in range(0, len(records), batch_size):
            records_batch = records[i : i + batch_size]

            payload = [
                {
                    'ticker': r['ticker'],
                    'begin': r['begin'],
                    'end': r['end'],
                    'open': r['open'],
                    'close': r['close'],
                    'high': r['high'],
                    'low': r['low'],
                    'value': r.get('value'),
                    'volume': r['volume'],
                }
                for r in records_batch
            ]

            stmt = (
                insert(AssetCandle)
                .values(payload)
                .on_conflict_do_nothing(constraint='unique_ticker_begin')
                .returning(AssetCandle.ticker, AssetCandle.begin)
            )
            result = await self.session.execute(stmt)
            result_count += len(result.all())
        return result_count
