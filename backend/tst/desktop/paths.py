"""Where the desktop build keeps things (M58 sub-task 2).

- Saves: `Documents/Tech Startup Tycoon/saves` (the user's own files: kept by updates and
  by the uninstaller), and the pre-update backups beside them in `backups`.
- Settings, the `.env` with the API key, logs, downloaded installers and the single-instance
  files: the app-data folder (`%APPDATA%/Tech Startup Tycoon` on Windows).

`TST_DESKTOP_HOME` puts both under one folder (tests and the release smoke test).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Tech Startup Tycoon"
HOME_ENV = "TST_DESKTOP_HOME"


def _windows_documents() -> Path | None:
    """The Documents folder as Windows knows it (follows OneDrive and moved folders)."""
    try:
        import ctypes
        from ctypes import wintypes

        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        csidl_personal = 5
        windll = ctypes.windll  # type: ignore[attr-defined,unused-ignore]
        if windll.shell32.SHGetFolderPathW(None, csidl_personal, None, 0, buf) == 0:
            return Path(buf.value)
    except (AttributeError, OSError):
        return None
    return None


def documents_dir(env: Mapping[str, str] | None = None, platform: str | None = None) -> Path:
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if platform == "win32" and env is os.environ and (found := _windows_documents()):
        return found
    if platform == "win32" and env.get("USERPROFILE"):
        return Path(env["USERPROFILE"]) / "Documents"
    return Path(env.get("HOME") or Path.home()) / "Documents"


def app_data_dir(env: Mapping[str, str] | None = None, platform: str | None = None) -> Path:
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if platform == "win32" and env.get("APPDATA"):
        return Path(env["APPDATA"]) / APP_NAME
    if platform == "darwin":
        return Path(env.get("HOME") or Path.home()) / "Library" / "Application Support" / APP_NAME
    base = env.get("XDG_DATA_HOME") or str(Path(env.get("HOME") or Path.home()) / ".local/share")
    return Path(base) / APP_NAME


@dataclass(frozen=True, slots=True)
class DesktopPaths:
    documents: Path  # Documents/Tech Startup Tycoon
    app_data: Path

    @classmethod
    def resolve(
        cls, env: Mapping[str, str] | None = None, platform: str | None = None
    ) -> DesktopPaths:
        env = os.environ if env is None else env
        if home := env.get(HOME_ENV):
            root = Path(home)
            return cls(documents=root / "Documents" / APP_NAME, app_data=root / "AppData")
        return cls(
            documents=documents_dir(env, platform) / APP_NAME,
            app_data=app_data_dir(env, platform),
        )

    @property
    def saves(self) -> Path:
        return self.documents / "saves"

    @property
    def update_backups(self) -> Path:
        return self.documents / "backups"

    @property
    def logs(self) -> Path:
        return self.app_data / "logs"

    @property
    def log_file(self) -> Path:
        return self.logs / "desktop.log"

    @property
    def env_file(self) -> Path:
        return self.app_data / ".env"

    @property
    def settings_file(self) -> Path:
        return self.app_data / "desktop.json"

    @property
    def lock_file(self) -> Path:
        return self.app_data / "instance.lock"

    @property
    def instance_file(self) -> Path:
        return self.app_data / "instance.json"

    @property
    def downloads(self) -> Path:
        return self.app_data / "updates"

    def make(self) -> None:
        for d in (self.saves, self.logs, self.app_data):
            d.mkdir(parents=True, exist_ok=True)
