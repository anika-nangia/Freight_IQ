"""Application settings loaded from environment variables / .env."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    weather_api_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_request_timeout: float = Field(default=8.0, gt=0, le=60)
    weather_cache_ttl: int = Field(default=600, ge=0)
    weather_forecast_days: int = Field(default=5, ge=1, le=7)

    cors_allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    )
    supported_ports: str = ""
    log_level: str = "INFO"
    data_dir: str = "data"
    history_db_path: str = "data/history.sqlite3"
    congestion_file: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return _split_csv(self.cors_allowed_origins)

    @property
    def supported_ports_list(self) -> list[str]:
        return _split_csv(self.supported_ports)


@lru_cache
def get_settings() -> Settings:
    return Settings()
