import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


class AppSettings(BaseModel):
    name: str = 'stocks-advisor'
    version: str = '0.1.0'
    debug: bool = False
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'


class DatabaseSettings(BaseModel):
    """Настройки PostgreSQL"""

    host: str = Field(default='', description='Host (DATABASE__HOST env)')
    port: str = Field(default='', description='Port (DATABASE__PORT env)')
    name: str = Field(default='', description='Database (DATABASE__NAME env)')
    user: str = Field(default='', description='User (DATABASE__USER env)')
    password: str = Field(default='', description='Password (DATABASE__PASSWORD env)')
    ssl_mode: str = Field(default='prefer', description='SSL mode for PostgreSQL connection')

    @model_validator(mode='after')
    def validate_required_fields(self) -> 'DatabaseSettings':
        required_fields = {
            'host': self.host,
            'port': self.port,
            'name': self.name,
            'user': self.user,
            'password': self.password,
        }
        missing = [field for field, value in required_fields.items() if not value]
        if missing:
            env_vars = {
                'host': 'DB_HOST',
                'port': 'DB_PORT',
                'name': 'DB_DATABASE',
                'user': 'DB_USER',
                'password': 'DB_PASSWORD',
            }
            missing_env_vars = [env_vars[field] for field in missing]
            raise ValueError(
                f'Missing required database configuration: {", ".join(missing)}. '
                f'Please set the following environment variables: {", ".join(missing_env_vars)}'
            )
        return self

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


class LoggingSettings(BaseModel):
    """Настройки логгера"""

    format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format: str = '%Y-%m-%d %H:%M:%S'


class Settings(BaseSettings):
    """Настройки приложения.

    Откуда берем настройки:
    - Основные настройки приложения: config.toml
    - Секреты: .env файл или переменные окружения
    """

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    moex: MOEXSettings = Field(default_factory=MOEXSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

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
        # Find config.toml in project root
        project_root = Path(__file__).parent.parent.parent
        config_file = project_root / 'config.toml'

        sources = [
            init_settings,  # Explicit init values
            env_settings,  # Environment variables
            dotenv_settings,  # .env file
        ]

        if config_file.exists():
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=str(config_file)))

        return tuple(sources)


@lru_cache
def get_settings():
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
