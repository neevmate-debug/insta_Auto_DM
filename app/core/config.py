"""
Core application settings module.
Loads environment variables using Pydantic Settings.
Defaults are provided for development and local testing.
Actual credentials must be supplied via a local .env file or deployment environment variables.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment or .env file.
    """
    # Application details
    APP_NAME: str = "Instagram & Facebook Auto-DM System"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Meta Graph API & Webhook Configuration
    # These remain None / empty by default until explicitly provided in .env or environment
    META_APP_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None
    META_GRAPH_API_VERSION: str = "v21.0"
    META_GRAPH_API_BASE_URL: str = "https://graph.facebook.com"
    META_VERIFY_TOKEN: Optional[str] = None

    # Meta Page & Instagram Credentials
    META_PAGE_ACCESS_TOKEN: Optional[str] = None
    INSTAGRAM_ACCOUNT_ID: Optional[str] = None

    # Automation Rules
    AUTO_DM_TRIGGER_KEYWORD: Optional[str] = None
    AUTO_DM_RESPONSE_MESSAGE: str = "Thanks for your comment! Here is the link you requested: https://example.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the application settings.
    """
    return Settings()
