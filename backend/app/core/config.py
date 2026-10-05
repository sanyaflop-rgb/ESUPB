from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings supplied by environment variables or a local .env file."""

    environment: str = "development"
    database_url: str = "sqlite:///./data/pk_control.db"
    cors_origins: str = "http://localhost:5173"
    documents_root: str = ""
    backups_root: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PK_CONTROL_",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
