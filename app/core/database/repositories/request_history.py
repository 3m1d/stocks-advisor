import logging
from sqlalchemy.sql.selectable import Select


from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import delete, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.db_models.request_history import HTTPMethodEnum, RequestHistory


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
        response_body: dict[str, Any] | None = None,
        request_size_bytes: int | None = None,
        request_datetime: datetime | None = None,
    ) -> RequestHistory:
        record = RequestHistory(
            method=method,
            endpoint=endpoint,
            request_body=request_body,
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
        stmt = delete(RequestHistory).returning(literal(1))
        res = await self.session.execute(stmt)
        return len(res.scalars().all())
