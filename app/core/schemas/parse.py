from pydantic import BaseModel


class ParseResponse(BaseModel):
    message: str
    parsed_count: int
    saved_count: int
