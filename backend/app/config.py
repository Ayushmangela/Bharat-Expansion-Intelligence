from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    data_gov_in_api_key: str
    data_gov_in_base_url: str = "https://api.data.gov.in"

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str

    redis_url: str = "redis://localhost:6379/0"

    http_max_concurrency: int = 4
    http_requests_per_second: float = 2.0
    http_timeout_seconds: int = 60
    http_max_retries: int = 5
    user_agent: str = "BharatExpansionIntelligence/0.1"

    bronze_path: str = "./data/bronze"
    reference_path: str = "./data/reference"

    llm_enabled: bool = False
    environment: str = "development"
    log_level: str = "INFO"

    @field_validator("bronze_path", "reference_path")
    @classmethod
    def _resolve_relative_to_repo_root(cls, v: str) -> str:
        p = Path(v)
        return str(p if p.is_absolute() else REPO_ROOT / p)


settings = Settings()  # type: ignore[call-arg]  # values come from .env, not call site
