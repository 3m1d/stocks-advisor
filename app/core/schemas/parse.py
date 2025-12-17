from pydantic import BaseModel


class ParseResponse(BaseModel):
    message: str
    records_processed: int
