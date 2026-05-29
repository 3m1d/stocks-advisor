import json
import logging
import time
import zoneinfo
from datetime import datetime

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import get_settings
from app.core.database import RequestHistoryRepository
from app.core.database.db_models.request_history import HTTPMethodEnum
from app.core.database.session import async_session_factory

settings = get_settings()
logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Writes requests history into database"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_datetime = datetime.now(zoneinfo.ZoneInfo('Europe/Moscow')).replace(tzinfo=None)

        if request.method not in HTTPMethodEnum:
            # Can't log, skipping
            logger.error(
                'Unsupported HTTP method',
                extra={
                    'endpoint': request.url.path,
                    'method': request.method,
                },
            )
            return await call_next(request)

        method = HTTPMethodEnum(request.method)
        path = request.url.path

        # Don't log ignored prefixes
        for prefix in settings.history.ignored_path_prefixes:
            if path.startswith(prefix):
                return await call_next(request)

        request_body, query_params, request_size_bytes = await self._parse_request_body(request)
        response, response_time_ms = await self._process_request(request, call_next)

        response_body = await self._parse_response_body(path, method, response)

        status_code = response.status_code

        await self._save_history(
            request_path=path,
            request_method=method,
            request_body=request_body,
            query_params=query_params,
            response_body=response_body,
            processing_time_ms=response_time_ms,
            request_size_bytes=request_size_bytes,
            status_code=status_code,
            request_datetime=request_datetime,
        )

        return response

    async def _process_request(self, request: Request, call_next: RequestResponseEndpoint) -> tuple[Response, int]:
        processing_start = time.perf_counter()
        response = await call_next(request)
        processing_time_ms = int(time.perf_counter() - processing_start) * 1000
        return response, processing_time_ms

    @classmethod
    async def _parse_request_body(cls, request: Request) -> tuple[dict, dict, int]:
        request_body = {}
        query_params = {}
        request_size_bytes = 0

        # Parse query params
        if request.url.query:
            query_params = dict(request.query_params)

        try:
            if request.method in ['POST', 'PUT']:
                body: bytes = await request.body()
                request_size_bytes = len(body)

                if body:
                    body_utf8 = body.decode('utf-8')
                    try:
                        body_data = json.loads(body_utf8)
                        if isinstance(body_data, dict):
                            request_body = body_data
                        else:
                            request_body = {'body': body_data}
                    except json.JSONDecodeError:
                        request_body = {'body': body_utf8}
        except Exception:
            logger.exception(
                'Failed to parse request body',
                extra={
                    'endpoint': request.url.path,
                    'method': request.method,
                },
            )
        return request_body, query_params, request_size_bytes

    @classmethod
    async def _parse_response_body(
        cls,
        request_path: str,
        request_method: HTTPMethodEnum,
        response: Response,
    ):
        response_body = {}
        try:
            if hasattr(response, 'body'):
                body: bytes = await response.body

                if len(body) >= settings.history.max_response_size:
                    response_body = {}

                if body:
                    body_utf8 = body.decode('utf-8')
                    try:
                        response_body = json.loads(body_utf8)
                    except json.JSONDecodeError:
                        response_body = {'body': body_utf8}
        except Exception:
            logger.exception(
                'Failed to parse response body',
                extra={
                    'endpoint': request_path,
                    'method': request_method,
                },
            )
        return response_body

    async def _save_history(
        self,
        request_path: str,
        request_method: HTTPMethodEnum,
        request_body: dict,
        query_params: dict,
        response_body: dict,
        processing_time_ms: int,
        request_size_bytes: int,
        status_code: int,
        request_datetime: datetime,
    ) -> None:
        try:
            async with async_session_factory() as session:
                repo = RequestHistoryRepository(session)
                await repo.create(
                    method=request_method,
                    endpoint=request_path,
                    request_body=request_body if request_body else None,
                    query_params=query_params if query_params else None,
                    response_body=response_body if response_body else None,
                    processing_time_ms=processing_time_ms,
                    request_size_bytes=request_size_bytes,
                    status_code=status_code,
                    request_datetime=request_datetime,
                )
        except Exception as e:
            logger.exception(
                'Failed to save request history to database',
                extra={
                    'endpoint': request_path,
                    'method': request_method,
                    'status_code': status_code,
                    'error': str(e),
                },
            )
