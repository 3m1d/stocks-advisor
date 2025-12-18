import jwt

from app.config.settings import get_settings

settings = get_settings()


def encode_jwt(
    payload: dict, private_key: str = settings.jwt.private_key_path.read_text(), algorithm: str = settings.jwt.algorithm
) -> str:
    """JWT encoding function"""
    token = jwt.encode(payload, private_key, algorithm=algorithm)
    return token


def decode_jwt(
    token: str, public_key: str = settings.jwt.public_key_path.read_text(), algorithm: str = settings.jwt.algorithm
) -> dict:
    """JWT decoding function"""
    payload = jwt.decode(token, public_key, algorithms=[algorithm])
    return payload
