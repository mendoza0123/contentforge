"""
ContentForge — Application Configuration
Loads settings from .env file and environment variables.
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""

    # Serper.dev
    serper_api_key: str = ""

    # Database
    database_url: str = "sqlite:///contentforge.db"

    # JWT Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True

    # Optional: fal.ai (Phase 5)
    fal_api_key: str = ""

    # Optional: n8n (Phase 4)
    n8n_base_url: str = ""
    n8n_api_key: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton
settings = Settings()