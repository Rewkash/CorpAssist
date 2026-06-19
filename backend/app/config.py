import logging
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'CorpAssist API'
    jwt_secret: str = 'change-me-in-production'
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = 60

    postgres_user: str = 'corpassist'
    postgres_password: str = 'corpassist'
    postgres_db: str = 'corpassist'
    postgres_host: str = 'postgres'
    postgres_port: int = 5432

    redis_url: str = 'redis://redis:6379/0'

    ollama_base_url: str = 'http://ollama:11434'
    ollama_model: str = 'gemma3:4b'
    enable_llm_debug: bool = False

    cors_origin: str = 'http://localhost:5173'

    @property
    def database_url(self) -> str:
        return (
            f'postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}'
            f'@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}'
        )


settings = Settings()

_INSECURE_SECRETS = {'change-me-in-production', 'super-secret-demo-key', 'secret', 'password'}


def check_jwt_secret() -> None:
    if os.getenv('JWT_SECRET') and settings.jwt_secret not in _INSECURE_SECRETS:
        return
    if settings.jwt_secret in _INSECURE_SECRETS:
        logger.warning(
            'JWT_SECRET uses an insecure default value (%r). '
            'Set a strong JWT_SECRET environment variable before deploying to production.',
            settings.jwt_secret,
        )
