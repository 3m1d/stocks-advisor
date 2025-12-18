from fastapi import APIRouter, Depends

from app.api.deps import authenticate_user
from app.core.auth.utils import encode_jwt
from app.core.schemas.jwt_auth import TokenInfo, UserSchema

router = APIRouter(prefix='/jwt', tags=['JWT'])


@router.post('/login', response_model=TokenInfo)
async def login_access_token(user: UserSchema = Depends(authenticate_user)):
    jwt_payload = {'sub': user.username, 'is_admin': user.is_admin}
    token = encode_jwt(jwt_payload)
    return TokenInfo(access_token=token, token_type='Bearer')
