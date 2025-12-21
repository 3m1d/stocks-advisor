from datetime import date, datetime

from fastapi import APIRouter

from app.core.database.session import DBSession
from app.core.processors.asset_parser import AssetParserProcessor
from app.core.schemas import ParseResponse

router = APIRouter(prefix='/parse', tags=['Parse'])


@router.post('/', response_model=ParseResponse)
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
