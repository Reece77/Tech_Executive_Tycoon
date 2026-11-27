"""A cache of the saves the e2e fixture tools build (M59; an e2e fixture helper, never used by the
game). CI's e2e shards keep it with actions/cache, keyed by a hash of everything a fixture save
is built from (backend/tst, backend/data, backend/migrations, tools/e2e_*, the lock file and the
e2e specs). The engine is deterministic (ADR-0002), so a cached save is the save a fresh build
would make; tests/integration/test_e2e_cache.py holds a cached one's state hash to a fresh one's.

Each `tools/e2e_*_save.py` ends with `sys.exit(e2e_cache.run(__file__, argv, lambda: main(...)))`.
Without TST_E2E_FIXTURE_CACHE (a folder) that is `main(...)` exactly. With it, a call whose
arguments name a save folder and then a save name that does not exist yet is a build:

- a hit copies the cached save into place, writes the new save's name into it (`save_meta.name`
  and the state's `SaveMeta`, the only place a save keeps its name), lists it in the folder's
  `index.json` as `create_save` does, replays the build's changes to the folder's JSON files
  (below) and what the tool printed, with the folder and name put back;
- a miss runs the tool and, if it exited 0, stores the save, its output and what it did to the
  folder's other JSON files, entry by entry (the profile's `earned.<achievement>` rows as it
  played its months; M25's `ready` clearing them for a fresh profile), and a hit replays those
  entries with the new name. A build that changes any other kind of file is never cached.
  Replayed rows keep the miss's `earned_at` stamps, wall-clock times no flow compares.

Every other call (a tool editing a save that exists: `advance`, `holiday` and so on) runs
uncached, as before.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Final, TextIO

ENV: Final = "TST_E2E_FIXTURE_CACHE"
SUFFIX: Final = ".tst.sqlite"
DIR_MARK: Final = "\x00dir\x00"
NAME_MARK: Final = "\x00name\x00"
INDEX: Final = "index.json"  # the folder's save list, which a hit updates as a build does


class _Tee(io.TextIOBase):
    def __init__(self, out: TextIO) -> None:
        self._out = out
        self.text = io.StringIO()

    def write(self, s: str) -> int:
        self.text.write(s)
        return self._out.write(s)

    def flush(self) -> None:
        self._out.flush()


def _target(args: list[str]) -> tuple[int, Path, str] | None:
    """The first argument that is an existing folder followed by a save name."""
    for i, arg in enumerate(args[:-1]):
        if Path(arg).is_dir():
            return i, Path(arg), args[i + 1]
    return None


def key(tool: str, args: list[str]) -> str:
    """The cache key of a build: the tool and its arguments, the folder and name left out."""
    found = _target(args)
    assert found is not None
    i = found[0]
    parts = [Path(tool).name, *args[:i], "<dir>", "<name>", *args[i + 2 :]]
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:32]


def _snapshot(folder: Path) -> dict[str, tuple[int, int]]:
    """Every file under the save folder, by relative path: (size, modified time)."""
    return {
        p.relative_to(folder).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in folder.rglob("*")
        if p.is_file()
    }


Change = tuple[str, str, str, object]  # (file, top key, second key or "", JSON value or _GONE)
_GONE: Final = "\x00gone\x00"


def _json_files(folder: Path) -> dict[str, object]:
    """The folder's JSON files other than the index (profiles/, results/), parsed."""
    out: dict[str, object] = {}
    for p in folder.rglob("*.json"):
        rel = p.relative_to(folder).as_posix()
        if rel != INDEX:
            try:
                out[rel] = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                out[rel] = None
    return out


def _changes(before: object, after: object, rel: str) -> list[Change] | None:
    """What a build did to one JSON file, entry by entry (two levels: `earned.first_hire`),
    or None when the file is not an object of objects and so cannot be replayed."""
    if not isinstance(after, dict) or not isinstance(before, dict | None):
        return None
    old = before or {}
    out: list[Change] = []
    for top in sorted(old.keys() | after.keys()):
        a, b = old.get(top, _GONE), after.get(top, _GONE)
        if a == b:
            continue
        if isinstance(a, dict) and isinstance(b, dict):
            for sub in sorted(a.keys() | b.keys()):
                if a.get(sub, _GONE) != b.get(sub, _GONE):
                    out.append((rel, top, sub, b.get(sub, _GONE)))
        else:
            out.append((rel, top, "", b))
    return out


def _apply(folder: Path, changes: list[Change]) -> None:
    for rel, top, sub, value in changes:
        path = folder / rel
        doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if sub:
            entry = doc.setdefault(top, {})
            if value == _GONE:
                entry.pop(sub, None)
            else:
                entry[sub] = value
        elif value == _GONE:
            doc.pop(top, None)
        else:
            doc[top] = value
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _restore(path: Path, name: str) -> None:
    """Name the copied save and list it in the folder's index, as create_save does."""
    from tst.db.models import SaveMetaRow
    from tst.db.repository import update_index, write_session

    with write_session(path) as session:
        row = session.get(SaveMetaRow, 1)
        assert row is not None
        row.name = name
    update_index(path)


def run(tool: str, args: list[str], build: Callable[[], int | None]) -> int:
    cache = os.environ.get(ENV)
    found = _target(args) if cache else None
    if cache is None or found is None:
        return build() or 0
    _, folder, name = found
    path = folder / f"{name}{SUFFIX}"
    if path.exists():  # an edit of a save that exists
        return build() or 0
    entry = Path(cache) / key(tool, args)
    if (entry / "save.sqlite").exists():
        shutil.copyfile(entry / "save.sqlite", path)
        _restore(path, name)
        files = (entry / "files.json").read_text().replace(NAME_MARK, name)
        _apply(folder, [tuple(c) for c in json.loads(files)])
        out = (entry / "stdout.txt").read_text()
        sys.stdout.write(out.replace(DIR_MARK, str(folder)).replace(NAME_MARK, name))
        print(f"e2e_cache: hit {entry.name} for {name}", file=sys.stderr)
        return 0
    before = _snapshot(folder)
    before_json = _json_files(folder)
    tee = _Tee(sys.stdout)
    real, sys.stdout = sys.stdout, tee
    try:
        code = build() or 0
    finally:
        sys.stdout = real
    after = _snapshot(folder)
    changed = {f for f in after.keys() | before.keys() if after.get(f) != before.get(f)}
    others = changed - {INDEX, path.name}
    if code != 0 or path.name not in changed:
        return code
    after_json = _json_files(folder)
    replay: list[Change] = []
    for rel in sorted(others):
        found_changes = _changes(before_json.get(rel), after_json.get(rel), rel)
        if found_changes is None:  # not a JSON object of objects: cannot be replayed
            return code
        replay += found_changes
    tmp = Path(cache) / f".{entry.name}.{os.getpid()}"
    tmp.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as src, sqlite3.connect(tmp / "save.sqlite") as dst:
        src.backup(dst)
    src.close()
    dst.close()
    text = tee.text.getvalue().replace(str(folder), DIR_MARK).replace(name, NAME_MARK)
    (tmp / "stdout.txt").write_text(text)
    (tmp / "files.json").write_text(json.dumps(replay).replace(name, NAME_MARK))
    if entry.exists():  # another process stored it first
        shutil.rmtree(tmp)
    else:
        tmp.rename(entry)
    print(f"e2e_cache: stored {entry.name} for {name}", file=sys.stderr)
    return 0
