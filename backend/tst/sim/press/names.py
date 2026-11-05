"""Words for a press template (29.1, 29.6): the moment's displayed facts and the named rival's
CEO. Imports only state and data so the events package can use it."""

from __future__ import annotations

from tst.sim.data_models import GameData
from tst.sim.state import GameState


def rival_ceo_id(state: GameState, rival_id: int) -> int | None:
    """A rival's CEO (29.4): the founder at a startup (its first executive-level key person),
    else the key person with the highest leadership. Re-chosen whenever asked, so a CEO who
    leaves is succeeded."""
    staff = [e for e in state.staff(rival_id) if e.status in ("active", "notice")]
    if not staff:
        return None
    company = state.company(rival_id)
    if company.is_startup:
        execs = [e for e in staff if e.level == "exec"]
        if execs:
            return min(execs, key=lambda e: e.person_id).person_id
    best = max(staff, key=lambda e: (state.person(e.person_id).skills["leadership"], -e.person_id))
    return best.person_id


def rival_ceo_name(state: GameState, rival_id: int) -> str | None:
    pid = rival_ceo_id(state, rival_id)
    if pid is None:
        return None
    person = state.person(pid)
    return f"{person.first_name} {person.last_name}"


def press_names(state: GameState, data: GameData, company_id: int, turn: int) -> dict[str, str]:
    """{rival_ceo}, {era}, {result} and {promise} for the moment shown in `turn`."""
    moment = next(
        (m for m in state.press_moments if m.company_id == company_id and m.event_turn == turn),
        None,
    )
    if moment is None:
        return {}
    names = {str(k): str(v) for k, v in moment.facts if k in ("era", "result", "promise")}
    if moment.rival_id is not None:
        ceo = rival_ceo_name(state, moment.rival_id)
        if ceo:
            names["rival_ceo"] = ceo
    return names
