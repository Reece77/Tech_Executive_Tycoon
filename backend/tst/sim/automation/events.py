"""Routine events (docs/formulas.md 40.5) and press moments (40.6).

A non-critical event whose category an automated area lists, still open when the player presses
Continue, is answered in phase 1 by that area's owner if the area's "Let them answer routine
events" is on. The right rule takes the choice with the best displayed effect (the effects the
event card shows), ties to the more cautious choice; the mistake takes the second best. Press
moments take the measured answer, or the bold one when the area allows bold claims and the
company's displayed revenue has grown for a quarter; the mistake is the bolder answer.
Critical events always go to the player and never resolve here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from itertools import pairwise

from tst.sim.automation import owners
from tst.sim.automation.models import AreaDecision, AreaOwner
from tst.sim.automation.run import automation_draws
from tst.sim.data_models import Balance, GameData
from tst.sim.events.effects import apply_choice
from tst.sim.events.models import EventChoice, GameEvent
from tst.sim.ledger import AccountCode, LedgerEntry, apply_entries
from tst.sim.log import LogItem
from tst.sim.money import Cents
from tst.sim.org.formulas import decision_quality
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_area_decisions

EVENT_SEQ = 10_000  # tunable-exempt: routine events' record numbers, after phase 2's
EVENT_KEY = 5_000  # tunable-exempt: stream-key offset for routine events' quality draws
PRESS = "press"
CASH_SCALE = 1_000_000  # tunable-exempt: $10,000 of a cash effect weighs as one point
MODIFIER_SCALE = 5.0  # tunable-exempt: a 5% modifier weighs as one point
TONE_ORDER = ("deflect", "measured", "bold")  # from cautious to bold
GROWTH_MONTHS = 3  # tunable-exempt: "grown for a quarter"


def owner_for(state: GameState, event: GameEvent, b: Balance) -> AreaOwner | None:
    """The owner who answers this event, or None: the player answers it (40.5)."""
    if event.severity == "critical" or event.status != "open" or not event.choices:
        return None
    if event.company_id != state.player.id:
        return None
    for o in state.owners_of(event.company_id):
        if not o.answer_events or not owners.valid_owner(state, o, b):
            continue
        if event.category in owners.area_def(b, o.area).events:
            return o
    return None


def answered_for_player(state: GameState, b: Balance) -> frozenset[int]:
    """Open events an owner will answer at Continue: they do not block it (40.5)."""
    return frozenset(e.id for e in state.open_events(state.player.id) if owner_for(state, e, b))


def _value(choice: EventChoice) -> float:
    """A choice's displayed effect, in points: what the event card lists."""
    total = 0.0
    for e in choice.effects:
        match e.type:
            case "cash_delta":
                total += e.value / CASH_SCALE
            case "morale_delta" | "brand_delta" | "quality_delta" | "customers_pct":
                total += e.value
            case "relationship_delta":
                total += e.value / 2
            case "modifier":
                total += e.value / MODIFIER_SCALE
    return total


def _caution(choice: EventChoice) -> float:
    return (0.0 if choice.do_nothing else 1.0) + sum(abs(e.value) for e in choice.effects)


def _tone(choice: EventChoice) -> str | None:
    return next((e.stat for e in choice.effects if e.type == "press_step"), None)


def ranked_choices(
    state: GameState, event: GameEvent, owner: AreaOwner, b: Balance
) -> list[EventChoice]:
    """Best first by the right rule (40.5, 40.6)."""
    choices = list(event.choices)
    if event.category == PRESS and any(_tone(c) for c in choices):
        history = state.company(event.company_id).mrr_history[-GROWTH_MONTHS - 1 :]
        growing = len(history) > GROWTH_MONTHS and all(
            later > earlier for earlier, later in pairwise(history)
        )
        want = "bold" if owner.allow_bold and growing else "measured"

        def press_key(c: EventChoice) -> tuple[int, int]:
            tone = _tone(c) or ""
            bolder = TONE_ORDER.index(tone) if tone in TONE_ORDER else -1
            return (0 if tone == want else 1, -bolder)  # the mistake: the bolder answer

        return sorted(choices, key=press_key)
    return sorted(choices, key=lambda c: (-_value(c), _caution(c), c.key))


def answer_routine(
    state: GameState,
    rng: RngFactory,
    b: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Phase 1, before the first-choice rule: owners answer their areas' open events."""
    company = state.player.id
    if not state.owners_of(company):
        return state, (), ()
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    lines: list[AreaDecision] = []
    seq = EVENT_SEQ + sum(
        1 for d in state.area_decisions if d.company_id == company and d.turn == state.turn
    )
    counts: dict[tuple[int, int], int] = {}
    for event in state.open_events(company):
        owner = owner_for(state, event, b)
        if owner is None:
            continue
        index = owners.area_index(b, owner.area)
        key = (owner.person_id, index)
        n = counts.get(key, 0)
        counts[key] = n + 1
        score = owners.true_area_score(state, company, owner.area, owner.person_id, b)
        u = float(automation_draws(rng, state.turn, owner.person_id, EVENT_KEY + index, n).random())
        ranked = ranked_choices(state, event, owner, b)
        right = u < decision_quality(score, b.automation.quality)
        choice = ranked[0] if right or len(ranked) == 1 else ranked[1]
        state, posted, logged = apply_choice(
            state,
            event,
            choice.key,
            b,
            data,
            auto=True,
            balances=apply_entries(balances, entries),
        )
        entries += posted
        logs += [replace(i, in_digest=True) for i in logged]
        mistake = not right and len(ranked) > 1
        lines.append(
            AreaDecision(
                company,
                state.turn,
                seq,
                owner.area,
                owner.person_id,
                "mistake" if mistake else "event",
                f"answered {event.title or event.template_id}: {choice.label}",
                0,
                event.id,
            )
        )
        seq += 1
    return with_area_decisions(state, lines), tuple(entries), tuple(logs)
