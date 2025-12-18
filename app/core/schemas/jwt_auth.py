from pydantic import BaseModel


class UserSchema(BaseModel):
    username: str
    password: str
    is_admin: bool


class TokenInfo(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: str
    is_admin: bool
