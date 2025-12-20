from fastapi import APIRouter

from app.core.database import DBSession, RequestHistoryRepository
from app.core.schemas import StatsResponse

router = APIRouter(prefix='/stats', tags=['Stats'])


@router.get('/', response_model=StatsResponse)
async def get_stats(session: DBSession) -> StatsResponse:
    """Requests stats"""
    repo = RequestHistoryRepository(session)
    return await repo.get_stats()
