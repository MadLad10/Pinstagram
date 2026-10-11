from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRETS = {"changeme", "change_me_run_openssl_rand_hex_32", ""}


def normalize_database_url(url: str) -> str:
    """Accept the plain `postgres://...?sslmode=require` URLs that hosted
    providers (Neon, Render, Supabase) hand out, and convert them for asyncpg,
    which needs the +asyncpg driver and spells the TLS option `ssl`."""
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    query = []
    for key, value in parse_qsl(parts.query):
        if key == "sslmode":
            query.append(("ssl", value))
        elif key != "channel_binding":  # libpq-only option
            query.append((key, value))
    return urlunsplit(parts._replace(scheme=scheme, query=urlencode(query)))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://app:app@localhost:5432/bdvisual"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "changeme"
    JWT_ACCESS_TTL_MIN: int = 15
    JWT_REFRESH_TTL_DAYS: int = 30

    S3_ENDPOINT: str = "http://localhost:9000"
    # Endpoint clients use for presigned uploads. Differs from S3_ENDPOINT when
    # the API reaches storage over a private network (e.g. inside Docker).
    S3_PUBLIC_URL: str = ""
    # Public base URL for reading media, without a trailing slash. Defaults to
    # path-style `<public endpoint>/<bucket>`; set it for CDNs or R2 public buckets.
    MEDIA_BASE_URL: str = ""
    # Set false on deployments without object storage; uploads then fail fast
    # with a clear message instead of a network error in the client.
    UPLOADS_ENABLED: bool = True
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
    # Number of reverse proxies in front of the API (Render: 1). The client IP
    # is read from that position counting from the right of X-Forwarded-For,
    # so clients can't spoof it. 0 = use the socket address and ignore the header.
    TRUSTED_PROXY_HOPS: int = 0
    FREE_POSTS_PER_DAY: int = 5

    # Shared public demo login: profile edits and account deletion are disabled.
    DEMO_USER_EMAIL: str = "demo@pinstagram.app"
    # Admin password used by the seed script; required in production.
    ADMIN_PASSWORD: str = ""

    ENV: str = "local"

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        return normalize_database_url(v)

    @property
    def s3_public_base(self) -> str:
        return (self.S3_PUBLIC_URL or self.S3_ENDPOINT).rstrip("/")

    @property
    def media_base_url(self) -> str:
        return (
            self.MEDIA_BASE_URL.rstrip("/") or f"{self.s3_public_base}/{self.S3_BUCKET}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.ENV == "production" and self.JWT_SECRET in _INSECURE_SECRETS:
            raise ValueError("JWT_SECRET must be set to a strong value in production")
        return self


settings = Settings()
