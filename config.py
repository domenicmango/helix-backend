from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = ""
    SECRET_KEY: str = "helix-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200
    DB_PATH: str = "./helix.db"
    BASE_CURRENCY: str = "EUR"
    ENVIRONMENT: str = "development"
    ENCRYPTION_KEY: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
