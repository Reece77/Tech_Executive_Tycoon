"""A cache of the saves the e2e fixture tools build (M59; an e2e fixture helper, never used by the
game). CI's e2e shards keep it with actions/cache, keyed by a hash of everything a fixture save
is built from (backend/tst, backend/data, backend/migrations, tools/e2e_*, the lock file and the
e2e specs). The engine is deterministic (ADR-0002), so a cached save is the save a fresh build
would make; tests/integration/test_e2e_cache.py holds a cached one's state hash to a fresh one's.

Each `tools/e2e_*_save.py` ends with `sys.exit(e2e_cache.run(__file__, argv, lambda: main(...)))`.
Without TST_E2E_FIXTURE_CACHE (a folder) that is `main(...)` exactly. With it, a call whose
arguments name a save folder and then a save name that does not exist yet is a build:

- a hit copies the cached save into place, writes the new save's name into it (`save_meta.name`
  and the state's `SaveMeta`, the only place a save keeps its name) and replays what the tool
  printed, with the folder and name put back;
- a miss runs the tool and, if it exited 0 and the only save file it made is that one, stores
  the save and its output.

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


def _saves(folder: Path) -> set[str]:
    return {p.name for p in folder.iterdir() if SUFFIX in p.name}


def _rename(path: Path, name: str) -> None:
    from tst.db.models import SaveMetaRow
    from tst.db.repository import write_session

    with write_session(path) as session:
        row = session.get(SaveMetaRow, 1)
        assert row is not None
        row.name = name


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
        _rename(path, name)
        out = (entry / "stdout.txt").read_text()
        sys.stdout.write(out.replace(DIR_MARK, str(folder)).replace(NAME_MARK, name))
        print(f"e2e_cache: hit {entry.name} for {name}", file=sys.stderr)
        return 0
    before = _saves(folder)
    tee = _Tee(sys.stdout)
    real, sys.stdout = sys.stdout, tee
    try:
        code = build() or 0
    finally:
        sys.stdout = real
    made = _saves(folder) - before
    if code != 0 or made != {path.name}:
        return code
    tmp = Path(cache) / f".{entry.name}.{os.getpid()}"
    tmp.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as src, sqlite3.connect(tmp / "save.sqlite") as dst:
        src.backup(dst)
    src.close()
    dst.close()
    text = tee.text.getvalue().replace(str(folder), DIR_MARK).replace(name, NAME_MARK)
    (tmp / "stdout.txt").write_text(text)
    if entry.exists():  # another process stored it first
        shutil.rmtree(tmp)
    else:
        tmp.rename(entry)
    print(f"e2e_cache: stored {entry.name} for {name}", file=sys.stderr)
    return 0
