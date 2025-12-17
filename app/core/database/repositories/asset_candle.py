from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.db_models.asset_candle import AssetCandle


class AssetCandleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> int:
        """Insert stock price records, skip duplicates."""
        if not records:
            return 0

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
            for r in records
        ]

        stmt = (
            insert(AssetCandle)
            .values(payload)
            .on_conflict_do_nothing(constraint='unique_ticker_begin')
            .returning(AssetCandle.ticker, AssetCandle.begin)
        )
        result = await self.session.execute(stmt)
        return len(result.all())
