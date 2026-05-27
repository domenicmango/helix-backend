import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "helix-secret")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200
    DB_PATH: str = os.environ.get("DB_PATH", "./helix.db")
    BASE_CURRENCY: str = os.environ.get("BASE_CURRENCY", "EUR")
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")
    ENCRYPTION_KEY: str = os.environ.get("ENCRYPTION_KEY", "")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
