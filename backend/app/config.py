"""Application settings.

All configuration comes from environment variables (or a local ``.env`` file in
development). There is deliberately NO usable default secret: in development an
ephemeral random key is generated per process, and in production the process
refuses to start unless the configuration is safe.
"""
import secrets
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

_PLACEHOLDER_MARKERS = (
    "change_me", "changeme", "change-me", "change_this", "replace", "placeholder",
    "example", "insecure", "your-secret", "your_secret", "todo", "default",
)


def _looks_like_placeholder(value: str) -> bool:
    low = value.lower()
    return any(marker in low for marker in _PLACEHOLDER_MARKERS)


class Settings(BaseSettings):
    app_name: str = "CycloneLens AI"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./cyclonelens.db"
    secret_key: str = ""
    access_token_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    allow_registration: bool = True
    enable_docs: bool = True
    log_level: str = "INFO"
    # None -> run migrations on startup in development/test only.
    auto_migrate: bool | None = None
    # Upload handling
    upload_dir: str = "./uploads"
    max_import_mb: int = 500
    max_image_mb: int = 20
    import_chunk_rows: int = 5000
    # Login throttling (per process; also rate-limit at the reverse proxy)
    login_max_failures: int = 5
    login_window_seconds: int = 900
    model_dir: str = "../ml/artifacts"

    secret_is_ephemeral: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        # Managed Postgres providers often hand out postgres:// or postgresql:// URLs.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def should_auto_migrate(self) -> bool:
        return (not self.is_production) if self.auto_migrate is None else self.auto_migrate

    @model_validator(mode="after")
    def _validate(self):
        problems: list[str] = []
        if not self.secret_key and not self.is_production:
            self.secret_key = secrets.token_urlsafe(48)
            self.secret_is_ephemeral = True
        if not 1 <= self.access_token_minutes <= 1440:
            problems.append("ACCESS_TOKEN_MINUTES must be between 1 and 1440.")
        if self.max_import_mb < 1 or self.max_image_mb < 1:
            problems.append("MAX_IMPORT_MB and MAX_IMAGE_MB must be positive.")
        if self.is_production:
            key = self.secret_key
            if len(key) < 32 or len(set(key)) < 12 or _looks_like_placeholder(key):
                problems.append(
                    "SECRET_KEY must be set to a random value of at least 32 characters "
                    "(generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
                )
            origins = self.cors_origin_list
            if not origins:
                problems.append("CORS_ORIGINS must list the public origin(s) of the frontend, e.g. https://cyclones.example.org.")
            for origin in origins:
                if origin == "*" or "*" in origin:
                    problems.append("CORS_ORIGINS must not contain wildcards in production.")
                elif not origin.startswith(("http://", "https://")):
                    problems.append(f"CORS_ORIGINS entry '{origin}' must start with http:// or https://.")
            try:
                url = make_url(self.database_url)
            except Exception:
                problems.append("DATABASE_URL is not a valid SQLAlchemy URL.")
            else:
                if url.get_backend_name() == "sqlite":
                    problems.append("DATABASE_URL must point to PostgreSQL in production (SQLite is for local development only).")
                else:
                    pw = url.password or ""
                    if len(pw) < 12 or _looks_like_placeholder(pw):
                        problems.append("The database password in DATABASE_URL must be a strong, non-placeholder value (>= 12 characters).")
        if problems:
            raise ValueError("Unsafe or invalid configuration:\n - " + "\n - ".join(problems))
        return self


settings = Settings()
