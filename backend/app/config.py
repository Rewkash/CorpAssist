from pydantic_settings import BaseSettings, SettingsConfigDict


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

    gpt_api_key: str | None = None
    gpt_api_url: str | None = None

    @property
    def database_url(self) -> str:
        return (
            f'postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}'
            f'@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}'
        )


settings = Settings()
