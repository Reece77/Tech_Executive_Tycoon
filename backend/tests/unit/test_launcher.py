"""M29 (formulas.md 42.5): the launcher's steps with a fake uv, pnpm, server and browser."""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

TOOLS = Path(__file__).resolve().parents[3] / "tools"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tst_launcher", TOOLS / "launcher.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tst_launcher"] = module
    spec.loader.exec_module(module)
    return module


launcher = _load()


class FakeServer:
    def __init__(self) -> None:
        self.stopped = False

    def poll(self) -> int | None:
        return None

    def wait(self) -> int:
        return 0

    def terminate(self) -> None:
        self.stopped = True


def repo(tmp_path: Path, *, built: bool = False, modules: bool = True) -> Path:
    root = tmp_path / "repo"
    (root / "backend").mkdir(parents=True)
    fe = root / "frontend"
    (fe / "src").mkdir(parents=True)
    (fe / "src" / "main.tsx").write_text("x")
    (fe / "pnpm-lock.yaml").write_text("lock")
    if modules:
        (fe / "node_modules").mkdir()
        (fe / "node_modules" / ".modules.yaml").write_text("m")
    if built:
        (fe / "dist").mkdir()
        (fe / "dist" / "index.html").write_text("<html>")
        later = (fe / "src" / "main.tsx").stat().st_mtime + 10
        os.utime(fe / "dist" / "index.html", (later, later))
    return root


def make(tmp_path: Path, **kw: Any) -> tuple[Any, list[list[str]], list[str]]:
    ran: list[list[str]] = []
    opened: list[str] = []
    tools = {"uv": "/bin/uv", "pnpm": "/bin/pnpm"}
    tools.update(kw.pop("tools", {}))
    ready = kw.pop("ready", True)

    def run(cmd: Sequence[str], cwd: Path) -> int:
        ran.append([*cmd])
        if cmd[-2:] == ["run", "build"]:
            dist = cwd / "dist"
            dist.mkdir(exist_ok=True)
            (dist / "index.html").write_text("<html>")
        return 0

    def start(cmd: Sequence[str], cwd: Path, env: dict[str, str]) -> FakeServer:
        ran.append([*cmd])
        assert env["TST_FRONTEND_DIR"].endswith("dist")
        return FakeServer()

    lch = launcher.Launcher(
        repo=kw.pop("root"),
        which=lambda name: tools.get(name),
        run=run,
        start=start,
        open_url=opened.append,
        fetch=lambda url: 200 if ready else 0,
        sleep=lambda s: None,
        port_free=kw.pop("port_free", lambda p: True),
        **kw,
    )
    return lch, ran, opened


def test_a_fresh_clone_installs_builds_serves_and_opens(tmp_path: Path) -> None:
    lch, ran, opened = make(tmp_path, root=repo(tmp_path, modules=False))
    code, proc = lch.launch()
    assert code == 0 and proc is not None
    assert lch.steps == ["uv", "sync", "build", "serve", "browser"]
    assert ran[0] == ["/bin/uv", "sync"]
    assert ["/bin/pnpm", "install", "--frozen-lockfile"] in ran
    assert ["/bin/pnpm", "run", "build"] in ran
    assert ran[-1][:3] == ["/bin/uv", "run", "uvicorn"] and ran[-1][-1] == "8770"
    assert opened == ["http://127.0.0.1:8770/"]


def test_a_built_front_end_is_not_rebuilt(tmp_path: Path) -> None:
    lch, ran, _ = make(tmp_path, root=repo(tmp_path, built=True))
    assert lch.launch()[0] == 0
    assert not any("build" in c for c in ran)


def test_changed_sources_rebuild(tmp_path: Path) -> None:
    root = repo(tmp_path, built=True)
    src = root / "frontend" / "src" / "main.tsx"
    later = (root / "frontend" / "dist" / "index.html").stat().st_mtime + 10
    os.utime(src, (later, later))
    lch, ran, _ = make(tmp_path, root=root)
    assert lch.launch()[0] == 0
    assert ["/bin/pnpm", "run", "build"] in ran
    assert ["/bin/pnpm", "install", "--frozen-lockfile"] not in ran  # modules are current


def test_missing_uv_shows_the_error_page(tmp_path: Path) -> None:
    root = repo(tmp_path)
    lch, ran, opened = make(tmp_path, root=root, tools={"uv": None})
    code, proc = lch.launch()
    assert code == 1 and proc is None and ran == []
    page = root / "saves" / "launcher-error.html"
    assert opened == [page.as_uri()]
    assert "uv is not installed" in page.read_text(encoding="utf-8")


def test_missing_node_shows_the_error_page(tmp_path: Path) -> None:
    root = repo(tmp_path)
    lch, _, _ = make(tmp_path, root=root, tools={"pnpm": None})
    assert lch.launch()[0] == 1
    assert "Node.js is not installed" in (root / "saves" / "launcher-error.html").read_text(
        encoding="utf-8"
    )


def test_corepack_stands_in_for_pnpm(tmp_path: Path) -> None:
    lch, ran, _ = make(
        tmp_path, root=repo(tmp_path), tools={"pnpm": None, "corepack": "/bin/corepack"}
    )
    assert lch.launch()[0] == 0
    assert ["/bin/corepack", "pnpm", "run", "build"] in ran


def test_a_port_in_use_by_another_program_is_an_error(tmp_path: Path) -> None:
    root = repo(tmp_path, built=True)
    lch, _, _ = make(tmp_path, root=root, port_free=lambda p: False, ready=False)
    assert lch.launch()[0] == 1
    assert "port 8770 is in use" in (root / "saves" / "launcher-error.html").read_text(
        encoding="utf-8"
    )


def test_a_second_launch_opens_the_running_game(tmp_path: Path) -> None:
    lch, ran, opened = make(tmp_path, root=repo(tmp_path, built=True), port_free=lambda p: False)
    code, proc = lch.launch()
    assert code == 0 and proc is None and opened == ["http://127.0.0.1:8770/"]
    assert not any("uvicorn" in c for c in ran)


def test_a_server_that_never_answers_times_out(tmp_path: Path) -> None:
    root = repo(tmp_path, built=True)
    ticks = iter(range(0, 10_000, 10))
    lch, _, _ = make(tmp_path, root=root, ready=False, clock=lambda: float(next(ticks)))
    assert lch.launch()[0] == 1
    assert "did not answer" in (root / "saves" / "launcher-error.html").read_text(encoding="utf-8")


def test_make_shortcut_points_at_the_cmd(tmp_path: Path) -> None:
    seen: list[Sequence[str]] = []
    assert launcher.make_shortcut(tmp_path, run=lambda c: seen.append(c) or 0) == 0
    script = seen[0][-1]
    assert "Tech Startup Tycoon.cmd" in script and "CreateShortcut" in script


def test_the_cmd_files_run_the_launcher() -> None:
    root = TOOLS.parent
    play = (root / "Tech Startup Tycoon.cmd").read_bytes()
    assert b"tools\\launcher.py" in play and b"\r\n" in play  # CRLF for cmd.exe
    assert b"launcher_missing_uv.html" in play
    assert (root / "tools" / "launcher_missing_uv.html").is_file()


@pytest.mark.parametrize("name", ["src", "index.html", "pnpm-lock.yaml"])
def test_front_end_sources_are_watched(name: str) -> None:
    assert name in launcher.FRONTEND_SOURCES
