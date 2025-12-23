import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pwdlib import PasswordHash
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent

password_hash = PasswordHash.recommended()


class AppSettings(BaseModel):
    name: str = 'stocks-advisor'
    version: str = '0.1.0'
    debug: bool = False
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'


class DatabaseSettings(BaseModel):
    """Настройки PostgreSQL"""

    host: str = Field(..., description='Host (DATABASE__HOST env)')
    port: str = Field(..., description='Port (DATABASE__PORT env)')
    name: str = Field(..., description='Database (DATABASE__NAME env)')
    user: str = Field(..., description='User (DATABASE__USER env)')
    password: str = Field(..., description='Password (DATABASE__PASSWORD env)')
    ssl_mode: str = Field(default='prefer', description='SSL mode for PostgreSQL connection')

    @property
    def url_async(self) -> str:
        return f'postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}'

    @property
    def url_sync(self) -> str:
        return f'postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}'


class MOEXSettings(BaseModel):
    """Настройки MOEX API клиента"""

    base_url: str = 'https://iss.moex.com/iss'
    timeout_connect: int = 30
    timeout_sock_read: int = 60
    timeout_total: int = 120


class APISettings(BaseModel):
    """Настройки сервера FastAPI"""

    host: str = '0.0.0.0'
    port: int = 8000
    reload: bool = False
    workers: int = 1

    V1: str = '/api/v1'


class AuthJWTSettings(BaseModel):
    """Настройки для JWT аутентификации"""

    private_key_path: Path = PROJECT_ROOT / 'app' / 'certs' / 'jwt-private.pem'
    public_key_path: Path = PROJECT_ROOT / 'app' / 'certs' / 'jwt-public.pem'

    algorithm: str = 'RS256'
    access_token_expire_minutes: int = Field(
        default=30, description='Access token expiration time in minutes (JWT__ACCESS_TOKEN_EXPIRE_MINUTES env)'
    )

    admin_username: str = Field(..., description='Admin username (JWT__ADMIN_USERNAME env)')
    admin_password_hash: str = Field(..., description='Admin password hash (argon2) (JWT__ADMIN_PASSWORD_HASH env)')

    @field_validator('admin_password_hash', mode='before')
    @classmethod
    def validate_admin_password_hash(cls, value: str) -> str:
        if not password_hash.current_hasher.identify(value):
            raise ValueError(
                f'Invalid Argon2 hash format. Expected a hash starting with $argon2, '
                f'but got: {value[:50]}{"..." if len(value) > 50 else ""}'
            )
        return value


class LoggingSettings(BaseModel):
    """Настройки логгера"""

    format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format: str = '%Y-%m-%d %H:%M:%S'


class Settings(BaseSettings):
    """Настройки приложения.

    Откуда берем настройки:
    - Основные настройки приложения: название файла берем из APP_CONFIG. По умолчанию - config.toml
    - Секреты: .env файл или переменные окружения
    """

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    moex: MOEXSettings = Field(default_factory=MOEXSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    jwt: AuthJWTSettings = Field(default_factory=AuthJWTSettings)

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_nested_delimiter='__',
        case_sensitive=False,
        extra='ignore',
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        config_file = os.getenv('APP_CONFIG', 'config.toml')
        config_file = PROJECT_ROOT / config_file

        toml_config = TomlConfigSettingsSource(settings_cls, toml_file=str(config_file))
        # Toml has higher priority than env variables
        sources = [
            init_settings,
            toml_config,
            dotenv_settings,
            env_settings,
        ]

        return tuple(sources)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def setup_logging(settings: Settings | None = None) -> None:
    if settings is None:
        settings = get_settings()

    log_level = getattr(logging, settings.app.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format=settings.logging.format,
        datefmt=settings.logging.date_format,
        force=True,
    )

    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
