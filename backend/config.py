from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRY: int = 3600
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "gemma3"

    # The repository itself is available as a project out of the box. Users can
    # add/replace entries through the PROJECTS JSON setting in backend/.env.
    PROJECTS: dict[str, str] = {
        "AI-chatbot-localmodel": str(Path(__file__).resolve().parent.parent)
    }
    DEFAULT_PROJECT: str = "AI-chatbot-localmodel"
    RAG_EMBED_MODEL: str = "nomic-embed-text"

    model_config = SettingsConfigDict(
        # resolve .env next to this file, whatever directory uvicorn starts from
        env_file=Path(__file__).parent / ".env",
        extra="ignore",
    )


Config = Settings()
