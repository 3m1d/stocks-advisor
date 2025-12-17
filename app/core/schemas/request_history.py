from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RequestHistoryResponse(BaseModel):
    id: int
    request_datetime: datetime
    created_at: datetime
    processing_time_ms: float
    method: str
    endpoint: str
    status_code: int
    request_body: dict[str, Any] | None = None
    response_body: dict[str, Any] | None = None
    request_size_bytes: int | None = None

    model_config = {'from_attributes': True}


class HistoryListResponse(BaseModel):
    items: list[RequestHistoryResponse]
    total: int
    limit: int
    offset: int
