"""The update check (M58 sub-task 4).

At start the window asks GitHub for the latest release of Reece77/Tech_Executive_Tycoon
(public: no token). A release is offered when its tag is a newer version than this build and
it carries the installer (`TechStartupTycoon-Setup-<version>.exe`) and its checksum
(`<installer>.sha256`, `sha256sum` format). **Update now**:

1. refuses while any save is busy (a turn, an action or a holiday: never update mid-turn);
2. downloads the installer to app data, hashing as it goes, and refuses it unless its SHA-256
   equals the published checksum; the asset URLs and every redirect must stay on GitHub's
   release hosts over HTTPS (M57r-B), the checksum file must hold exactly one record naming
   this installer, and no more bytes than the release lists are read; older installers are
   deleted once the new one is verified;
3. backs up every save (SQLite's backup API under each save's write lock) and the save
   folder's settings to `Documents/Tech Startup Tycoon/backups/before-<version>-<stamp>`;
4. hashes the installer once more just before running it, then runs it silently; it closes
   this copy, installs over it (saves are not in the
   install folder) and starts the new version.

Network and process calls are passed in, so tests run without either. `TST_UPDATE_SOURCE`
(a loopback `http://127.0.0.1:<port>` only) points the check and the downloads at a fake
release server instead of GitHub: the release smoke test's in-game update (M57r-B).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tst.desktop.version import parse_version

log = logging.getLogger(__name__)

REPO = "Reece77/Tech_Executive_Tycoon"
API_BASE = "https://api.github.com"
DOWNLOAD_BASE = "https://github.com"
LATEST_URL = f"{API_BASE}/repos/{REPO}/releases/latest"
# Where GitHub sends a release asset's download (M57r-B): https only, these hosts only.
REDIRECT_HOSTS = frozenset(
    {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
)
SOURCE_ENV = "TST_UPDATE_SOURCE"
_LOOPBACK_SOURCE = re.compile(r"^http://127\.0\.0\.1:\d{1,5}$")
INSTALLER_PREFIX = "TechStartupTycoon-Setup-"
CHECKSUM_SUFFIX = ".sha256"
USER_AGENT = "TechStartupTycoon-updater"
CHECK_TIMEOUT_S = 10.0
DOWNLOAD_TIMEOUT_S = 60.0
CHUNK = 1 << 20
MAX_NOTES = 20_000  # characters of release notes shown
# M57r-B: /SUPPRESSMSGBOXES, so no prompt nobody sees can stall an unattended update (the
# smoke test's in-game update hung on one), and /LOG for a record of what setup did
INSTALLER_ARGS = (
    "/SILENT",
    "/SP-",
    "/NOCANCEL",
    "/SUPPRESSMSGBOXES",
    "/CLOSEAPPLICATIONS",
    "/NORESTART",
)
INSTALL_LOG = "update-install.log"
_RECORD = re.compile(r"^([0-9a-fA-F]{64}) [ *](\S.*)$")  # sha256sum: hash, space, mode, name


class UpdateError(Exception):
    """An update step failed; the message is shown to the player."""


@dataclass(frozen=True, slots=True)
class Source:
    """Where releases come from: GitHub, or (the smoke test) a loopback fake of it."""

    api_base: str = API_BASE
    download_base: str = DOWNLOAD_BASE
    redirect_hosts: frozenset[str] = REDIRECT_HOSTS

    @property
    def latest_url(self) -> str:
        return f"{self.api_base}/repos/{REPO}/releases/latest"

    def asset_url(self, tag: str, name: str) -> str:
        """The only URL an asset of `tag` called `name` may have."""
        return f"{self.download_base}/{REPO}/releases/download/{tag}/{name}"


GITHUB = Source()


def source_from(environ: dict[str, str] | os._Environ[str]) -> Source:
    """GitHub, unless TST_UPDATE_SOURCE names a loopback fake (anything else is ignored)."""
    value = (environ.get(SOURCE_ENV) or "").rstrip("/")
    if value and _LOOPBACK_SOURCE.match(value):
        return Source(api_base=value, download_base=value, redirect_hosts=frozenset())
    if value:
        log.warning("%s ignored: only http://127.0.0.1:<port> is accepted", SOURCE_ENV)
    return GITHUB


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


@dataclass(frozen=True, slots=True)
class Download:
    """A verified installer: its path and the digest it must still have when launched."""

    path: Path
    sha256: str


type Fetch = Callable[[str, float], bytes]
type Stream = Callable[[str, float], Iterator[bytes]]


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    )


class _PinnedRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to https on GitHub's release hosts (M57r-B)."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not redirect_allowed(newurl, GITHUB):
            raise UpdateError("the download was redirected off GitHub; nothing was installed")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def redirect_allowed(url: str, source: Source) -> bool:
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and (parts.hostname or "") in source.redirect_hosts


_OPENER = urllib.request.build_opener(_PinnedRedirects)


def http_get(url: str, timeout: float) -> bytes:
    with _OPENER.open(_request(url), timeout=timeout) as res:
        body: bytes = res.read()
        return body


def http_stream(url: str, timeout: float) -> Iterator[bytes]:
    with _OPENER.open(_request(url), timeout=timeout) as res:
        while chunk := res.read(CHUNK):
            yield chunk


def parse_release(payload: dict[str, Any], source: Source = GITHUB) -> Release | None:
    """The release's version and assets, or None when it is not an installable release (an
    asset URL other than the source's own for this tag and name, or no listed size, is not)."""
    tag = str(payload.get("tag_name") or "")
    if payload.get("draft") or payload.get("prerelease") or parse_version(tag) is None:
        return None
    version = tag.removeprefix("v")
    assets = {str(a.get("name")): a for a in payload.get("assets") or [] if isinstance(a, dict)}
    name = f"{INSTALLER_PREFIX}{version}.exe"
    installer, checksum = assets.get(name), assets.get(name + CHECKSUM_SUFFIX)
    if installer is None or checksum is None:
        return None
    installer_url = str(installer.get("browser_download_url") or "")
    checksum_url = str(checksum.get("browser_download_url") or "")
    if installer_url != source.asset_url(tag, name) or checksum_url != source.asset_url(
        tag, name + CHECKSUM_SUFFIX
    ):
        log.warning("release %s ignored: its assets are not on %s", tag, source.download_base)
        return None
    try:
        size = int(installer.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if size <= 0:
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
        installer_url=installer_url,
        installer_size=size,
        checksum_url=checksum_url,
    )


def is_newer(current: str, candidate: str) -> bool:
    now, new = parse_version(current), parse_version(candidate)
    return now is not None and new is not None and new > now


def check(current: str, fetch: Fetch = http_get, source: Source = GITHUB) -> Release | None:
    """The latest release when it is newer than `current` (never for a "dev" build)."""
    if parse_version(current) is None:
        return None
    payload = json.loads(fetch(source.latest_url, CHECK_TIMEOUT_S))
    release = parse_release(payload, source) if isinstance(payload, dict) else None
    if release is None or not is_newer(current, release.version):
        return None
    return release


def parse_checksum(text: str, name: str) -> str:
    """The SHA-256 of `name` from a `sha256sum` file holding exactly one record, for it."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    records = [m for line in lines if (m := _RECORD.match(line))]
    if len(lines) != 1 or len(records) != 1:
        raise UpdateError("the release's checksum file is not one SHA-256 record")
    if records[0][2].strip() != name:
        raise UpdateError("the release's checksum file names another installer")
    return records[0][1].lower()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def download(
    release: Release, dest: Path, fetch: Fetch = http_get, stream: Stream = http_stream
) -> Download:
    """The verified installer in `dest`; UpdateError (and no file) when the hash differs or
    the download is longer or shorter than the release lists. Older installers in `dest` are
    deleted once this one is verified."""
    expected = parse_checksum(
        fetch(release.checksum_url, CHECK_TIMEOUT_S).decode("utf-8", "replace"),
        release.installer_name,
    )
    dest.mkdir(parents=True, exist_ok=True)
    final = dest / release.installer_name
    part = final.with_name(final.name + ".partial")
    digest = hashlib.sha256()
    size = 0
    try:
        with part.open("wb") as out:
            for chunk in stream(release.installer_url, DOWNLOAD_TIMEOUT_S):
                size += len(chunk)
                if size > release.installer_size:
                    raise UpdateError(
                        "the download is larger than the release lists; nothing was installed"
                    )
                digest.update(chunk)
                out.write(chunk)
    except OSError as e:
        part.unlink(missing_ok=True)
        raise UpdateError(f"the download failed ({e})") from e
    except UpdateError:
        part.unlink(missing_ok=True)
        raise
    if size != release.installer_size:
        part.unlink(missing_ok=True)
        raise UpdateError("the download is incomplete; nothing was installed")
    if digest.hexdigest() != expected:
        part.unlink(missing_ok=True)
        raise UpdateError(
            "the download's checksum does not match the release; nothing was installed"
        )
    part.replace(final)
    for old in dest.iterdir():
        if old != final and old.is_file() and old.name.startswith(INSTALLER_PREFIX):
            old.unlink(missing_ok=True)
    return Download(path=final, sha256=expected)


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


def launch_installer(
    installer: Download,
    popen: Callable[..., object] = subprocess.Popen,
    log_dir: Path | None = None,
) -> None:
    """Hash the installer again (it sat in app data through the backup), then start it
    detached from this process, which then closes."""
    path = installer.path
    try:
        same = file_sha256(path) == installer.sha256
    except OSError:
        same = False
    if not same:
        path.unlink(missing_ok=True)
        raise UpdateError("the installer changed after it was checked; nothing was installed")
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    # setup waits for this process to exit before it installs (packaging/installer.iss)
    args = [str(path), *INSTALLER_ARGS, f"/WAITPID={os.getpid()}"]
    if log_dir is not None:
        args.append(f"/LOG={log_dir / INSTALL_LOG}")
    popen(args, creationflags=flags, close_fds=True)
