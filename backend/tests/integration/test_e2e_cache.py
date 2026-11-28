"""M59 sub-task 3: a fixture save from the e2e cache (tools/e2e_cache.py) is the save a fresh build
makes. The fixture is M10b's event save (tools/e2e_event_save.py, `--modifier`): built once into
the cache under one name, restored under another, and held to a fresh build of that name by the
full-state digest (M30's Digester) and the ledger. Edits of a save that exists are never cached.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tst.balance.m30 import Digester
from tst.db.repository import ledger_balances, list_saves, open_session, save_path
from tst.db.state_io import load_state

TOOLS = Path(__file__).resolve().parents[3] / "tools"
ARGS = ["--modifier"]


def _tools() -> tuple[ModuleType, ModuleType]:
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    return importlib.import_module("e2e_cache"), importlib.import_module("e2e_event_save")


def _build(folder: Path, name: str) -> int:
    cache, tool = _tools()
    args = [str(folder), name, *ARGS]
    return int(cache.run(tool.__file__, args, lambda: tool.main(args)))


def _fingerprint(path: Path) -> tuple[str, str, dict[str, int]]:
    with open_session(path) as session:
        state = load_state(session)
        ledger = dict(ledger_balances(session))
    return state.save_meta.name, Digester().digest(state).hex(), ledger


def test_a_cached_fixture_equals_a_fresh_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cache, built, restored, fresh = (tmp_path / d for d in ("cache", "built", "restored", "fresh"))
    for d in (cache, built, restored, fresh):
        d.mkdir()
    monkeypatch.setenv("TST_E2E_FIXTURE_CACHE", str(cache))
    assert _build(built, "first-1") == 0
    assert "e2e_cache: stored" in capsys.readouterr().err
    assert len([p for p in cache.iterdir() if not p.name.startswith(".")]) == 1

    assert _build(restored, "second-2") == 0
    hit = capsys.readouterr()
    assert "e2e_cache: hit" in hit.err

    monkeypatch.delenv("TST_E2E_FIXTURE_CACHE")
    assert _build(fresh, "second-2") == 0
    plain = capsys.readouterr()
    assert "e2e_cache" not in plain.err
    assert hit.out.replace(str(restored), str(fresh)) == plain.out

    got = _fingerprint(save_path(restored, "second-2"))
    want = _fingerprint(save_path(fresh, "second-2"))
    assert got[0] == "second-2"
    assert got == want
    assert _fingerprint(save_path(built, "first-1"))[1] != want[1]  # the name is in the state
    # listed in the folder's index, as a build lists it (M7b's save list reads it)
    assert [s.slug for s in list_saves(restored)] == ["second-2"]
    assert list_saves(restored) == list_saves(fresh)
    # and the achievements it earned while it was built are in the profile, as after a build
    assert _profile(restored) == _profile(fresh)
    assert _profile(restored)["earned"]


def _profile(folder: Path) -> dict[str, Any]:
    """The folder's profile without its wall-clock `earned_at` stamps."""
    doc: dict[str, Any] = json.loads((folder / "profiles" / "default.json").read_text())
    for row in doc.get("earned", {}).values():
        row.pop("earned_at", None)
    return doc


def test_a_profile_reset_is_replayed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """M25's `ready` starts a fresh profile: a hit clears it as the build did."""
    cache, a, b = tmp_path / "cache", tmp_path / "a", tmp_path / "b"
    for d in (cache, a, b):
        (d / "profiles").mkdir(parents=True)
    old = {"earned": {"first_launch": {"save": "old"}}, "profile": "default", "watch": {}}
    for d in (a, b):
        (d / "profiles" / "default.json").write_text(json.dumps(old))
    monkeypatch.setenv("TST_E2E_FIXTURE_CACHE", str(cache))
    e2e_cache, _ = _tools()

    def build(folder: Path, name: str) -> int:
        _build(folder, name)  # a real save, so the hit has one to copy
        doc = {"earned": {}, "profile": "default", "watch": {name: {"n": 1}}}
        (folder / "profiles" / "default.json").write_text(json.dumps(doc))
        return 0

    monkeypatch.delenv("TST_E2E_FIXTURE_CACHE")
    want = tmp_path / "want"
    (want / "profiles").mkdir(parents=True)
    (want / "profiles" / "default.json").write_text(json.dumps(old))
    build(want, "two-2")
    monkeypatch.setenv("TST_E2E_FIXTURE_CACHE", str(cache))
    assert (
        e2e_cache.run("e2e_x_save.py", ["ready", str(a), "one-1"], lambda: build(a, "one-1")) == 0
    )
    assert e2e_cache.run("e2e_x_save.py", ["ready", str(b), "two-2"], lambda: 1 / 0) == 0  # a hit
    got = json.loads((b / "profiles" / "default.json").read_text())
    assert got == json.loads((want / "profiles" / "default.json").read_text())


def test_a_build_that_changes_another_kind_of_file_is_never_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, folder = tmp_path / "cache", tmp_path / "saves"
    cache.mkdir()
    folder.mkdir()
    monkeypatch.setenv("TST_E2E_FIXTURE_CACHE", str(cache))
    e2e_cache, _ = _tools()

    def build() -> int:
        save_path(folder, "made").write_bytes(b"")
        (folder / "notes.txt").write_text("a side effect a hit could not replay")
        return 0

    assert e2e_cache.run("e2e_x_save.py", ["x", str(folder), "made"], build) == 0
    assert list(cache.iterdir()) == []


def test_an_edit_of_an_existing_save_is_never_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, folder = tmp_path / "cache", tmp_path / "saves"
    cache.mkdir()
    folder.mkdir()
    save_path(folder, "taken").write_bytes(b"")
    monkeypatch.setenv("TST_E2E_FIXTURE_CACHE", str(cache))
    e2e_cache, _ = _tools()
    calls: list[str] = []
    code = e2e_cache.run("e2e_x_save.py", ["edit", str(folder), "taken"], lambda: calls.append("x"))
    assert code == 0
    assert calls == ["x"]
    assert list(cache.iterdir()) == []
