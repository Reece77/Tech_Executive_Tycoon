"""Geopolitics in the turn (docs/formulas.md 39).

- Phase 5, before the markets: customers in closed destinations leave (sales.py); after them,
  tariffs and local partners' shares post (tariffs.py).
- Phase 12: licence decisions and expiries, then entity listings for this month; then next
  month's tension, escalation or détente (tension.py), and the events for every rule announced
  next month (events.py).
"""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.geopolitics import actions as ga
from tst.sim.geopolitics import events as ge
from tst.sim.geopolitics import listing, sales, tariffs, tension, world
from tst.sim.geopolitics import rules as gr
from tst.sim.ledger import LedgerEntry
from tst.sim.log import LogItem
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def before_markets(state: GameState, balance: Balance, data: GameData) -> GameState:
    if not world.enabled(data):
        return state
    return sales.exits(state, balance, data)


def after_markets(state: GameState, balance: Balance, data: GameData) -> list[LedgerEntry]:
    if not world.enabled(data):
        return []
    return [
        *tariffs.tariffs_month(state, balance, data),
        *tariffs.partner_month(state, balance, data),
    ]


def month_end(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    if not world.enabled(data):
        return state, []
    state, logs = ga.decide(state, rng, balance, data)
    state, listed = listing.listing_month(state, rng, balance, data)
    state, shock, rule_key = tension.next_month(state, rng, balance, data)
    due = state.turn + 1
    arriving = list(gr.announced_in(state, data, due))
    detentes = [
        f"{ge.DETENTE_PREFIX}{d.key}" for d in gr.controls_of(data).detentes if d.start_turn == due
    ]
    if shock == "escalation" and rule_key is not None:
        arriving += [a for a in gr.all_rules(state, data) if a.seeded and a.start_turn == due]
    elif shock == "detente" and rule_key is not None:
        detentes.append(f"{ge.DETENTE_PREFIX}{rule_key}")
    state = ge.announce(state, data, balance, arriving, detentes, listed)
    return state, logs
