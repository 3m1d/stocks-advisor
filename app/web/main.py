from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import FastAPI
from sqlalchemy.dialects.postgresql import insert

from app.core.clients.moex import Boards, Engines, Interval, Markets, MOEXClient, Ticker
from app.core.config import get_settings, setup_logging
from app.core.database import DBSession, engine
from app.core.database.db_models.stock_price import StockPrice

# Setup logging before creating the app
settings = get_settings()
setup_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    debug=settings.app.debug,
    lifespan=lifespan,
)


@app.get('/')
async def root():
    return {'message': 'Hello World'}


@app.post('/parse')
async def parse_stock_data(start_date: date, end_date: date, session: DBSession):
    """Parse MOEX stock data for a date range and insert into database."""
    client = MOEXClient()
    tickers = list(Ticker)

    data = await client.get_data(
        tickers=tickers,
        engine=Engines.STOCK,
        market=Markets.SHARES,
        board=Boards.TQBR,
        start_date=datetime.combine(start_date, datetime.min.time()),
        end_date=datetime.combine(end_date, datetime.min.time()),
        interval=Interval.HOUR_1,
    )

    inserted_count = 0
    for ticker, df in data.items():
        if df.empty:
            continue

        records = df.to_dict('records')
        for record in records:
            stmt = (
                insert(StockPrice)
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

            await session.execute(stmt)
            inserted_count += 1

    return {'message': f'Parsed {start_date} to {end_date}', 'records_processed': inserted_count}
