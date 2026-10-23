"""Application configuration loaded from environment variables.

All secrets are read from the process environment (or a local ``.env`` file).
Nothing sensitive is ever returned to the browser: the frontend only ever
receives public values (API base URL, feature flags).
"""

from __future__ import annotations

import functools
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ``backend/`` directory - used to resolve model / dataset paths.
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment-driven settings for the AgriVision AI API."""

    model_config = SettingsConfigDict(
        # Order matters: later files win. ``backend/.env`` is the authoritative
        # location for backend secrets, so it must be loaded *after* the
        # project-root ``.env`` fallback. Real process environment variables
        # always take precedence over both.
        env_file=(BACKEND_ROOT.parent / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Application ------------------------------------------------------
    app_name: str = "AgriVision AI"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # -- Database ---------------------------------------------------------
    mongodb_uri: str = Field(default="", description="MongoDB Atlas connection string")
    mongodb_db_name: str = "agrivision_ai"
    mongodb_timeout_ms: int = 8000
    mongodb_max_pool_size: int = 50

    # -- Security ---------------------------------------------------------
    jwt_secret_key: str = Field(default="", description="Secret used to sign JWTs")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    cookie_name: str = "agrivision_token"
    refresh_cookie_name: str = "agrivision_refresh"
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None
    csrf_enabled: bool = True
    # Password hashing (Argon2id)
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 2

    # -- CORS -------------------------------------------------------------
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    additional_cors_origins: str = ""

    # -- Rate limiting ----------------------------------------------------
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    auth_rate_limit_requests: int = 10
    auth_rate_limit_window_seconds: int = 300

    # -- Uploads / images -------------------------------------------------
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    allowed_image_mime_types: str = "image/jpeg,image/png,image/webp"
    image_min_dimension: int = 32
    image_max_dimension: int = 8000

    # -- Machine learning -------------------------------------------------
    model_dir: str = str(BACKEND_ROOT / "data" / "models")
    dataset_dir: str = str(BACKEND_ROOT / "data" / "dataset")
    upload_dir: str = str(BACKEND_ROOT / "data" / "uploads")
    inference_confidence_threshold: float = 0.35
    device: Literal["auto", "cpu", "gpu"] = "cpu"

    # -- Weather ----------------------------------------------------------
    weather_api_key: str = Field(default="", description="Optional key for a weather provider")
    weather_api_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_geocoding_base_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    weather_timeout_seconds: float = 10.0
    weather_provider: str = "Open-Meteo"

    # -- Admin bootstrap --------------------------------------------------
    admin_bootstrap_email: str = ""
    admin_bootstrap_password: str = ""

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("mongodb_uri")
    @classmethod
    def _strip_mongo_uri(cls, value: str) -> str:
        return value.strip()

    @field_validator("frontend_url", "backend_url", mode="before")
    @classmethod
    def _normalise_url(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().rstrip("/")
        return value

    @model_validator(mode="after")
    def _validate_runtime_secrets(self) -> "Settings":
        """Fail loudly in production when mandatory secrets are missing.

        In development we auto-generate an ephemeral signing key so that the
        project boots for a first-time user, but we log a loud warning because
        tokens will not survive a restart.
        """
        if self.environment in {"production", "staging"}:
            missing: list[str] = []
            if not self.jwt_secret_key:
                missing.append("JWT_SECRET_KEY")
            if not self.mongodb_uri:
                missing.append("MONGODB_URI")
            if missing:
                raise ValueError(
                    "Missing mandatory production environment variables: "
                    + ", ".join(missing)
                    + ". Refusing to start."
                )
            if len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 32 characters in production."
                )
        elif "cookie_secure" not in self.model_fields_set:
            # The `Secure` attribute makes the browser refuse the cookie on
            # plain-HTTP origins, which would break the local dev server.
            self.cookie_secure = False
        return self

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origins(self) -> list[str]:
        """Explicit allow-list of browser origins.

        Never falls back to ``*`` - permissive CORS is a production foot-gun
        because it allows any site to make credentialed requests.
        """
        origins = [self.frontend_url] if self.frontend_url else []
        if self.additional_cors_origins:
            origins.extend(
                origin.strip()
                for origin in self.additional_cors_origins.split(",")
                if origin.strip()
            )
        # Deduplicate, preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for origin in origins:
            if origin not in seen:
                seen.add(origin)
                unique.append(origin)
        return unique

    @property
    def allowed_image_mimes(self) -> list[str]:
        """Parsed list of the accepted image MIME types."""
        return [
            item.strip().lower()
            for item in self.allowed_image_mime_types.split(",")
            if item.strip()
        ]

    @property
    def has_database(self) -> bool:
        return bool(self.mongodb_uri)

    @property
    def effective_jwt_secret(self) -> str:
        """Return the signing key, generating an ephemeral one in dev."""
        if self.jwt_secret_key:
            return self.jwt_secret_key
        if not hasattr(self, "_ephemeral_secret"):
            self._ephemeral_secret = secrets.token_urlsafe(48)
        return self._ephemeral_secret


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (FastAPI dependency friendly)."""
    return Settings()
