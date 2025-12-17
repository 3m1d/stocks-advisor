import logging
from sqlalchemy.sql.selectable import Select


from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import delete, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.db_models.request_history import HTTPMethodEnum, RequestHistory
from app.core.schemas.request_history import ProcessingTimeStats, RequestStats, StatsResponse


logger = logging.getLogger(__name__)


class RequestHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        method: HTTPMethodEnum,
        endpoint: str,
        processing_time_ms: float,
        status_code: int,
        request_body: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        response_body: dict[str, Any] | None = None,
        request_size_bytes: int | None = None,
        request_datetime: datetime | None = None,
    ) -> RequestHistory:
        record = RequestHistory(
            method=method,
            endpoint=endpoint,
            request_body=request_body,
            query_params=query_params,
            response_body=response_body,
            processing_time_ms=processing_time_ms,
            request_size_bytes=request_size_bytes,
            status_code=status_code,
            request_datetime=request_datetime,
        )
        self.session.add(record)
        return record

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        endpoint: str | None = None,
        method: HTTPMethodEnum | None = None,
    ) -> Sequence[RequestHistory]:
        q = select(RequestHistory).order_by(
            RequestHistory.created_at.desc(),
            RequestHistory.id.desc(),
        )

        if endpoint:
            q = q.where(RequestHistory.endpoint == endpoint)
        if method:
            q = q.where(RequestHistory.method == method)

        q = q.limit(limit).offset(offset)
        result = await self.session.scalars(q)
        return result.all()

    async def count(
        self,
        endpoint: str | None = None,
        method: HTTPMethodEnum | None = None,
    ) -> int:
        q = select(func.count(RequestHistory.id))

        if endpoint:
            q = q.where(RequestHistory.endpoint == endpoint)
        if method:
            q = q.where(RequestHistory.method == method)

        result = await self.session.scalar(q)
        return result or 0

    async def delete_all(self) -> int:
        # Подзапрос, который удаляет записи и возвращает 1 для каждой удаленной записи
        q = delete(RequestHistory).returning(literal(1)).cte('deleted')

        # Запрос, который считает количество удаленных записей
        q2 = select(func.count()).select_from(q)
        count = await self.session.scalar(q2)
        return int(count or 0)

    async def get_stats(self) -> StatsResponse:
        # Averages and quantiles
        processing_time_stats = await self.session.execute(
            select(
                func.avg(RequestHistory.processing_time_ms).label('mean'),
                func.percentile_cont(0.50).within_group(RequestHistory.processing_time_ms).label('p50'),
                func.percentile_cont(0.95).within_group(RequestHistory.processing_time_ms).label('p95'),
                func.percentile_cont(0.99).within_group(RequestHistory.processing_time_ms).label('p99'),
            )
        )
        time_stats = processing_time_stats.first()

        # Request size stats
        request_size_stats = await self.session.execute(
            select(
                func.avg(RequestHistory.request_size_bytes).label('mean_bytes'),
            ).where(RequestHistory.request_size_bytes.isnot(None))
        )
        size_stats = request_size_stats.first()

        return StatsResponse(
            processing_time=ProcessingTimeStats(
                mean_ms=float(time_stats.mean) if time_stats and time_stats.mean else None,
                p50_ms=float(time_stats.p50) if time_stats and time_stats.p50 else None,
                p95_ms=float(time_stats.p95) if time_stats and time_stats.p95 else None,
                p99_ms=float(time_stats.p99) if time_stats and time_stats.p99 else None,
            ),
            request_stats=RequestStats(
                mean_size_bytes=int(size_stats.mean_bytes) if size_stats and size_stats.mean_bytes else None
            ),
        )
