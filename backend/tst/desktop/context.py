"""The running desktop window's state, shared with the API's desktop routes (M58).

`tst.desktop.main` installs one `DesktopContext` with `install()`; outside the desktop build
(`make dev`, the launcher, tests) there is none and `/api/desktop` says so. The update runs on
its own thread through `UpdateJob`; the window polls its state.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from tst.desktop import imports, secrets, update
from tst.desktop.paths import DesktopPaths

log = logging.getLogger(__name__)

type UpdateState = Literal[
    "none", "checking", "available", "downloading", "backing_up", "installing", "failed"
]
CLOSE_DELAY_S = 1.0  # the installer is started, then the window closes


@dataclass
class DesktopContext:
    paths: DesktopPaths
    version: str
    focus: Callable[[], None] = lambda: None
    close: Callable[[], None] = lambda: None
    check_token: Callable[[str | None], bool] = lambda _t: False
    token: str | None = None  # the instance token, served to the game's own page (M57r-B)
    fetch: update.Fetch = update.http_get
    stream: update.Stream = update.http_stream
    popen: Callable[..., object] = update.subprocess.Popen
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    sleep: Callable[[float], None] = time.sleep
    environ: dict[str, str] | os._Environ[str] = field(default_factory=lambda: os.environ)
    import_offer: imports.ImportOffer | None = None
    release: update.Release | None = None
    update_state: UpdateState = "none"
    update_message: str = ""
    backup_folder: Path | None = None
    updating: bool = False  # set once the backup starts: every write is refused from then
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _thread: threading.Thread | None = None

    # --- the update check -------------------------------------------------------------
    def check_for_update(self) -> None:
        """Ask GitHub once (at start, on its own thread); failures only log."""
        with self._lock:
            self.update_state = "checking"
        try:
            release = update.check(self.version, self.fetch, update.source_from(self.environ))
        except Exception as e:  # offline, rate-limited, GitHub down: play on
            log.warning("update check failed: %s", secrets.redact(str(e)))
            release = None
        with self._lock:
            self.release = release
            self.update_state = "available" if release else "none"
        if release:
            log.info("update available: %s", release.version)

    def start_check(self) -> threading.Thread:
        t = threading.Thread(target=self.check_for_update, name="update-check", daemon=True)
        t.start()
        return t

    # --- Update now -------------------------------------------------------------------
    def begin_update(self) -> None:
        """Start the update job; UpdateError when there is nothing to install or a save is
        busy (checked here first so the player sees it at once)."""
        from tst.db import saves as saves_db

        with self._lock:
            if self.release is None:
                raise update.UpdateError("no newer version is available")
            if self.update_state in ("downloading", "backing_up", "installing"):
                return
            if any(s.busy for s in saves_db.list_files(self.paths.saves)):
                raise update.UpdateError(
                    "a turn or holiday is running; update when it has finished"
                )
            self.update_state, self.update_message = "downloading", ""
            self._thread = threading.Thread(target=self._run_update, name="update", daemon=True)
            self._thread.start()

    def _run_update(self) -> None:
        release = self.release
        assert release is not None
        try:
            installer = update.download(release, self.paths.downloads, self.fetch, self.stream)
            with self._lock:
                self.update_state, self.updating = "backing_up", True
            stamp = self.clock().strftime("%Y%m%d-%H%M%S")
            self.backup_folder = update.backup_saves(
                self.paths.saves, self.paths.update_backups, release.version, stamp
            )
            with self._lock:
                self.update_state = "installing"
            update.launch_installer(installer, self.popen, self.paths.logs)
        except Exception as e:
            from tst.sim.errors import SaveBusyError

            message = (
                "a turn or holiday is running; update when it has finished"
                if isinstance(e, SaveBusyError)
                else str(e)
            )
            log.error("update failed: %s", secrets.redact(message))
            with self._lock:
                self.update_state, self.update_message, self.updating = "failed", message, False
            return
        log.info("installer started; closing for the update to %s", release.version)
        self.sleep(CLOSE_DELAY_S)
        self.close()

    def later(self) -> None:
        """Later: not offered again until the next start."""
        with self._lock:
            if self.update_state in ("available", "failed"):
                self.update_state = "none"

    # --- the API key ------------------------------------------------------------------
    def key_saved(self) -> bool:
        return bool(secrets.read_env(self.paths.env_file).get(secrets.KEY_NAME))

    def save_key(self, key: str | None) -> None:
        from tst.config import get_settings

        secrets.save_key(self.paths.env_file, key, self.environ)
        get_settings.cache_clear()  # the next request reads the new key
        log.info("API key %s", "saved" if key else "removed")

    # --- first-run import -------------------------------------------------------------
    def import_saves(self) -> list[str]:
        offer = self.import_offer
        if offer is None:
            return []
        copied = imports.import_saves(offer.folder, self.paths.saves)
        self.skip_import()
        log.info("imported %d saves from %s", len(copied), offer.folder)
        return copied

    def skip_import(self) -> None:
        """Asked once: either answer is remembered in desktop.json."""
        self.import_offer = None
        settings = load_settings(self.paths)
        settings["import_answered"] = True
        save_settings(self.paths, settings)


def load_settings(paths: DesktopPaths) -> dict[str, object]:
    try:
        data = json.loads(paths.settings_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(paths: DesktopPaths, settings: dict[str, object]) -> None:
    paths.settings_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.settings_file.with_name(paths.settings_file.name + ".partial")
    tmp.write_text(json.dumps(settings, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(paths.settings_file)


_CURRENT: DesktopContext | None = None


def install(ctx: DesktopContext | None) -> None:
    global _CURRENT
    _CURRENT = ctx


def current() -> DesktopContext | None:
    return _CURRENT
