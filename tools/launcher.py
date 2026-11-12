"""Double-click to play (docs/formulas.md 42.5; M29).

`Tech Startup Tycoon.cmd` runs this with uv. Each launch:

1. checks for uv (the .cmd has already found it; this names it in the log);
2. installs the backend's dependencies (`uv sync`, quick when nothing changed);
3. builds the front end when `frontend/dist` is missing or older than its sources
   (`pnpm install` when node_modules is missing or older than the lockfile, then `pnpm build`);
4. starts the API serving the built front end on one local port (TST_FRONTEND_DIR);
5. opens the browser at the Main menu, and keeps running until its window is closed.

Everything goes to `saves/launcher.log`. When a step fails (no uv or Node.js, the port is
taken by something else, a build error) it writes `saves/launcher-error.html`, a plain page
saying what failed and what to do, and opens that instead.

`--make-shortcut` puts a "Tech Startup Tycoon" shortcut on the Windows desktop. Tests replace
the commands, the browser and the clock through `Launcher`'s arguments.
"""

from __future__ import annotations

import argparse
import html
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 8770  # not 8000, so `make dev` can run beside it
READY_TIMEOUT_S = 90.0
POLL_S = 0.5
FRONTEND_SOURCES = (
    "src",
    "public",
    "index.html",
    "package.json",
    "pnpm-lock.yaml",
    "vite.config.ts",
)
SHORTCUT_NAME = "Tech Startup Tycoon"
UV_URL = "https://docs.astral.sh/uv/getting-started/installation/"
NODE_URL = "https://nodejs.org/"

log = logging.getLogger("launcher")


class LaunchError(Exception):
    """A step failed: `what` for the page's title, `hint` for what to do."""

    def __init__(self, step: str, what: str, hint: str) -> None:
        super().__init__(f"{step}: {what}")
        self.step, self.what, self.hint = step, what, hint


type Run = Callable[[Sequence[str], Path], int]
type Start = Callable[[Sequence[str], Path, dict[str, str]], "Process"]


class Process:
    """The running server (subprocess.Popen's surface the launcher uses)."""

    def __init__(self, popen: subprocess.Popen[bytes]) -> None:
        self.popen = popen

    def poll(self) -> int | None:
        return self.popen.poll()

    def wait(self) -> int:
        return self.popen.wait()

    def terminate(self) -> None:
        self.popen.terminate()


def _newest(paths: Iterable[Path]) -> float:
    newest = 0.0
    for path in paths:
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
        elif path.is_dir():
            for f in path.rglob("*"):
                if f.is_file():
                    newest = max(newest, f.stat().st_mtime)
    return newest


@dataclass
class Launcher:
    repo: Path = REPO
    port: int = DEFAULT_PORT
    which: Callable[[str], str | None] = shutil.which
    run: Run | None = None
    start: Start | None = None
    open_url: Callable[[str], object] = webbrowser.open
    fetch: Callable[[str], int] | None = None  # url -> HTTP status (0: no answer)
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    port_free: Callable[[int], bool] | None = None
    skip_install: bool = False
    open_browser: bool = True
    log_file: Path | None = None
    steps: list[str] = field(default_factory=list)

    # --- paths ---------------------------------------------------------------------------
    @property
    def backend(self) -> Path:
        return self.repo / "backend"

    @property
    def frontend(self) -> Path:
        return self.repo / "frontend"

    @property
    def dist(self) -> Path:
        return self.frontend / "dist"

    @property
    def saves(self) -> Path:
        return self.repo / "saves"

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    # --- defaults ------------------------------------------------------------------------
    def _run(self, cmd: Sequence[str], cwd: Path) -> int:
        if self.run is not None:
            return self.run(cmd, cwd)
        log.info("$ %s  (in %s)", " ".join(cmd), cwd)
        with (self.log_file or Path(os.devnull)).open("a", encoding="utf-8") as out:
            return subprocess.call(list(cmd), cwd=cwd, stdout=out, stderr=subprocess.STDOUT)

    def _start(self, cmd: Sequence[str], cwd: Path, env: dict[str, str]) -> Process:
        if self.start is not None:
            return self.start(cmd, cwd, env)
        log.info("$ %s  (in %s)", " ".join(cmd), cwd)
        out = (self.log_file or Path(os.devnull)).open("a", encoding="utf-8")
        return Process(
            subprocess.Popen(
                list(cmd), cwd=cwd, env={**os.environ, **env}, stdout=out, stderr=subprocess.STDOUT
            )
        )

    def _fetch(self, url: str) -> int:
        if self.fetch is not None:
            return self.fetch(url)
        try:
            with urllib.request.urlopen(url, timeout=2) as res:
                return int(res.status)
        except urllib.error.HTTPError as e:
            return int(e.code)
        except (urllib.error.URLError, OSError):
            return 0

    def _port_free(self, port: int) -> bool:
        if self.port_free is not None:
            return self.port_free(port)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                return False
        return True

    # --- steps ---------------------------------------------------------------------------
    def find_uv(self) -> str:
        self.steps.append("uv")
        uv = self.which("uv")
        if uv is None:
            raise LaunchError(
                "Checking for uv",
                "uv is not installed",
                f"Install uv (one command, see {UV_URL}), then double-click Tech Startup Tycoon "
                "again.",
            )
        return uv

    def install_backend(self, uv: str) -> None:
        self.steps.append("sync")
        if self.skip_install:
            return
        if self._run([uv, "sync"], self.backend) != 0:
            raise LaunchError(
                "Installing the game's Python packages",
                "uv sync failed",
                "Check your internet connection and try again; the log has the details.",
            )

    def frontend_stale(self) -> bool:
        index = self.dist / "index.html"
        if not index.is_file():
            return True
        sources = (self.frontend / name for name in FRONTEND_SOURCES)
        return _newest(sources) > index.stat().st_mtime

    def build_frontend(self) -> bool:
        """Build when missing or stale. True when it built."""
        self.steps.append("build")
        if not self.frontend_stale():
            return False
        pnpm = self.which("pnpm")
        cmd: list[str]
        if pnpm is not None:
            cmd = [pnpm]
        elif (corepack := self.which("corepack")) is not None:
            cmd = [corepack, "pnpm"]
        else:
            raise LaunchError(
                "Building the game's screens",
                "Node.js is not installed (the game's screens are built with it once)",
                f"Install Node.js 22 or later from {NODE_URL}, then double-click Tech Startup "
                "Tycoon again.",
            )
        modules = self.frontend / "node_modules" / ".modules.yaml"
        lock = self.frontend / "pnpm-lock.yaml"
        stale_modules = not modules.is_file() or lock.stat().st_mtime > modules.stat().st_mtime
        install = [*cmd, "install", "--frozen-lockfile"]
        if not self.skip_install and stale_modules and self._run(install, self.frontend) != 0:
            raise LaunchError(
                "Installing the screens' packages",
                "pnpm install failed",
                "Check your internet connection and try again; the log has the details.",
            )
        if self._run([*cmd, "run", "build"], self.frontend) != 0:
            raise LaunchError(
                "Building the game's screens",
                "the build failed",
                "Pull the latest version in GitHub Desktop and try again; the log has the details.",
            )
        return True

    def running_here(self) -> bool:
        """The game is already being served on the port (a second double-click)."""
        return self._fetch(self.url + "api/meta/scenarios") == 200 and self._fetch(self.url) == 200

    def serve(self, uv: str) -> Process | None:
        """Start the server, or None when this port already serves the game."""
        self.steps.append("serve")
        if not self._port_free(self.port):
            if self.running_here():
                return None
            raise LaunchError(
                "Starting the game",
                f"port {self.port} is in use by another program",
                f"Close the program using port {self.port}, or start the game on another port: "
                f"uv run --project backend python tools/launcher.py --port {self.port + 1}",
            )
        env = {"TST_FRONTEND_DIR": str(self.dist)}
        cmd = [uv, "run", "uvicorn", "tst.api.app:app", "--host", "127.0.0.1"]
        proc = self._start([*cmd, "--port", str(self.port)], self.backend, env)
        deadline = self.clock() + READY_TIMEOUT_S
        while self.clock() < deadline:
            if proc.poll() is not None:
                raise LaunchError(
                    "Starting the game", "the game's server stopped", "The log has the details."
                )
            if self._fetch(self.url + "api/meta/scenarios") == 200:
                return proc
            self.sleep(POLL_S)
        proc.terminate()
        raise LaunchError(
            "Starting the game", "the server did not answer in time", "The log has the details."
        )

    def open(self) -> None:
        self.steps.append("browser")
        if self.open_browser:
            self.open_url(self.url)

    # --- the whole launch ----------------------------------------------------------------
    def launch(self) -> tuple[int, Process | None]:
        """Run every step; (0, the server) on success, (1, None) after the error page."""
        try:
            uv = self.find_uv()
            self.install_backend(uv)
            self.build_frontend()
            proc = self.serve(uv)
            self.open()
            return 0, proc
        except LaunchError as e:
            log.error("%s", e)
            page = self.error_page(e)
            if self.open_browser:
                self.open_url(page.as_uri())
            return 1, None

    def error_page(self, e: LaunchError) -> Path:
        self.saves.mkdir(parents=True, exist_ok=True)
        page = self.saves / "launcher-error.html"
        logs = self.saves / "launcher.log"
        page.write_text(
            "<!doctype html><meta charset='utf-8'><title>Tech Startup Tycoon could not start"
            "</title><body style='font-family:sans-serif;max-width:40em;margin:3em auto'>"
            "<h1>Tech Startup Tycoon could not start</h1>"
            f"<p><strong>{html.escape(e.step)}:</strong> {html.escape(e.what)}.</p>"
            f"<p>{html.escape(e.hint)}</p>"
            f"<p style='color:#666'>The log is at {html.escape(str(logs))}.</p></body>",
            encoding="utf-8",
        )
        return page


def make_shortcut(repo: Path = REPO, run: Callable[[Sequence[str]], int] | None = None) -> int:
    """A desktop shortcut to Tech Startup Tycoon.cmd (Windows; uses the shell's own COM
    object, so nothing else is needed)."""
    target = repo / f"{SHORTCUT_NAME}.cmd"
    script = (
        "$d=[Environment]::GetFolderPath('Desktop');"
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut("
        f"(Join-Path $d '{SHORTCUT_NAME}.lnk'));"
        f"$s.TargetPath='{target}';$s.WorkingDirectory='{repo}';"
        "$s.WindowStyle=7;$s.Save()"
    )
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    return (run or (lambda c: subprocess.call(list(c))))(cmd)


def _setup_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start Tech Startup Tycoon in the browser.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument(
        "--skip-install", action="store_true", help="assume dependencies are installed"
    )
    parser.add_argument("--make-shortcut", action="store_true", help="add a desktop shortcut")
    args = parser.parse_args(argv)
    if args.make_shortcut:
        code = make_shortcut()
        print("Added the shortcut to your desktop." if code == 0 else "Could not add it.")
        return code
    log_file = REPO / "saves" / "launcher.log"
    _setup_log(log_file)
    launcher = Launcher(
        port=args.port,
        skip_install=args.skip_install,
        open_browser=not args.no_browser,
        log_file=log_file,
    )
    code, proc = launcher.launch()
    if code != 0:
        return code
    print(f"Tech Startup Tycoon is running at {launcher.url}")
    if proc is None:
        print("It was already running; the browser has opened it.")
        return 0
    print("Keep this window open while you play. Close it to stop the game.")
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return 0


if __name__ == "__main__":
    sys.exit(main())
