from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/documind"
    REDIS_URL: str = "redis://localhost:6379/0"
    AI_API_KEY: str = ""
    AI_PROVIDER: str = "anthropic"
    AI_MODEL: str = "claude-sonnet-4-5-20250514"
    MAX_FILE_SIZE_MB: int = 50

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
