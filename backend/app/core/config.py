from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://app:app@localhost:5432/bdvisual"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "changeme"
    JWT_ACCESS_TTL_MIN: int = 15
    JWT_REFRESH_TTL_DAYS: int = 30

    S3_ENDPOINT: str = "http://localhost:9000"
    S3_REGION: str = "us-east-1"
    S3_BUCKET: str = "bdvisual-media"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"

    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_MAPS_API_KEY: str = ""

    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = "no-reply@example.com"

    ENV: str = "local"


settings = Settings()
