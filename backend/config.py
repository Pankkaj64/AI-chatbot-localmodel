from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRY: int = 3600
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "gemma3"

    model_config = SettingsConfigDict(
        # resolve .env next to this file, whatever directory uvicorn starts from
        env_file=Path(__file__).parent / ".env",
        extra="ignore",
    )


Config = Settings()
