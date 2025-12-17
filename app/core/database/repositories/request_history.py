from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.db_models.request_history import HTTPMethodEnum, RequestHistory


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
        await self.session.flush()
        return record
