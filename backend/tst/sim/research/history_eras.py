"""History eras (M50b, docs/formulas.md 60.5): the eras before the 2008 world.

A 2000 world has no public cloud, no social networks of scale, no video or music streaming
and no electric-car industry. Each of these is a history era in eras.yaml's `history_eras`,
with the categories it `opens`. A category an era opens takes no product launch until the era
arrives: on its historical month, or earlier in the month a company's level in the era's
domain reaches its threshold (21.4's rule, `eras.causer`), so the player can be early by
research but cannot skip the era: a history era waits for the history eras listed before it
in its domain, and no other era arrives while a history era is still to come. The arrival is
recorded in `state.era_arrivals` (the inbox tells every company the player controls), and no
baseline, boost or estimate reads it.

A history era is played only in a world begun before its month (`world_start_turn`): every
history era arrives by January 2008 (the loader's check), so a 2008 or a 2010 game has every
category open from its first month and never records one. It draws nothing.
"""

from __future__ import annotations

from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.log import LogItem, inbox_item
from tst.sim.modes.models import world_start_turn
from tst.sim.research.data import EraDef
from tst.sim.research.eras import causer
from tst.sim.research.levels import historical_turn
from tst.sim.research.models import EraArrival
from tst.sim.state import GameState, player_companies, with_era_arrival


def played(state: GameState, era: EraDef) -> bool:
    """The era is history still to come in this world (a world begun before its month)."""
    return world_start_turn(state.mode) < historical_turn(era)


def still_to_come(state: GameState, data: GameData) -> bool:
    """A history era of this world has not arrived yet: the later eras wait for it (M50b: an
    era cannot skip its prerequisites, so Mobile-first never comes before Smartphones)."""
    return any(
        played(state, e) and state.era_arrival(e.key) is None for e in data.eras.history_eras
    )


def _waiting(state: GameState, data: GameData, era: EraDef) -> bool:
    """An earlier history era of the same domain is still to come."""
    for e in data.eras.history_eras:
        if e.key == era.key:
            return False
        if e.domain == era.domain and played(state, e) and state.era_arrival(e.key) is None:
            return True
    return False


def opening_era(data: GameData, category: str) -> EraDef | None:
    """The history era that opens `category`, if any."""
    return next((e for e in data.eras.history_eras if category in e.opens), None)


def category_open(state: GameState, data: GameData, category: str) -> bool:
    """A product may launch in `category` this month: no history era opens it, the world began
    at or after the era's month, or the era has arrived."""
    era = opening_era(data, category)
    if era is None or not played(state, era):
        return True
    arrival = state.era_arrival(era.key)
    return arrival is not None and arrival.turn <= state.turn


def opens_label(data: GameData, category: str) -> str | None:
    """The history era's label and month for a closed category's launch problem."""
    era = opening_era(data, category)
    if era is None:
        return None
    return f"the {era.label} era ({format_turn(historical_turn(era))}, or earlier by research)"


def arrive_history_eras(
    state: GameState, data: GameData, balance: Balance
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Phase 3, before the other eras: each history era still to come in this world arrives on
    its historical month, or this month if a company's level reaches its threshold (21.4)."""
    logs: list[LogItem] = []
    for era in data.eras.history_eras:
        if not played(state, era) or state.era_arrival(era.key) is not None:
            continue
        if _waiting(state, data, era):  # in eras.yaml order within a domain
            continue
        hist = historical_turn(era)
        found = causer(state, data, balance, era) if state.turn < hist else None
        if state.turn < hist and found is None:
            continue
        cid = found[0] if found else None
        state = with_era_arrival(
            state, EraArrival(era.key, state.turn, cid, max(0, hist - state.turn))
        )
        names = ", ".join(data.category(c).label for c in era.opens)
        logs += [
            inbox_item(
                state.turn,
                c.id,
                "history_era_arrived",
                era=era.label,
                categories=names,
                early="" if cid is None else f", {hist - state.turn} months early",
            )
            for c in player_companies(state)
        ]
    return state, tuple(logs)
