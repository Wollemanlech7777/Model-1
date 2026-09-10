from pathlib import Path

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/config.py → parents[1]=apps/api, parents[3]=repo root
_API_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]

_DEFAULT_CORS = "http://localhost:3000,http://127.0.0.1:3000"
_PRODUCTION_ENVS = frozenset({"production", "prod"})


def _parse_cors_origins(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Later files override earlier ones → root .env takes priority.
        env_file=(
            str(_API_DIR / ".env"),
            str(_REPO_ROOT / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Site Companion API"
    # development | staging | production — never put secrets here
    environment: str = "development"
    log_level: str = "INFO"

    # Local docker-compose default only (override via DATABASE_URL in real envs)
    database_url: str = "postgresql+psycopg://site:site@localhost:5432/site_companion"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    gemini_timeout_seconds: float = 20.0
    # CyberNotes MTPL (real portal) — secrets only via env / non-versioned .env
    cybernotes_base_url: str = "https://api.cybernotes.it/mtpl/v1"
    cybernotes_client_id: str | None = None
    cybernotes_client_secret: str | None = None
    cybernotes_timeout_seconds: float = 20.0

    # API hardening (comma-separated origins; never use * with credentials)
    cors_origins: str = _DEFAULT_CORS
    cors_allow_credentials: bool = True
    # POST /jobs/policy-review requests per client per minute; 0 disables
    rate_limit_policy_review_per_minute: int = 60

    # Local/demo helpers — disabled automatically when environment is production/prod
    # unless explicitly overridden with ENABLE_DEMO_RESET=true (not recommended).
    enable_demo_reset: bool | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _default_cors_origins(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return _DEFAULT_CORS
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return "INFO"
        return str(value).strip().upper()

    @field_validator("enable_demo_reset", mode="before")
    @classmethod
    def _empty_enable_demo_reset(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    def cors_origin_list(self) -> list[str]:
        origins = _parse_cors_origins(self.cors_origins)
        # Refuse wildcard when credentials are enabled (browser-unsafe combo).
        if self.cors_allow_credentials and "*" in origins:
            return [o for o in origins if o != "*"] or _parse_cors_origins(_DEFAULT_CORS)
        return origins or _parse_cors_origins(_DEFAULT_CORS)

    def is_production(self) -> bool:
        return self.environment.strip().lower() in _PRODUCTION_ENVS

    def demo_reset_allowed(self) -> bool:
        if self.enable_demo_reset is not None:
            return bool(self.enable_demo_reset)
        return not self.is_production()


@lru_cache
def get_settings() -> Settings:
    return Settings()
