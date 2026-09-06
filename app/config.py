"""
ContentForge — Application Configuration
Loads settings from .env file and environment variables.
"""
import os

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

# Vercel's function filesystem is read-only except /tmp, so the relative SQLite
# default cannot even be created there. Only steps in when nothing else was
# configured — a DATABASE_URL (Neon, etc.) always wins. Note /tmp is private to
# each function instance and wiped on cold start; it keeps the app up, but a
# shared database is what makes an n8n callback land where the run was made.
if os.environ.get("VERCEL") and settings.database_url == "sqlite:///contentforge.db":
    settings.database_url = "sqlite:////tmp/contentforge.db"