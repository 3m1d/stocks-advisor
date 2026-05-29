from typing import Any
import pandas as pd
from sqlalchemy import select, desc
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
        if batch_size <= 0:
            raise ValueError('batch_size must be greater than 0')

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
            .on_conflict_do_nothing(constraint='unique_ticker_begin')
            .returning(AssetCandle.ticker, AssetCandle.begin)
            .execution_options(insertmanyvalues_page_size=batch_size)
        )

        async with self.session.begin():
            result = await self.session.execute(stmt, payload)
            return len(result.all())

    async def get_dataframe_by_ticker(self, ticker: str, limit: int) -> pd.DataFrame:
        query = (
            select(AssetCandle)
            .where(AssetCandle.ticker == ticker)
            .order_by(desc(AssetCandle.begin))
            .limit(limit)
        )

        async with self.session.begin():
            result = await self.session.execute(query)
            candles = result.scalars().all()
        
        if not candles:
            return pd.DataFrame()
        
        data = []
        for candle in reversed(candles):
            data.append({
                'begin': candle.begin,
                'open': float(candle.open),
                'high': float(candle.high),
                'low': float(candle.low),
                'close': float(candle.close),
                'volume': float(candle.volume),
                'value': float(candle.value) if candle.value else None,
                'ticker': candle.ticker
            })
        
        return pd.DataFrame(data)
