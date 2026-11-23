"""One running copy (M58 sub-task 1).

The first launch holds an OS lock on `instance.lock` for its lifetime and writes
`instance.json` (its port and a random token). A second launch fails to take the lock, reads
the file and asks the first, over its own 127.0.0.1 server, to bring its window forward
(`POST /api/desktop/focus` with the token), then exits. The lock dies with the process, so a
crash never leaves the game unable to start.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import IO

log = logging.getLogger(__name__)

FOCUS_PATH = "/api/desktop/focus"
TOKEN_HEADER = "X-TST-Instance"


def _try_lock(handle: IO[bytes]) -> bool:
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


class SingleInstance:
    def __init__(self, lock_file: Path, instance_file: Path) -> None:
        self.lock_file = lock_file
        self.instance_file = instance_file
        self.token = secrets.token_urlsafe(24)
        self._handle: IO[bytes] | None = None

    def acquire(self) -> bool:
        """True when this is the only copy (keep the object alive while running)."""
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        handle = self.lock_file.open("a+b")
        if not _try_lock(handle):
            handle.close()
            return False
        self._handle = handle
        return True

    def publish(self, port: int) -> None:
        """Tell later launches where this copy listens."""
        body = {"pid": os.getpid(), "port": port, "token": self.token}
        tmp = self.instance_file.with_name(self.instance_file.name + ".partial")
        tmp.write_text(json.dumps(body), encoding="utf-8")
        tmp.replace(self.instance_file)

    def release(self) -> None:
        if self._handle is not None:
            self.instance_file.unlink(missing_ok=True)
            self._handle.close()
            self._handle = None

    def check_token(self, token: str | None) -> bool:
        return token is not None and secrets.compare_digest(token, self.token)


def focus_running(instance_file: Path, timeout: float = 3.0) -> bool:
    """Ask the running copy to show its window. True when it answered."""
    try:
        info = json.loads(instance_file.read_text(encoding="utf-8"))
        port, token = int(info["port"]), str(info["token"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{FOCUS_PATH}",
        method="POST",
        headers={TOKEN_HEADER: token},
        data=b"",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return int(res.status) == 204
    except (urllib.error.URLError, OSError):
        log.warning("the running copy did not answer on port %s", port)
        return False
