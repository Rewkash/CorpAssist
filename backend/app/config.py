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

    ollama_base_url: str = 'http://ollama:11434'
    ollama_model: str = 'gemma3:4b'
    embedding_model: str = 'bge-m3'
    embedding_dim: int = 1024

    rag_top_k: int = 5
    rag_min_score: float = 0.45
    rag_max_chars_per_chunk: int = 1200

    semantic_cache_enabled: bool = True
    semantic_cache_threshold: float = 0.92
    semantic_cache_ttl_seconds: int = 3 * 24 * 60 * 60

    @property
    def database_url(self) -> str:
        return (
            f'postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}'
            f'@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}'
        )


settings = Settings()
