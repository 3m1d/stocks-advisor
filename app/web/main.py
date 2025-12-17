from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import FastAPI, Query

from app.config import get_settings, setup_logging
from app.core.database import DBSession, RequestHistoryRepository, engine
from app.core.database.db_models.request_history import HTTPMethodEnum
from app.core.processors import AssetParserProcessor
from app.core.schemas import (
    HistoryDeleteResponse,
    HistoryListResponse,
    ParseResponse,
    RequestHistoryResponse,
    StatsResponse,
)
from app.web.middleware.request_logging import RequestLoggingMiddleware

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

# Middleware for saving requests history into database
app.add_middleware(RequestLoggingMiddleware)


@app.get('/')
async def root():
    return {'message': 'Hello World'}


@app.post('/parse', response_model=ParseResponse)
async def parse_stock_data(start_date: date, end_date: date, session: DBSession) -> ParseResponse:
    """Parse MOEX stock data for a date range and insert into database."""
    processor = AssetParserProcessor(session)
    parsed_count, saved_count = await processor.parse(
        datetime.combine(start_date, datetime.min.time()),
        datetime.combine(end_date, datetime.min.time()),
    )
    return ParseResponse(
        message=f'Parsed {start_date} to {end_date}', parsed_count=parsed_count, saved_count=saved_count
    )


@app.get('/history', response_model=HistoryListResponse)
async def get_history(
    session: DBSession,
    limit: int = Query(default=100, ge=1),
    offset: int = Query(default=0, ge=0),
    endpoint: str | None = None,
    method: HTTPMethodEnum | None = None,
) -> HistoryListResponse:
    """Get requests history from database"""
    repo = RequestHistoryRepository(session)
    items = await repo.get_all(limit=limit, offset=offset, endpoint=endpoint, method=method)
    total = await repo.count(endpoint=endpoint, method=method)

    return HistoryListResponse(
        items=[RequestHistoryResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.delete('/history', response_model=HistoryDeleteResponse)
async def delete_history(
    session: DBSession,
) -> HistoryDeleteResponse:
    """Deletes entire requests history"""
    repo: RequestHistoryRepository = RequestHistoryRepository(session)
    deleted_count = await repo.delete_all()
    await session.commit()

    return HistoryDeleteResponse(deleted_count=deleted_count)


@app.get('/stats', response_model=StatsResponse)
async def get_stats(session: DBSession) -> StatsResponse:
    """Requests stats"""
    repo = RequestHistoryRepository(session)
    return await repo.get_stats()
