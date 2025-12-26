"""
Configuration management using environment variables.
Follows 12-factor app principles.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite:////data/app.db",
        description="SQLite database URL",
    )
    
    # Logging
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    
    # Security
    WEBHOOK_SECRET: str = Field(
        default="",
        description="HMAC secret for webhook signature verification",
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
