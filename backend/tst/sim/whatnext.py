"""What next: the Overview's short list of what to do now (docs/formulas.md 42.3; M29).

Pure and read-only, beside the COO's briefing (`coo.py`, 17.3), which it extends: the most
urgent risk first (a critical event set aside, a covenant in breach, short runway), then
proposals and pitches waiting for the founder, then the briefing's other issues, then
systems that unlocked this month. Uses only what the player can see; no energy.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from tst.sim.coo import Issue, briefing
from tst.sim.data_models import Balance, GameData
from tst.sim.finance.debt import covenants
from tst.sim.money import Cents
from tst.sim.state import GameState
from tst.sim.unlocks import System

MAX_ITEMS = 5  # tunable-exempt: the panel's length, fixed by the spec (42.3)


@dataclass(frozen=True, slots=True)
class Item:
    key: str  # risk_event | risk_covenant | runway | proposal | pitch | <briefing key> | unlock
    text: str
    link_kind: str  # a coo LinkKind, or "proposal", "pitch", "guide"
    link_id: int | None = None
    link_key: str | None = None  # a systems key for "guide"


def _risk(state: GameState, cash: Cents, balance: Balance) -> Item | None:
    cid = state.player.id
    for event in state.open_events(cid):
        if event.severity == "critical" and event.status == "open":
            return Item(
                "risk_event",
                f"A critical decision is waiting: {event.title or 'untitled'}.",
                "event",
                event.id,
            )
    for loan in state.loans:
        if loan.company_id != cid or loan.status != "active":
            continue
        for c in covenants(state, loan, cash, balance):
            if not c.holds:
                return Item(
                    "risk_covenant",
                    f"A loan covenant is in breach: {c.description.lower()}.",
                    "finance",
                )
    return None


def _from_issue(issue: Issue) -> Item:
    return Item(issue.key, issue.text, issue.link_kind, issue.link_id)


def automation_items(state: GameState, balance: Balance) -> list[Item]:
    """Areas whose owner ran out of time or budget last month, else areas the team could run
    (40.3, 40.8): at most one line each."""
    from tst.sim.automation import owners

    cid = state.player.id
    month = [d for d in state.area_decisions if d.company_id == cid and d.turn == state.turn - 1]
    short = sorted(
        {
            owners.area_def(balance, d.area).label
            for d in month
            if d.kind in ("no_time", "over_budget")
        }
    )
    if short:
        return [
            Item(
                "automation_short",
                f"{', '.join(short)} went short last month: change priorities, limits or owners.",
                "automation",
            )
        ]
    if state.player.stage < balance.exec_seats.stage:
        return []
    open_areas = [
        a
        for a in owners.area_keys(balance)
        if state.area_owner(cid, a) is None and owners.eligible_people(state, cid, a, balance)
    ]
    if not open_areas:
        return []
    n = len(open_areas)
    return [
        Item(
            "automation_open",
            f"Your team could run {n} area{'s' if n != 1 else ''} for you: see Automation.",
            "automation",
        )
    ]


def what_next(
    state: GameState,
    cash: Cents,
    balance: Balance,
    data: GameData,
    unlocked_now: Iterable[System] = (),
) -> tuple[Item, ...]:
    """Up to MAX_ITEMS items, most urgent first. `unlocked_now`: systems announced this
    month (the unlock inbox items of the current turn)."""
    cid = state.player.id
    items: list[Item] = []
    risk = _risk(state, cash, balance)
    if risk is not None:
        items.append(risk)
    for p in state.pending_proposals(cid):
        items.append(Item("proposal", f"A proposal waits for your answer: {p.text}", "org"))
    for pitch in state.pending_pitches(cid):
        items.append(Item("pitch", f"A pitch waits for your answer: {pitch.title}.", "org"))
    for issue in briefing(state, cash, balance, data):
        if risk is not None and risk.link_kind == "event" and issue.link_id == risk.link_id:
            continue  # the same event, already first
        items.append(_from_issue(issue))
    items += automation_items(state, balance)  # M27a (40.8; M29 follow-up 4)
    for system in unlocked_now:
        items.append(
            Item(
                "unlock",
                f"{system.label} is open now: see what it does.",
                "guide",
                link_key=system.key,
            )
        )
    return tuple(items[:MAX_ITEMS])
