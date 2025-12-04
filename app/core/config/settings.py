import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
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

    host: str = Field(
        default_factory=lambda: os.getenv('DB_HOST', ''),
        description='Host (DB_HOST env)',
    )
    port: str = Field(
        default_factory=lambda: os.getenv('DB_PORT', ''),
        description='Port (DB_PORT env)',
    )
    name: str = Field(
        default_factory=lambda: os.getenv('DB_DATABASE', ''),
        description='Database (DB_DATABASE env)',
    )
    user: str = Field(
        default_factory=lambda: os.getenv('DB_USER', ''),
        description='User (DB_USER env)',
    )
    password: str = Field(
        default_factory=lambda: os.getenv('DB_PASSWORD', ''),
        description='Password (DB_PASSWORD env)',
    )
    ssl_mode: str = Field(default='prefer', description='SSL mode for PostgreSQL connection')

    @property
    def url(self) -> str:
        return f'postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}'


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
        toml_file='config.toml',
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
        project_root = Path(__file__).parent.parent.parent.parent
        config_file = project_root / 'config.toml'

        sources = [
            init_settings,  # Explicit init values
            env_settings,  # Environment variables
            dotenv_settings,  # .env file
        ]

        if config_file.exists():
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=str(config_file)))

        return tuple(sources)
