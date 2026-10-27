from datetime import time
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration, overridable through environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = REPO_ROOT / "data"
    timezone: str = "Europe/London"
    # Local wall-clock time on D-1 by which day-ahead bids for day D must be placed.
    decision_cutoff_local: time = time(9, 0)
    # Central confidence level of the risk band (0.8 -> P10..P90 of historical error).
    band_confidence: float = 0.8
    # Prior complete days of error history required before a band is shown.
    min_history_days: int = 3
    # Access control. Fail closed: the app refuses to start without credentials and a strong
    # signing secret unless auth is explicitly disabled (tests / trusted local use only).
    auth_enabled: bool = True
    auth_username: str = ""
    auth_password: SecretStr = SecretStr("")
    session_secret: SecretStr = SecretStr("")
    session_ttl_hours: int = 12
    session_cookie: str = "ww_session"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]

    @model_validator(mode="after")
    def _auth_configured(self) -> "Settings":
        if self.auth_enabled and not (
            self.auth_username
            and self.auth_password.get_secret_value()
            and len(self.session_secret.get_secret_value()) >= 32
        ):
            raise ValueError(
                "Auth is enabled but AUTH_USERNAME, AUTH_PASSWORD or SESSION_SECRET (>=32 chars) "
                "is missing. Set them, or AUTH_ENABLED=false for local use only."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
