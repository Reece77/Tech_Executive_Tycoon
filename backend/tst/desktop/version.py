"""The installed build's version (M58 sub-task 4).

The release workflow writes `packaging/version.txt` (the tag without its "v", e.g. 6.0.0) and
the PyInstaller spec bundles it at the bundle's root. Running from the repository there is no
such file: the version is "dev" and the update check is off.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEV = "dev"
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$")


def bundle_root() -> Path | None:
    """PyInstaller's unpacked bundle (`sys._MEIPASS`), or None when not frozen."""
    root = getattr(sys, "_MEIPASS", None)
    return Path(root) if root else None


def current_version(root: Path | None = None) -> str:
    root = bundle_root() if root is None else root
    if root is not None and (root / "version.txt").is_file():
        text = (root / "version.txt").read_text(encoding="utf-8").strip()
        if parse_version(text) is not None:
            return text.removeprefix("v")
    return DEV


def parse_version(text: str) -> tuple[int, int, int] | None:
    """ "v6.0.0", "6.0.0" or "6.1" -> (6, 0, 0); anything else (a pre-release, "dev") None."""
    m = _VERSION_RE.match(text.strip())
    if m is None:
        return None
    return int(m[1]), int(m[2]), int(m[3] or 0)
