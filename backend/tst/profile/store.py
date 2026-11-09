"""The profile file (M25 section 2): `<saves>/profiles/<profile>.json`, one per player
profile, across saves. It holds each earned achievement once, with the save and the game
date it was earned in, whether its toast has been seen, and small per-save watch records
(a downturn's start). Written atomically under a lock; never read by the sim."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

PROFILES_DIR: Final = "profiles"
DEFAULT_PROFILE: Final = "default"
VERSION: Final = 1
_LOCK = threading.Lock()


def profile_name() -> str:
    """TST_PROFILE (letters, digits, - and _), else "default"."""
    raw = os.environ.get("TST_PROFILE", DEFAULT_PROFILE)
    name = re.sub(r"[^A-Za-z0-9_-]", "", raw)[:40]
    return name or DEFAULT_PROFILE


def profile_path(save_dir: Path, name: str | None = None) -> Path:
    return save_dir / PROFILES_DIR / f"{name or profile_name()}.json"


@dataclass
class Profile:
    name: str
    earned: dict[str, dict[str, Any]] = field(default_factory=dict)
    watch: dict[str, dict[str, Any]] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "version": VERSION,
            "profile": self.name,
            "earned": self.earned,
            "watch": self.watch,
        }


def _read(path: Path, name: str) -> Profile:
    if not path.is_file():
        return Profile(name)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Profile(name)  # an unreadable profile starts again rather than block a turn
    return Profile(name, dict(raw.get("earned") or {}), dict(raw.get("watch") or {}))


def _write(path: Path, profile: Profile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(profile.as_json(), f, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load(save_dir: Path, name: str | None = None) -> Profile:
    with _LOCK:
        return _read(profile_path(save_dir, name), name or profile_name())


def update(save_dir: Path, change: Any, name: str | None = None) -> Profile:
    """Read, change (a function of the Profile, in place) and write, under the lock."""
    path = profile_path(save_dir, name)
    with _LOCK:
        profile = _read(path, name or profile_name())
        before = json.dumps(profile.as_json(), sort_keys=True)
        change(profile)
        if json.dumps(profile.as_json(), sort_keys=True) != before:
            _write(path, profile)
        return profile


def mark_seen(save_dir: Path, keys: list[str], name: str | None = None) -> Profile:
    def _seen(p: Profile) -> None:
        for key in keys:
            if key in p.earned:
                p.earned[key]["seen"] = True

    return update(save_dir, _seen, name)
