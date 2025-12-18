from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import ValidationError

from app.config.settings import get_settings
from app.core.auth.utils import decode_jwt, verify_password
from app.core.schemas.jwt_auth import TokenPayload, UserSchema

TokenDep = Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())]
CredsDep = Annotated[HTTPBasicCredentials, Depends(HTTPBasic())]

settings = get_settings()


async def authenticate_user(credentials: CredsDep) -> UserSchema:
    """Create UserSchema from BasicAuth credentials, also check if credentials are match admin creds

    Args:
        credentials (CredsDep): BasicAuth credentials

    Returns:
        UserSchema: Schema representing user
    """
    username, password = credentials.username, credentials.password
    is_admin = username == settings.jwt.admin_username and verify_password(password, settings.jwt.admin_password_hash)
    user = UserSchema(
        username=username,
        password=password,
        is_admin=is_admin,
    )
    return user


async def get_token_payload(credentials: TokenDep) -> TokenPayload:
    """Extract payload from token

    Args:
        credentials (TokenDep): AuthorizationCredentials with token

    Raises:
        HTTPException: If token is invalid

    Returns:
        TokenPayload: Decoded token payload
    """
    token = credentials.credentials
    try:
        payload = decode_jwt(token=token)
        return TokenPayload(**payload)

    except InvalidTokenError or ValidationError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='Invalid token')


async def require_admin(token_payload: Annotated[TokenPayload, Depends(get_token_payload)]) -> TokenPayload:
    """
    Dependency to check if user is admin
    Check is_admin field in token payload

    Args:
        token_payload (Annotated[TokenPayload, Depends): Decoded token payload

    Raises:
        HTTPException: If user is not admin

    Returns:
        TokenPayload: If user is admin
    """
    if not token_payload.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail='Insufficient permissions')
    return token_payload
