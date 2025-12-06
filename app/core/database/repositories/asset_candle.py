from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.db_models.asset_candle import AssetCandle


class AssetCandleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> int:
        """Insert stock price records, skip duplicates."""
        count = 0
        for record in records:
            stmt = (
                insert(AssetCandle)
                .values(
                    ticker=record['ticker'],
                    begin=record['begin'],
                    end=record['end'],
                    open=record['open'],
                    close=record['close'],
                    high=record['high'],
                    low=record['low'],
                    value=record.get('value'),
                    volume=record['volume'],
                )
                .on_conflict_do_nothing(constraint='unique_ticker_begin')
            )
            await self.session.execute(stmt)
            count += 1
        return count
