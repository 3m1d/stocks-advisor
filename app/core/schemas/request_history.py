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
    query_params: dict[str, Any] | None = None
    response_body: dict[str, Any] | None = None
    request_size_bytes: int | None = None

    model_config = {'from_attributes': True}


class HistoryListResponse(BaseModel):
    items: list[RequestHistoryResponse]
    total: int
    limit: int
    offset: int


class HistoryDeleteResponse(BaseModel):
    deleted_count: int


class ProcessingTimeStats(BaseModel):
    mean_ms: float | None = None
    p50_ms: float | None = None
    p95_ms: float | None = None
    p99_ms: float | None = None


class RequestStats(BaseModel):
    mean_size_bytes: int | None = None


class StatsResponse(BaseModel):
    processing_time: ProcessingTimeStats
    request_stats: RequestStats
