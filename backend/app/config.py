"""Environment-backed application settings and derived path helpers for the backend."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


LEGACY_DEV_SECRET_KEY = "screenpulse-dev-secret-key-change-me-now"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_prefix="SCREENPULSE_",
        extra="ignore",
    )

    app_name: str = "ScreenPulse API"
    api_prefix: str = "/api"
    secret_key: str = ""
    access_token_expire_hours: int = 12
    database_url: str = "sqlite:///./storage/screenpulse.db"
    cors_origins: str = "http://localhost:3001"
    storage_dir: str = "storage"
    default_sampling_interval_minutes: int = 5
    max_frame_upload_bytes: int = 5 * 1024 * 1024
    max_frame_pixels: int = 8_294_400
    invite_code_max_uses: int = 25
    auth_rate_limit_attempts: int = 10
    auth_rate_limit_window_seconds: int = 60

    model_api_base_url: str = ""
    model_api_key: str = ""
    vision_model: str = ""
    summary_model: str = ""

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir)

    @property
    def default_sampling_interval_seconds(self) -> int:
        return self.default_sampling_interval_minutes * 60

    def validate_runtime_security(self) -> None:
        if not self.secret_key or self.secret_key == LEGACY_DEV_SECRET_KEY:
            raise RuntimeError(
                "SCREENPULSE_SECRET_KEY must be set to a unique secret before starting the backend."
            )
        if len(self.secret_key) < 32:
            raise RuntimeError("SCREENPULSE_SECRET_KEY must be at least 32 characters long.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
