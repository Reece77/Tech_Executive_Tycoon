"""Run the API (uvicorn on :8000) and the front end (Vite on :5173) together.

Used by `make dev`. Ctrl+C stops both.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
IS_WINDOWS = sys.platform == "win32"


def main() -> int:
    procs = [
        subprocess.Popen(
            ["uv", "run", "uvicorn", "tst.api.app:app", "--reload", "--port", "8000"],
            cwd=REPO / "backend",
            shell=IS_WINDOWS,
        ),
        subprocess.Popen(["pnpm", "dev"], cwd=REPO / "frontend", shell=IS_WINDOWS),
    ]
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            p.wait()
    return max((p.returncode or 0) for p in procs)


if __name__ == "__main__":
    sys.exit(main())
