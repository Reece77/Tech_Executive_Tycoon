"""Scenario results across saves (M51, docs/formulas.md 63.3): `<saves>/results/<profile>.json`,
one per player profile (as the achievement profile, M25), outside every save, so results survive
a save's deletion and the installer's updates (saves live in Documents, M58).

It holds one record per scenario save once its verdict is in: the result, the game date, the
company score at the verdict with its parts, the challenge rules and their multiplier, and the
score they give. Written atomically under a lock after a committed turn; never read by the sim.
A failure here is logged and never affects the game."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from tst.loader import LoadedData
from tst.profile.store import profile_name
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance
from tst.sim.modes.challenges import score_mult
from tst.sim.score import points
from tst.sim.state import GameState

log = logging.getLogger(__name__)

RESULTS_DIR: Final = "results"
VERSION: Final = 1
_LOCK = threading.Lock()


def results_path(save_dir: Path, name: str | None = None) -> Path:
    return save_dir / RESULTS_DIR / f"{name or profile_name()}.json"


def _read(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """scenario key -> save slug -> record; an unreadable file starts again."""
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = raw.get("results") if isinstance(raw, dict) else None
    return dict(out) if isinstance(out, dict) else {}


def _write(path: Path, name: str, results: dict[str, dict[str, dict[str, Any]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp")
    body = {"version": VERSION, "profile": name, "results": results}
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(body, f, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load(save_dir: Path, name: str | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    with _LOCK:
        return _read(results_path(save_dir, name))


def record_of(state: GameState, slug: str, balance: Balance) -> dict[str, Any] | None:
    """The save's result record, or None before a verdict (or outside a scenario)."""
    mode = state.mode
    if mode is None or mode.kind != "scenario" or mode.scenario is None or mode.result is None:
        return None
    cid = state.player.id
    snap = next((s for s in reversed(state.scores) if s.company_id == cid), None)
    mult = score_mult(mode, balance)
    score = snap.score if snap is not None else 0
    return {
        "scenario": mode.scenario,
        "save": slug,
        "company": state.player.name,
        "result": mode.result,
        "turn": mode.result_turn,
        "date_label": format_turn(mode.result_turn if mode.result_turn is not None else state.turn),
        "score": score,
        "parts": None if snap is None else points(snap, balance),  # 30.1's parts, in points
        "challenges": list(mode.challenges),
        "multiplier": mult,
        "adjusted": round(score * mult),
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def best(
    records: dict[str, dict[str, Any]], *, without: str | None = None
) -> dict[str, Any] | None:
    """A scenario's best record: a success over a failure, then the higher adjusted score, then
    the earlier. `without` leaves one save's records out (the result screen's comparison)."""
    kept = sorted(
        (r for r in records.values() if r.get("save") != without),
        key=lambda r: str(r.get("recorded_at") or ""),
    )
    if not kept:
        return None  # max keeps the first of equals: the earliest
    return max(
        kept, key=lambda r: (1 if r.get("result") == "success" else 0, int(r.get("adjusted") or 0))
    )


def record(save_path: Path, data: LoadedData) -> bool:
    """Keep the committed save's verdict, once; True when a record was added."""
    from tst.db import repository
    from tst.db.models import SaveMetaRow
    from tst.db.state_io import META_ID
    from tst.sim.modes.scenarios import DONE

    slug = save_path.name.split(".")[0]
    with repository.read_session(save_path) as session:
        meta = session.get(SaveMetaRow, META_ID)
        if meta is None or meta.game_state != DONE:  # cheap: most turns end here
            return False
        state = repository.read_state(session)
    entry = record_of(state, slug, data.balance)
    if entry is None:
        return False
    path = results_path(save_path.parent)
    with _LOCK:
        results = _read(path)
        mine = results.setdefault(str(entry["scenario"]), {})
        key = f"{slug}:{state.save_meta.master_seed}"  # a later save of the same name is another
        if key in mine:
            return False
        mine[key] = entry
        _write(path, profile_name(), results)
    return True


def record_quietly(save_path: Path, data: LoadedData) -> None:
    """`record`, but a failure is logged: the game never depends on the results file."""
    try:
        record(save_path, data)
    except Exception:
        log.exception("Scenario result not recorded for %s", save_path.name)
