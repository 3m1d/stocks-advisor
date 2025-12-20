from fastapi import APIRouter, Query

from app.core.database import DBSession, RequestHistoryRepository
from app.core.database.db_models.request_history import HTTPMethodEnum
from app.core.schemas import HistoryDeleteResponse, HistoryListResponse, RequestHistoryResponse, StatsResponse

router = APIRouter(prefix='/history', tags=['History'])


@router.get('/', response_model=HistoryListResponse)
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


@router.delete('/', response_model=HistoryDeleteResponse)
async def delete_history(
    session: DBSession,
) -> HistoryDeleteResponse:
    """Deletes an entire requests history"""
    repo: RequestHistoryRepository = RequestHistoryRepository(session)
    deleted_count = await repo.delete_all()
    await session.commit()

    return HistoryDeleteResponse(deleted_count=deleted_count)


@router.get('/stats', response_model=StatsResponse)
async def get_stats(session: DBSession) -> StatsResponse:
    """Requests stats"""
    repo = RequestHistoryRepository(session)
    return await repo.get_stats()
