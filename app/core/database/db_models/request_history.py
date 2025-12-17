from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, TIMESTAMP, BigInteger, Enum, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.db_models.base import Base


class HTTPMethodEnum(StrEnum):
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'


class RequestHistory(Base):
    """История API запросов"""

    __tablename__ = 'request_history'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    request_datetime: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP'),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP'),
    )
    processing_time_ms: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)

    method: Mapped[HTTPMethodEnum] = mapped_column(Enum(HTTPMethodEnum, native_enum=False), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(BigInteger, nullable=False)

    request_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    request_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        Index('idx_request_history_datetime', 'request_datetime'),
        Index('idx_request_history_method', 'method'),
        Index('idx_request_history_endpoint', 'endpoint'),
        Index('idx_request_history_status_code', 'status_code'),
    )

    def __repr__(self) -> str:
        return f'<RequestHistory(id={self.id}, method={self.method}, endpoint={self.endpoint!r})>'
