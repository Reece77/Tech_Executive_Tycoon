"""M58: the desktop build's pieces that need no window (paths, key, instance, import, update)."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tst.desktop import imports, secrets, update
from tst.desktop.instance import SingleInstance
from tst.desktop.paths import APP_NAME, DesktopPaths, app_data_dir, documents_dir
from tst.desktop.version import current_version, parse_version

KEY = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789"


# --- paths ------------------------------------------------------------------------------
def test_windows_paths_follow_userprofile_and_appdata() -> None:
    env = {"USERPROFILE": r"C:\Users\reece", "APPDATA": r"C:\Users\reece\AppData\Roaming"}
    paths = DesktopPaths.resolve(env, "win32")
    assert paths.saves == Path(r"C:\Users\reece") / "Documents" / APP_NAME / "saves"
    assert paths.env_file == Path(r"C:\Users\reece\AppData\Roaming") / APP_NAME / ".env"
    assert paths.logs.parent == paths.app_data
    assert paths.update_backups.parent == paths.documents  # beside the saves, not in app data


def test_linux_paths_and_home_override(tmp_path: Path) -> None:
    assert documents_dir({"HOME": "/home/r"}, "linux") == Path("/home/r/Documents")
    assert app_data_dir({"HOME": "/home/r"}, "linux") == Path("/home/r/.local/share") / APP_NAME
    paths = DesktopPaths.resolve({"TST_DESKTOP_HOME": str(tmp_path)})
    assert paths.saves.is_relative_to(tmp_path) and paths.app_data.is_relative_to(tmp_path)


# --- the API key ------------------------------------------------------------------------
def test_key_saved_loaded_and_removed(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    environ: dict[str, str] = {}
    secrets.save_key(env_file, f"  {KEY} ", environ)
    assert environ[secrets.KEY_NAME] == KEY
    assert secrets.read_env(env_file) == {secrets.KEY_NAME: KEY}
    fresh: dict[str, str] = {}
    assert secrets.load_into(env_file, fresh) and fresh[secrets.KEY_NAME] == KEY
    secrets.save_key(env_file, None, environ)
    assert secrets.KEY_NAME not in environ and secrets.read_env(env_file) == {}


def test_key_shape_is_checked() -> None:
    for bad in ("a b", "x" * 401, 'k"ey', "k=ey"):
        with pytest.raises(ValueError):
            secrets.clean_key(bad)


def test_logs_never_hold_a_key(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tst.test_desktop")
    handler_filter = secrets.RedactingFilter()
    caplog.handler.addFilter(handler_filter)
    try:
        logger.warning("calling with %s", KEY)
        try:
            raise RuntimeError(f"bad key {KEY}")
        except RuntimeError:
            logger.exception("failed")
    finally:
        caplog.handler.removeFilter(handler_filter)
    assert KEY not in caplog.text
    assert secrets.MASK in caplog.text


# --- one copy ---------------------------------------------------------------------------
def test_second_instance_is_refused_until_the_first_releases(tmp_path: Path) -> None:
    first = SingleInstance(tmp_path / "instance.lock", tmp_path / "instance.json")
    second = SingleInstance(tmp_path / "instance.lock", tmp_path / "instance.json")
    assert first.acquire()
    first.publish(8123)
    assert json.loads((tmp_path / "instance.json").read_text())["port"] == 8123
    assert not second.acquire()
    assert first.check_token(first.token) and not first.check_token("nope")
    assert not first.check_token(None)
    first.release()
    assert not (tmp_path / "instance.json").exists()
    assert second.acquire()
    second.release()


# --- first-run import -------------------------------------------------------------------
def _save(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("create table t (v integer)")
    con.execute("insert into t values (?)", (value,))
    con.commit()
    con.close()


def _value(path: Path) -> int:
    con = sqlite3.connect(path)
    try:
        return int(con.execute("select v from t").fetchone()[0])
    finally:
        con.close()


def test_import_offers_new_saves_and_never_overwrites(tmp_path: Path) -> None:
    repo_saves = tmp_path / "Documents" / "GitHub" / "Tech_Executive_Tycoon" / "saves"
    target = tmp_path / "game" / "saves"
    _save(repo_saves / "alpha.tst.sqlite", 1)
    _save(repo_saves / "beta.tst.sqlite", 2)
    _save(repo_saves / "backups" / "alpha" / "alpha.turn-012.sqlite", 9)
    (repo_saves / "llm_settings.json").write_text("{}")
    (repo_saves / "launcher.log").write_text("log")
    _save(target / "beta.tst.sqlite", 7)  # already in the game's folder: kept

    found = imports.candidates(tmp_path / "Documents", tmp_path / "home", {})
    offer = imports.find_offer(target, found)
    assert offer is not None and offer.folder == repo_saves and offer.saves == ("alpha",)

    assert imports.import_saves(offer.folder, target) == ["alpha"]
    assert _value(target / "alpha.tst.sqlite") == 1
    assert _value(target / "beta.tst.sqlite") == 7
    assert (target / "llm_settings.json").is_file()
    assert not (target / "launcher.log").exists() and not (target / "backups").exists()
    assert imports.find_offer(target, found) is None  # nothing new left
    assert _value(repo_saves / "alpha.tst.sqlite") == 1  # the originals stay


# --- versions and releases --------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "parsed"),
    [("v6.0.0", (6, 0, 0)), ("6.1", (6, 1, 0)), ("dev", None), ("v6.0.0-rc1", None)],
)
def test_parse_version(text: str, parsed: tuple[int, int, int] | None) -> None:
    assert parse_version(text) == parsed


def test_bundled_version_file(tmp_path: Path) -> None:
    assert current_version(tmp_path) == "dev"
    (tmp_path / "version.txt").write_text("v6.0.2\n")
    assert current_version(tmp_path) == "6.0.2"


def release_payload(version: str = "6.1.0", size: int = 1234, **extra: Any) -> dict[str, Any]:
    name = f"TechStartupTycoon-Setup-{version}.exe"
    base = f"https://github.com/{update.REPO}/releases/download/v{version}/"
    return {
        "tag_name": f"v{version}",
        "body": "## What's new\n- Faster turns",
        "html_url": f"https://github.com/{update.REPO}/releases/tag/v{version}",
        "assets": [
            {"name": name, "browser_download_url": base + name, "size": size},
            {"name": name + ".sha256", "browser_download_url": base + name + ".sha256"},
        ],
        **extra,
    }


def test_a_newer_release_is_offered_with_its_notes() -> None:
    def fetch(url: str, _timeout: float) -> bytes:
        assert url == update.LATEST_URL
        return json.dumps(release_payload()).encode()

    release = update.check("6.0.0", fetch)
    assert release is not None
    assert release.version == "6.1.0" and "Faster turns" in release.notes
    assert release.installer_size == 1234
    assert update.check("6.1.0", fetch) is None  # same version
    assert update.check("6.2.0", fetch) is None  # older
    assert update.check("dev", fetch) is None  # a repository run never updates


@pytest.mark.parametrize(
    "payload",
    [
        release_payload(prerelease=True),
        release_payload(draft=True),
        {**release_payload(), "assets": release_payload()["assets"][:1]},  # no checksum
        {**release_payload(), "tag_name": "nightly"},
    ],
)
def test_releases_that_cannot_be_installed_are_ignored(payload: dict[str, Any]) -> None:
    assert update.parse_release(payload) is None


def _release(size: int = 1234) -> update.Release:
    release = update.parse_release(release_payload(size=size))
    assert release is not None
    return release


NAME = "TechStartupTycoon-Setup-6.1.0.exe"


def _fakes(blob: bytes, published: str) -> tuple[update.Fetch, update.Stream]:
    def fetch(url: str, _timeout: float) -> bytes:
        assert url.endswith(".sha256")
        return f"{published}  {NAME}\n".encode()

    def stream(_url: str, _timeout: float) -> Iterator[bytes]:
        yield blob[:3]
        yield blob[3:]

    return fetch, stream


def test_download_verifies_the_checksum(tmp_path: Path) -> None:
    blob = b"installer bytes"
    fetch, stream = _fakes(blob, hashlib.sha256(blob).hexdigest().upper())
    got = update.download(_release(len(blob)), tmp_path, fetch, stream)
    assert got.path.read_bytes() == blob and got.path.name == NAME
    assert got.sha256 == hashlib.sha256(blob).hexdigest()


def test_a_tampered_download_is_refused_and_deleted(tmp_path: Path) -> None:
    fetch, stream = _fakes(b"tampered", hashlib.sha256(b"original").hexdigest())
    with pytest.raises(update.UpdateError, match="checksum"):
        update.download(_release(len(b"tampered")), tmp_path, fetch, stream)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "text",
    [
        "not a hash",
        "",
        # one hash anywhere in the file is no longer enough: one record, for this installer
        f"see {'a' * 64} for details",
        f"{'a' * 64}  TechStartupTycoon-Setup-6.0.9.exe",
        f"{'a' * 64}  {NAME}\n{'b' * 64}  {NAME}",
        f"{'a' * 64}  {NAME}\n{'b' * 64}  other.exe",
    ],
)
def test_checksum_file_must_be_one_record_for_the_installer(text: str) -> None:
    with pytest.raises(update.UpdateError):
        update.parse_checksum(text, NAME)


def test_checksum_record_forms() -> None:
    digest = "A" * 64
    assert update.parse_checksum(f"{digest}  {NAME}", NAME) == "a" * 64
    assert update.parse_checksum(f"{digest} *{NAME}\r\n", NAME) == "a" * 64


def test_downloads_longer_or_shorter_than_listed_are_refused(tmp_path: Path) -> None:
    blob = b"installer bytes"
    fetch, stream = _fakes(blob, hashlib.sha256(blob).hexdigest())
    with pytest.raises(update.UpdateError, match="larger"):
        update.download(_release(len(blob) - 1), tmp_path, fetch, stream)
    with pytest.raises(update.UpdateError, match="incomplete"):
        update.download(_release(len(blob) + 1), tmp_path, fetch, stream)
    assert list(tmp_path.iterdir()) == []


def test_older_installers_are_deleted_once_the_new_one_is_verified(tmp_path: Path) -> None:
    (tmp_path / "TechStartupTycoon-Setup-6.0.0.exe").write_bytes(b"old")
    (tmp_path / "keep.txt").write_text("not ours")
    blob = b"installer bytes"
    fetch, stream = _fakes(blob, hashlib.sha256(blob).hexdigest())
    update.download(_release(len(blob)), tmp_path, fetch, stream)
    assert sorted(p.name for p in tmp_path.iterdir()) == [NAME, "keep.txt"]


@pytest.mark.parametrize(
    "url",
    [
        "https://example.invalid/dl/TechStartupTycoon-Setup-6.1.0.exe",
        "http://github.com/Reece77/Tech_Executive_Tycoon/releases/download/v6.1.0/"
        "TechStartupTycoon-Setup-6.1.0.exe",
        "https://github.com/someone/else/releases/download/v6.1.0/TechStartupTycoon-Setup-6.1.0.exe",
        "https://github.com/Reece77/Tech_Executive_Tycoon/releases/download/v6.0.0/"
        "TechStartupTycoon-Setup-6.1.0.exe",
    ],
)
def test_assets_off_the_release_are_refused(url: str) -> None:
    payload = release_payload()
    payload["assets"][0]["browser_download_url"] = url
    assert update.parse_release(payload) is None
    payload = release_payload()
    payload["assets"][1]["browser_download_url"] = url + ".sha256"
    assert update.parse_release(payload) is None


def test_a_release_without_a_listed_size_is_refused() -> None:
    assert update.parse_release(release_payload(size=0)) is None


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("https://objects.githubusercontent.com/x", True),
        ("https://release-assets.githubusercontent.com/x", True),
        ("https://github.com/x", True),
        ("http://objects.githubusercontent.com/x", False),
        ("https://evil.example/x", False),
        ("https://objects.githubusercontent.com.evil.example/x", False),
    ],
)
def test_redirects_stay_on_github_over_https(url: str, ok: bool) -> None:
    assert update.redirect_allowed(url, update.GITHUB) is ok


def test_the_redirect_handler_refuses_a_foreign_hop() -> None:
    import urllib.request

    handler = update._PinnedRedirects()
    req = urllib.request.Request("https://github.com/x")
    with pytest.raises(update.UpdateError, match="redirected"):
        handler.redirect_request(req, None, 302, "Found", {}, "http://evil.example/x")
    ok = handler.redirect_request(
        req, None, 302, "Found", {}, "https://objects.githubusercontent.com/y"
    )
    assert ok is not None and ok.full_url == "https://objects.githubusercontent.com/y"


def test_update_source_is_github_unless_a_loopback_fake() -> None:
    assert update.source_from({}) is update.GITHUB
    assert update.source_from({"TST_UPDATE_SOURCE": "https://evil.example"}) is update.GITHUB
    assert update.source_from({"TST_UPDATE_SOURCE": "http://10.0.0.1:80"}) is update.GITHUB
    fake = update.source_from({"TST_UPDATE_SOURCE": "http://127.0.0.1:8123/"})
    assert fake.latest_url == f"http://127.0.0.1:8123/repos/{update.REPO}/releases/latest"
    payload = release_payload()
    for a in payload["assets"]:
        a["browser_download_url"] = fake.asset_url("v6.1.0", a["name"])
    assert update.parse_release(payload, fake) is not None
    assert update.parse_release(payload) is None  # the fake's URLs are not GitHub's


def _installer(tmp_path: Path, blob: bytes = b"setup") -> update.Download:
    path = tmp_path / "setup.exe"
    path.write_bytes(blob)
    return update.Download(path=path, sha256=hashlib.sha256(blob).hexdigest())


def test_installer_runs_silently_and_detached(tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []
    update.launch_installer(_installer(tmp_path), lambda cmd, **kw: calls.append((cmd, kw)))
    ((cmd, kw),) = calls
    assert cmd[0].endswith("setup.exe") and "/SILENT" in cmd and "/CLOSEAPPLICATIONS" in cmd
    assert kw["close_fds"] is True


def test_installer_is_hashed_again_just_before_it_runs(tmp_path: Path) -> None:
    calls: list[object] = []
    installer = _installer(tmp_path)
    installer.path.write_bytes(b"swapped during the backup")
    with pytest.raises(update.UpdateError, match="changed"):
        update.launch_installer(installer, lambda cmd, **kw: calls.append(cmd))
    assert calls == [] and not installer.path.exists()
