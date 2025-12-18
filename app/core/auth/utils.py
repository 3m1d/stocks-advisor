from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config.settings import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=['bcrypt'])


def encode_jwt(
    payload: dict,
    private_key: str = settings.jwt.private_key_path.read_text(),
    algorithm: str = settings.jwt.algorithm,
    expire_minutes: int = settings.jwt.access_token_expire_minutes,
) -> str:
    """JWT encoding function"""
    to_encode = payload.copy()

    # Add fields `exp` and `iat` to payload
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)
    to_encode.update(exp=expire, iat=now)

    token = jwt.encode(to_encode, private_key, algorithm=algorithm)
    return token


def decode_jwt(
    token: str, public_key: str = settings.jwt.public_key_path.read_text(), algorithm: str = settings.jwt.algorithm
) -> dict:
    """JWT decoding function"""
    payload = jwt.decode(token, public_key, algorithms=[algorithm])
    return payload


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Password verifying password

    Args:
        plain_password (str): Password to verify
        hashed_password (str): Existing password hash

    Returns:
        bool: If password is verified
    """
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Password hashing function

    Args:
        password (str): Password to hash

    Returns:
        str: Hashed password
    """
    return pwd_context.hash(password)
