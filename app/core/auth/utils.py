from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config.settings import get_settings

settings = get_settings()

password_hash = PasswordHash.recommended()


def encode_jwt(
    payload: dict,
    private_key: str | None = None,
    algorithm: str | None = None,
    expire_minutes: int | None = None,
) -> str:
    """JWT encoding function"""
    private_key = private_key if private_key is not None else settings.jwt.private_key_path.read_text()
    algorithm = algorithm if algorithm is not None else settings.jwt.algorithm
    expire_minutes = expire_minutes if expire_minutes is not None else settings.jwt.access_token_expire_minutes
    to_encode = payload.copy()

    # Add fields `exp` and `iat` to payload
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)
    to_encode.update(exp=expire, iat=now)

    token = jwt.encode(to_encode, private_key, algorithm=algorithm)
    return token


def decode_jwt(token: str, public_key: str | None = None, algorithm: str | None = None) -> dict:
    """JWT decoding function"""
    public_key = public_key if public_key else settings.jwt.public_key_path.read_text()
    algorithm = algorithm if algorithm else settings.jwt.algorithm
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
    return password_hash.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Password hashing function

    Args:
        password (str): Password to hash

    Returns:
        str: Hashed password
    """

    return password_hash.hash(password)
