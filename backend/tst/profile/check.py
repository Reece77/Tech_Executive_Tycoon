"""Award achievements after a committed turn or action (M25 section 2). Reads the committed
state and stored rows, writes only the profile file; a failure here is logged and never
affects the game. Sandbox and modded games earn none; scenario wins only in scenario mode
(the facts themselves say so)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tst.db import repository
from tst.db.models import SaveMetaRow
from tst.db.state_io import META_ID
from tst.loader import LoadedData
from tst.profile.data import earned
from tst.profile.facts import facts_of
from tst.profile.store import Profile, update
from tst.sim.calendar import format_turn
from tst.sim.state import GameState

log = logging.getLogger(__name__)


def why_none(state: GameState, mod_name: str | None) -> str | None:
    """Why this game earns no achievements, or None when it can."""
    if state.mode is not None and state.mode.kind == "sandbox":
        return "Sandbox games earn no achievements."
    if mod_name:
        return f"Modded games earn no achievements (this one uses the mod {mod_name!r})."
    return None


def mod_of(session: Any) -> str | None:
    meta = session.get(SaveMetaRow, META_ID)
    return getattr(meta, "mod_name", None) if meta is not None else None


def check(save_path: Path, data: LoadedData) -> list[str]:
    """Award what the committed state has earned; returns the keys newly earned."""
    if not data.achievements:
        return []
    slug = save_path.name.split(".")[0]
    with repository.read_session(save_path) as session:
        state = repository.read_state(session)
        if why_none(state, mod_of(session)) is not None:
            return []
        found: list[str] = []

        def _award(profile: Profile) -> None:
            watch = profile.watch.get(slug, {})
            facts, new_watch = facts_of(session, state, data, watch)
            if new_watch:
                profile.watch[slug] = new_watch
            else:
                profile.watch.pop(slug, None)
            now = datetime.now(UTC).isoformat(timespec="seconds")
            for a in data.achievements:
                if a.key in profile.earned or not earned(a, facts):
                    continue
                profile.earned[a.key] = {
                    "save": slug,
                    "company": state.player.name,
                    "turn": state.turn,
                    "date_label": format_turn(state.turn),  # the game date on screen
                    "earned_at": now,
                    "seen": False,
                }
                found.append(a.key)

        update(save_path.parent, _award)
    return found


def check_quietly(save_path: Path, data: LoadedData) -> list[str]:
    """`check`, but a failure is logged: the game never depends on the profile."""
    try:
        return check(save_path, data)
    except Exception:
        log.exception("Achievement check failed for %s", save_path.name)
        return []
