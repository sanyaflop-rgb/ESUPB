from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def prepare_sqlite_directory(database_url: str) -> None:
    """Create a local SQLite parent folder and reject SMB/UNC network-share paths."""
    if database_url.startswith(("sqlite:////", "sqlite:///\\\\")):
        raise RuntimeError("SQLite database must be stored on the server's local disk, not on a network share.")
    if not database_url.startswith("sqlite:///") or database_url == "sqlite:///:memory:":
        return
    database_path = database_url.removeprefix("sqlite:///")
    Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Settings supplied by environment variables or a local .env file."""

    environment: str = "development"
    database_url: str = "sqlite:///./data/pk_control.db"
    cors_origins: str = "http://localhost:5173"
    documents_root: str = ""
    backups_root: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    initial_admin_login: str = ""
    initial_admin_password: str = ""
    initial_admin_name: str = "Администратор"

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
