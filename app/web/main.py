from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import FastAPI

from app.core.config import get_settings, setup_logging
from app.core.database import DBSession, engine
from app.core.processors import StockParserProcessor

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
    processor = StockParserProcessor(session)
    count = await processor.parse(
        datetime.combine(start_date, datetime.min.time()),
        datetime.combine(end_date, datetime.min.time()),
    )
    return {'message': f'Parsed {start_date} to {end_date}', 'records_processed': count}
