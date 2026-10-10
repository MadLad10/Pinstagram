from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRETS = {"changeme", "change_me_run_openssl_rand_hex_32", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://app:app@localhost:5432/bdvisual"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "changeme"
    JWT_ACCESS_TTL_MIN: int = 15
    JWT_REFRESH_TTL_DAYS: int = 30

    S3_ENDPOINT: str = "http://localhost:9000"
    # Base URL clients use to reach stored media and presigned uploads. Differs
    # from S3_ENDPOINT when the API talks to storage over a private network.
    S3_PUBLIC_URL: str = ""
    S3_REGION: str = "us-east-1"
    S3_BUCKET: str = "bdvisual-media"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"

    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_MAPS_API_KEY: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = "no-reply@example.com"

    # Comma-separated list of allowed browser origins (the admin dashboard).
    CORS_ORIGINS: str = "http://localhost:3001"
    RATE_LIMIT_ENABLED: bool = True
    FREE_POSTS_PER_DAY: int = 5

    ENV: str = "local"

    @property
    def s3_public_base(self) -> str:
        return (self.S3_PUBLIC_URL or self.S3_ENDPOINT).rstrip("/")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.ENV == "production" and self.JWT_SECRET in _INSECURE_SECRETS:
            raise ValueError("JWT_SECRET must be set to a strong value in production")
        return self


settings = Settings()
