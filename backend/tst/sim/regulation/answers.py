"""The player's answers to regulation events (docs/formulas.md 48.3-48.4), applied by the engine.

An event finds its case or order by the month it is shown and its template (several the same
month pair in id order). Steps: at an inquiry `cooperate` (the case runs on, contested), `settle`
or `lobby`; at the objections `settle`, `contest` or `lobby`; at a ruling `comply` or `appeal`; at
a structural order `spin_off`, `sell`, `appeal` or `wait`. The odds the texts show are the ranges
in balance.yaml; the chances are drawn inside them when decided and never stored."""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.events.describe import dollars
from tst.sim.events.models import GameEvent
from tst.sim.ledger import LedgerBalances, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.regulation import cases, structural
from tst.sim.regulation import data as rdata
from tst.sim.regulation.models import Case, Order
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

CASE_TEMPLATES: Final = (cases.INQUIRY, cases.OBJECTIONS, cases.RULING)
CONDUCT_WORDS: Final[dict[str, str]] = {
    "self_preferencing": "favouring its own apps",
    "anti_steering": "stopping apps from pointing users to cheaper prices",
    "removals": "removing rivals' apps from its store",
    "fees": "its store fees",
    "acquisitions": "buying up young rivals",
    "noncompliance": "breaking the duties it was given",
    "tying": "tying its services together",
    "exclusivity": "exclusive deals",
    "dominance": "its dominant position",
}


def _paired[T: (Case, Order)](items: list[T], state: GameState, event: GameEvent) -> T | None:
    if not items:
        return None
    events = sorted(
        e.id
        for e in state.events
        if e.turn == event.turn
        and e.company_id == event.company_id
        and e.template_id == event.template_id
    )
    ordered = sorted(items, key=lambda x: x.id)
    index = events.index(event.id) if event.id in events else 0
    return ordered[min(index, len(ordered) - 1)]


def _latest[T: (Case, Order)](items: list[T]) -> list[T]:
    """The records asked most recently (an engine-queued event is shown the month it was asked
    for, or the month after)."""
    if not items:
        return []
    last = max(x.asked_turn if x.asked_turn is not None else 0 for x in items)
    return [x for x in items if (x.asked_turn if x.asked_turn is not None else 0) == last]


def case_for(state: GameState, event: GameEvent) -> Case | None:
    return _paired(
        _latest(
            [
                c
                for c in state.reg_cases
                if c.company_id == event.company_id
                and c.asked_template == event.template_id
                and c.asked_turn is not None
                and c.asked_turn <= event.turn
                and c.stage != "closed"
            ]
        ),
        state,
        event,
    )


def order_for(state: GameState, event: GameEvent) -> Order | None:
    return _paired(
        _latest(
            [
                o
                for o in state.reg_orders
                if o.company_id == event.company_id
                and o.asked_template == event.template_id
                and o.asked_turn is not None
                and o.asked_turn <= event.turn
                and o.status in ("open", "appealing")
            ]
        ),
        state,
        event,
    )


def regulation_step(
    state: GameState,
    event: GameEvent,
    step: str,
    rng: RngFactory,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not rdata.enabled(data):
        return state, [], []
    if event.template_id == structural.ORDER_EVENT:
        o = order_for(state, event)
        if o is None or o.status != "open":
            return state, [], []
        if step == "sell":
            return structural.sell(state, o, balance, data)
        if step == "spin_off":
            return structural.spin_off(state, o, balances, balance, data)
        if step == "appeal" and o.appeal_until is None:
            return structural.appeal(state, o, rng, balance), [], []
        return state, [], []
    case = case_for(state, event)
    if case is None or case.stage == "closed":
        return state, [], []
    if step == "settle" and case.stage in ("inquiry", "objections"):
        return cases.settle(state, case, balance, data)
    if step == "lobby" and case.stage in ("inquiry", "objections"):
        state, entries = cases.lobby(state, case, balance)
        return state, entries, []
    if step in ("contest", "cooperate"):
        return cases.contest(state, case), [], []
    if step == "appeal" and case.stage == "ruling":
        return cases.appeal(state, case, rng, balance), [], []
    if step == "comply" and case.stage == "ruling":
        state, logs = cases.comply(state, case, data)
        return state, [], logs
    return state, [], []


def odds_words(lo: float, hi: float) -> str:
    return f"{lo:.0%}-{hi:.0%}"


def event_names(
    state: GameState, data: GameData, balance: Balance, event: GameEvent
) -> dict[str, str]:
    """Placeholders for a regulation event: never a draw or a chance, only shown ranges."""
    rb = balance.regulation
    names = {"regulator": "the regulator", "case": "the investigation", "market": "its market",
             "fine": "a fine", "odds": "", "unit": "the unit"}  # fmt: skip
    if event.template_id == structural.ORDER_EVENT:
        o = order_for(state, event)
        if o is not None:
            reg = rdata.file(data).regulator(o.regulator)
            lo, hi = rb.structural.appeal_win
            names |= {"regulator": reg.name, "unit": o.unit_label, "odds": odds_words(lo, hi)}
        return names
    case = case_for(state, event)
    if case is None:
        return names
    reg = rdata.file(data).regulator(case.regulator)
    names |= {
        "regulator": reg.name,
        "case": CONDUCT_WORDS.get(case.conduct, case.conduct.replace("_", " ")),
        "market": case.market.replace("_", " "),
    }
    if event.template_id == cases.RULING:
        lo, hi = rb.odds.appeal_win
        names |= {"fine": dollars(case.fine_cents), "odds": odds_words(lo, hi)}
    else:
        lo, hi = rb.odds.ruling_against
        flo, fhi = rb.fine.share
        names |= {"odds": odds_words(lo, hi), "fine": f"{flo:.1%}-{fhi:.0%} of turnover"}
    return names
