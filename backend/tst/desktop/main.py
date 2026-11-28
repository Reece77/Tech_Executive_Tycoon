"""The installed game's entry point (M58 sub-task 1): `Tech Startup Tycoon.exe`.

1. One copy only: a second launch brings the first window forward and exits.
2. Saves in Documents/Tech Startup Tycoon/saves; settings, the API key and logs in app data
   (`paths`); the key is loaded from app data's `.env` into this process only.
3. The API and the built front end on one free port on 127.0.0.1 (never another interface),
   in this process on a background thread (uvicorn).
4. A pywebview window titled Tech Startup Tycoon on it; closing the window stops the server.
5. The update check runs once, in the background, after the window opens.

`--headless` serves without a window until stopped (the release smoke test); `--smoke-window`
opens the window, waits for the page to load, closes it and exits 0.

    uv run --group desktop python -m tst.desktop        # from backend/, after `pnpm build`
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import signal
import socket
import sys
import threading
import time
import webbrowser
from collections.abc import Sequence
from pathlib import Path

from tst.desktop import context, imports, secrets
from tst.desktop.instance import SingleInstance, focus_running
from tst.desktop.paths import APP_NAME, DesktopPaths
from tst.desktop.version import bundle_root, current_version

log = logging.getLogger("tst.desktop")

HOST = "127.0.0.1"  # never 0.0.0.0: the game is for this computer only
READY_TIMEOUT_S = 60.0
FOCUS_RETRY_S = 15.0  # a second launch while the first is still starting
LOG_BYTES = 1_000_000
LOG_KEEP = 3
WINDOW_SIZE = (1440, 900)
WINDOW_MIN = (1024, 700)
BACKGROUND = "#1a1b1e"  # the dark theme's page colour, shown before the page paints


def frontend_dir() -> Path:
    root = bundle_root()
    if root is not None:
        return root / "frontend"
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


def setup_logging(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=LOG_BYTES, backupCount=LOG_KEEP, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(secrets.RedactingFilter())
    handlers: list[logging.Handler] = [handler]
    if sys.stderr is not None:  # the windowed exe has no console
        console = logging.StreamHandler(sys.stderr)
        console.addFilter(secrets.RedactingFilter())
        handlers.append(console)
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)


def configure_environment(paths: DesktopPaths, environ: dict[str, str] | os._Environ[str]) -> None:
    """Point the API's settings at the desktop folders, before tst.config is first read."""
    environ["TST_SAVE_DIR"] = str(paths.saves)
    environ["TST_FRONTEND_DIR"] = str(frontend_dir())
    secrets.load_into(paths.env_file, environ)


def bind(port: int) -> socket.socket:
    """A listening socket on 127.0.0.1 (port 0: any free port)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform != "win32":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, port))
    sock.listen(128)
    return sock


class Server:
    """uvicorn on its own thread, on an already-bound socket."""

    def __init__(self, sock: socket.socket) -> None:
        import uvicorn

        from tst.api.app import create_app

        self.sock = sock
        self.port = int(sock.getsockname()[1])
        config = uvicorn.Config(create_app(), log_config=None, access_log=False, lifespan="off")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(
            target=self.server.run, kwargs={"sockets": [sock]}, name="server", daemon=True
        )

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self.port}/"

    def start(self, timeout: float = READY_TIMEOUT_S) -> None:
        self.thread.start()
        deadline = time.monotonic() + timeout
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("the game's server did not start")
            time.sleep(0.05)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)
        self.sock.close()


def _import_offer(paths: DesktopPaths) -> imports.ImportOffer | None:
    if context.load_settings(paths).get("import_answered"):
        return None
    found = imports.candidates(paths.documents.parent, Path.home())
    return imports.find_offer(paths.saves, found)


def _message_box(text: str) -> None:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, 0x10)  # type: ignore[attr-defined,unused-ignore]


def run_window(ctx: context.DesktopContext, url: str, smoke: bool) -> bool:
    """The game's window; returns once it is closed (True: the page loaded)."""
    import webview  # the desktop dependency group; imported only here

    window = webview.create_window(
        APP_NAME,
        url,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=WINDOW_MIN,
        background_color=BACKGROUND,
        text_select=True,
    )
    loaded = threading.Event()

    def focus() -> None:
        window.restore()
        window.show()
        window.on_top = True
        window.on_top = False

    def on_loaded() -> None:
        loaded.set()
        log.info("window loaded %s", url)
        if smoke:
            threading.Timer(1.0, window.destroy).start()

    ctx.focus, ctx.close = focus, window.destroy
    window.events.loaded += on_loaded
    gui = "edgechromium" if sys.platform == "win32" else None
    webview.start(gui=gui, private_mode=False, storage_path=str(ctx.paths.app_data / "webview"))
    return loaded.is_set()


def wait_headless(ctx: context.DesktopContext) -> None:
    stop = threading.Event()
    ctx.close = stop.set
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.wait(0.5):
        pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Play Tech Startup Tycoon.")
    parser.add_argument("--headless", action="store_true", help="serve without a window")
    parser.add_argument("--port", type=int, default=0, help="the local port (0: any free one)")
    parser.add_argument("--smoke-window", action="store_true", help="open, load, close, exit")
    parser.add_argument("--no-update-check", action="store_true")
    args = parser.parse_args(argv)

    paths = DesktopPaths.resolve()
    paths.make()
    setup_logging(paths.log_file)
    version = current_version()
    log.info("%s %s starting (saves in %s)", APP_NAME, version, paths.saves)

    instance = SingleInstance(paths.lock_file, paths.instance_file)
    if not instance.acquire():
        deadline = time.monotonic() + FOCUS_RETRY_S
        while time.monotonic() < deadline:
            if focus_running(paths.instance_file):
                log.info("already running: focused the open window")
                return 0
            time.sleep(0.5)
        log.error("another copy holds the lock but does not answer")
        _message_box(
            "Tech Startup Tycoon is already running but not answering. Close it and try again."
        )
        return 1

    configure_environment(paths, os.environ)
    from tst.config import get_settings

    get_settings.cache_clear()
    ctx = context.DesktopContext(
        paths=paths, version=version, check_token=instance.check_token, token=instance.token
    )
    ctx.import_offer = _import_offer(paths)
    context.install(ctx)
    server: Server | None = None
    try:
        server = Server(bind(args.port))
        server.start()
        instance.publish(server.port)
        log.info("serving on %s", server.url)
        if not args.no_update_check:
            ctx.start_check()
        if args.headless:
            wait_headless(ctx)
            return 0
        try:
            loaded = run_window(ctx, server.url, args.smoke_window)
        except Exception:
            log.exception("the window could not open")
            _message_box(
                "Tech Startup Tycoon could not open its window (it needs Microsoft Edge "
                "WebView2, part of Windows 10 and 11). It will open in your browser instead; "
                "close this message when you have finished playing."
            )
            webbrowser.open(server.url)
            _message_box("Close this message to stop Tech Startup Tycoon.")
            return 1
        log.info("window closed")
        return 0 if loaded or not args.smoke_window else 1
    except Exception:
        log.exception("could not start")
        _message_box(f"Tech Startup Tycoon could not start. The log is at {paths.log_file}.")
        return 1
    finally:
        if server is not None:
            server.stop()
        context.install(None)
        instance.release()
        log.info("stopped")


if __name__ == "__main__":
    sys.exit(main())
