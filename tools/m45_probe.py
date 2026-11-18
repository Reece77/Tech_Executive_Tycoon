"""M45 TEMPORARY probe (removed before merging): 14 months from a V6 save, as played, with the
periodic backup off, and with the candidate prune off, to find what makes one month slow on CI."""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

from tests.helpers import answer_critical, continue_at_end
from tst.db import history, migrate, repository
from tst.loader import load_all


def months(src: Path, variant: str) -> list[int]:
    folder = Path(tempfile.mkdtemp())
    path = folder / src.name
    shutil.copy(src, path)
    migrate.ensure_current(path)
    data = load_all(Path(__file__).resolve().parents[1] / "backend" / "data")
    continue_at_end(path, data)
    keep_b, keep_p = repository.periodic_backup_in_background, history.prune_candidates
    if variant == "no-backup":
        repository.periodic_backup_in_background = lambda *a, **k: None  # type: ignore[assignment]
    if variant == "no-prune":
        history.prune_candidates = lambda *a, **k: 0  # type: ignore[assignment]
    out = []
    try:
        for _ in range(14):
            answer_critical(path, data)
            t = time.perf_counter()
            repository.run_turn(path, data)
            out.append(round((time.perf_counter() - t) * 1000))
    finally:
        repository.periodic_backup_in_background, history.prune_candidates = keep_b, keep_p
    time.sleep(3)
    shutil.rmtree(folder, ignore_errors=True)
    return out


if __name__ == "__main__":
    save = Path(sys.argv[1])
    for variant in ("as-played", "no-backup", "no-prune", "as-played"):
        print(f"M45 probe {variant}: {months(save, variant)}", flush=True)
