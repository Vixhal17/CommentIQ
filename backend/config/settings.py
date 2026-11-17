from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    SHADOW_MODE: bool = True
    AUTO_PUBLISH_ENABLED: bool = False

    # Security (Fernet encryption key for OAuth tokens)
    FERNET_SECRET_KEY: str = Field(
        default="y-GqU-s6N2uKk_k_H6FzV8D3n-E8M5e4b2d3Z1x9w8A=",
        description="Fernet key for encrypting stored OAuth refresh tokens"
    )

    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./test.db",
        description="Database connection string (PostgreSQL for prod, SQLite for standalone test)"
    )

    # LLM Providers (OpenAI compatible)
    GROQ_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"

    # Daily Token Budget
    DAILY_TOKEN_BUDGET: int = 100000

    # Google OAuth (YouTube Data API v3 - Testing Mode)
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/youtube/callback"

    # Celery / Redis (Optional Worker Scaling)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Config Path
    LLM_CONFIG_PATH: Path = BASE_DIR / "config" / "llm_config.yaml"

settings = Settings()

