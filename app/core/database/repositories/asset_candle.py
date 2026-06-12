from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import Date, cast, desc, func, select
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

    async def get_latest_begin_date(self) -> date | None:
        query = select(func.max(cast(AssetCandle.begin, Date)))
        async with self.session.begin():
            latest = await self.session.scalar(query)
        return latest

    async def get_dataframe(
        self,
        ticker: str | None = None,
        limit: int | None = None,
        date_start: datetime | None = None,
        date_end: datetime | None = None,
    ) -> pd.DataFrame:
        query = select(AssetCandle).order_by(desc(AssetCandle.begin))
        if ticker is not None:
            query = query.where(AssetCandle.ticker == ticker)
        if date_start is not None:
            query = query.where(AssetCandle.begin >= date_start)
        if date_end is not None:
            query = query.where(AssetCandle.begin <= date_end)
        if limit is not None:
            query = query.limit(limit)

        async with self.session.begin():
            result = await self.session.execute(query)
            candles = result.scalars().all()

        if not candles:
            return pd.DataFrame()

        data = []
        for candle in reversed(candles):
            data.append(
                {
                    'begin': candle.begin,
                    'open': float(candle.open),
                    'high': float(candle.high),
                    'low': float(candle.low),
                    'close': float(candle.close),
                    'volume': float(candle.volume),
                    'value': float(candle.value) if candle.value else None,
                    'ticker': candle.ticker,
                }
            )

        return pd.DataFrame(data)

    async def get_dataframe_by_ticker(
        self,
        ticker: str | None = None,
        limit: int | None = None,
        date_start: datetime | None = None,
        date_end: datetime | None = None,
    ) -> dict[str, pd.DataFrame]:
        df = await self.get_dataframe(
            ticker=ticker,
            limit=limit,
            date_start=date_start,
            date_end=date_end,
        )
        if df.empty:
            return {}
        return {
            str(ticker_symbol): ticker_df.reset_index(drop=True)
            for ticker_symbol, ticker_df in df.groupby('ticker', sort=True)
        }
