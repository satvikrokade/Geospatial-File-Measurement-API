from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', case_sensitive=False, extra='ignore')
    app_name: str = 'Geospatial Measurement API'
    app_env: str = Field(default='development', pattern='^(development|production|testing)$')
    debug: bool = False
    api_v1_prefix: str = '/api/v1'
    cors_origins: list[str] = ['http://localhost:8000']

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v
    secret_key: str = Field(..., min_length=32)
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    postgres_host: str = 'localhost'
    postgres_port: int = 5432
    postgres_db: str = 'geospatial'
    postgres_user: str = 'geouser'
    postgres_password: str = 'geopassword'
    database_url: str | None = None

    @model_validator(mode='after')
    def assemble_db_url(self) -> 'Settings':
        if not self.database_url:
            self.database_url = f'postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}'
        return self

    @property
    def sync_database_url(self) -> str:
        if self.database_url:
            return self.database_url.replace('+asyncpg', '+psycopg2')
        return f'postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}'
    redis_url: str = 'redis://localhost:6379/0'
    upload_dir: Path = Path('./uploads')
    max_file_size_mb: int = 50
    async_processing_threshold_mb: int = 5

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def async_threshold_bytes(self) -> int:
        return self.async_processing_threshold_mb * 1024 * 1024
    rate_limit_per_minute: int = 60
    log_level: str = 'INFO'
    log_json: bool = True
    report_logo_path: Path = Path('/app/static/logo.png')

@lru_cache
def get_settings() -> Settings:
    return Settings()
