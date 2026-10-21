"""Runtime settings (paths, environment variables). Never imported by tst.sim."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TST_",
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    save_dir: Path = REPO_DIR / "saves"
    data_dir: Path = BACKEND_DIR / "data"

    def resolved_save_dir(self) -> Path:
        """Relative TST_SAVE_DIR values are resolved against the repository root."""
        path = self.save_dir
        return path if path.is_absolute() else (REPO_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
