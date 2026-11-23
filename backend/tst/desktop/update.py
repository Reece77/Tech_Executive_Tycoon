"""The update check (M58 sub-task 4).

At start the window asks GitHub for the latest release of Reece77/Tech_Executive_Tycoon
(public: no token). A release is offered when its tag is a newer version than this build and
it carries the installer (`TechStartupTycoon-Setup-<version>.exe`) and its checksum
(`<installer>.sha256`, `sha256sum` format). **Update now**:

1. refuses while any save is busy (a turn, an action or a holiday: never update mid-turn);
2. downloads the installer to app data, hashing as it goes, and refuses it unless its SHA-256
   equals the published checksum;
3. backs up every save (SQLite's backup API under each save's write lock) and the save
   folder's settings to `Documents/Tech Startup Tycoon/backups/before-<version>-<stamp>`;
4. runs the installer silently; it closes this copy, installs over it (saves are not in the
   install folder) and starts the new version.

Network and process calls are passed in, so tests run without either.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
import sys
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tst.desktop.version import parse_version

log = logging.getLogger(__name__)

REPO = "Reece77/Tech_Executive_Tycoon"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
INSTALLER_PREFIX = "TechStartupTycoon-Setup-"
CHECKSUM_SUFFIX = ".sha256"
USER_AGENT = "TechStartupTycoon-updater"
CHECK_TIMEOUT_S = 10.0
DOWNLOAD_TIMEOUT_S = 60.0
CHUNK = 1 << 20
MAX_NOTES = 20_000  # characters of release notes shown
INSTALLER_ARGS = ("/SILENT", "/SP-", "/NOCANCEL", "/CLOSEAPPLICATIONS", "/NORESTART")
_HEX64 = re.compile(r"\b([0-9a-fA-F]{64})\b")


class UpdateError(Exception):
    """An update step failed; the message is shown to the player."""


@dataclass(frozen=True, slots=True)
class Release:
    version: str  # without the "v"
    tag: str
    notes: str
    page_url: str
    installer_name: str
    installer_url: str
    installer_size: int
    checksum_url: str


type Fetch = Callable[[str, float], bytes]
type Stream = Callable[[str, float], Iterator[bytes]]


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    )


def http_get(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(_request(url), timeout=timeout) as res:
        body: bytes = res.read()
        return body


def http_stream(url: str, timeout: float) -> Iterator[bytes]:
    with urllib.request.urlopen(_request(url), timeout=timeout) as res:
        while chunk := res.read(CHUNK):
            yield chunk


def parse_release(payload: dict[str, Any]) -> Release | None:
    """The release's version and assets, or None when it is not an installable release."""
    tag = str(payload.get("tag_name") or "")
    if payload.get("draft") or payload.get("prerelease") or parse_version(tag) is None:
        return None
    version = tag.removeprefix("v")
    assets = {str(a.get("name")): a for a in payload.get("assets") or [] if isinstance(a, dict)}
    name = f"{INSTALLER_PREFIX}{version}.exe"
    installer, checksum = assets.get(name), assets.get(name + CHECKSUM_SUFFIX)
    if installer is None or checksum is None:
        return None
    notes = str(payload.get("body") or "").strip()
    if len(notes) > MAX_NOTES:
        notes = notes[:MAX_NOTES].rstrip() + "\n\n(continued on the release page)"
    return Release(
        version=version,
        tag=tag,
        notes=notes,
        page_url=str(payload.get("html_url") or ""),
        installer_name=name,
        installer_url=str(installer["browser_download_url"]),
        installer_size=int(installer.get("size") or 0),
        checksum_url=str(checksum["browser_download_url"]),
    )


def is_newer(current: str, candidate: str) -> bool:
    now, new = parse_version(current), parse_version(candidate)
    return now is not None and new is not None and new > now


def check(current: str, fetch: Fetch = http_get) -> Release | None:
    """The latest release when it is newer than `current` (never for a "dev" build)."""
    if parse_version(current) is None:
        return None
    payload = json.loads(fetch(LATEST_URL, CHECK_TIMEOUT_S))
    release = parse_release(payload) if isinstance(payload, dict) else None
    if release is None or not is_newer(current, release.version):
        return None
    return release


def parse_checksum(text: str) -> str:
    m = _HEX64.search(text)
    if m is None:
        raise UpdateError("the release's checksum file holds no SHA-256")
    return m[1].lower()


def download(
    release: Release, dest: Path, fetch: Fetch = http_get, stream: Stream = http_stream
) -> Path:
    """The verified installer in `dest`; UpdateError (and no file) when the hash differs."""
    expected = parse_checksum(
        fetch(release.checksum_url, CHECK_TIMEOUT_S).decode("utf-8", "replace")
    )
    dest.mkdir(parents=True, exist_ok=True)
    final = dest / release.installer_name
    part = final.with_name(final.name + ".partial")
    digest = hashlib.sha256()
    try:
        with part.open("wb") as out:
            for chunk in stream(release.installer_url, DOWNLOAD_TIMEOUT_S):
                digest.update(chunk)
                out.write(chunk)
    except OSError as e:
        part.unlink(missing_ok=True)
        raise UpdateError(f"the download failed ({e})") from e
    if digest.hexdigest() != expected:
        part.unlink(missing_ok=True)
        raise UpdateError(
            "the download's checksum does not match the release; nothing was installed"
        )
    part.replace(final)
    return final


def backup_saves(saves: Path, backups: Path, version: str, stamp: str) -> Path:
    """Copy every save (under its write lock: SaveBusyError if a turn holds it) and the save
    folder's other top-level files into a new backup folder."""
    from tst.db import backup as backup_files
    from tst.db import saves as saves_db

    folder = backups / f"before-{version}-{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    paths = sorted(saves.glob(f"*{backup_files.SAVE_SUFFIX}")) if saves.is_dir() else []
    with ExitStack() as held:
        for path in paths:  # every lock first: a busy save refuses before anything is copied
            held.enter_context(saves_db.exclusive(path))
        for path in paths:
            backup_files._copy(path, folder / path.name)
    for path in sorted(saves.iterdir()) if saves.is_dir() else []:
        if path.is_file() and not path.name.endswith((backup_files.SAVE_SUFFIX, "-wal", "-shm")):
            shutil.copy2(path, folder / path.name)
    log.info("backed up %d saves to %s", len(paths), folder)
    return folder


def launch_installer(path: Path, popen: Callable[..., object] = subprocess.Popen) -> None:
    """Start the installer detached from this process, which then closes."""
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    popen([str(path), *INSTALLER_ARGS], creationflags=flags, close_fds=True)
