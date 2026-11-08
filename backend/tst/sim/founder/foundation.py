"""The founder's foundation (docs/formulas.md 32.3, M24): created once personal cash reaches
foundation.min_cents, funded by gifts from the personal account, granting foundation.payout
of its endowment each December. A year's grants raise Beloved and, for effect_months, add
their cause's effect."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.founder import personal
from tst.sim.founder.config import CAUSES
from tst.sim.founder.models import Foundation
from tst.sim.founder.persona import raise_trait
from tst.sim.geo.cities import hq_city
from tst.sim.log import LogItem, inbox_item
from tst.sim.state import GameState, foundation_of, life_of, with_foundation, with_life

FIRST_GRANTS_TEMPLATE: Final = "founder_first_grants"
DECEMBER: Final = 11  # tunable-exempt: calendar (turn % 12)
CENTS_A_DOLLAR: Final = 100  # tunable-exempt: cents in a dollar
MAX_NAME: Final = 60  # tunable-exempt: the same limit as a company name
CAUSE_WORDS: Final[dict[str, str]] = {
    "education": "education",
    "climate": "climate",
    "health": "health",
    "local": "local communities",
}


def create(
    state: GameState,
    person_id: int,
    name: str,
    cause: str,
    city: str | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, LogItem]:
    fb = balance.foundation
    if foundation_of(state, person_id) is not None:
        raise InvalidActionError("you already have a foundation")
    if cause not in CAUSES:
        raise InvalidActionError(f"a cause is one of {', '.join(CAUSES)}")
    if personal.cash_cents(state, person_id) < fb.min_cents:
        raise InvalidActionError(
            f"a foundation needs ${fb.min_cents // CENTS_A_DOLLAR:,} of personal cash"
        )
    title = name.strip() or f"The {state.person(person_id).last_name} Foundation"
    if len(title) > MAX_NAME:
        raise InvalidActionError(f"a name is at most {MAX_NAME} characters")
    home = hq_city(state.player, balance)
    if cause == "local":
        city = city or home
        if not data.has_city(city):
            raise InvalidActionError(f"unknown city {city!r}")
    else:
        city = None
    foundation = Foundation(
        person_id=person_id,
        name=title,
        cause=cause,
        created_turn=state.turn,
        city=city,
        region=data.city(home).region,
    )
    state = with_foundation(state, foundation)
    log = inbox_item(
        state.turn,
        state.player.id,
        "foundation_created",
        name=title,
        cause=CAUSE_WORDS[cause],
    )
    return state, log


def give(state: GameState, person_id: int, cents: int) -> tuple[GameState, LogItem]:
    foundation = foundation_of(state, person_id)
    if foundation is None:
        raise InvalidActionError("create a foundation first")
    if cents <= 0:
        raise InvalidActionError("a gift needs a positive amount")
    if cents > personal.cash_cents(state, person_id):
        raise InvalidActionError("the gift is more than your personal cash")
    state = personal.gift(state, person_id, cents)
    state = with_foundation(state, replace(foundation, gifts_cents=foundation.gifts_cents + cents))
    log = inbox_item(
        state.turn, state.player.id, "foundation_gift", name=foundation.name, amount_cents=cents
    )
    return state, log


def beloved_from(grant_cents: int, balance: Balance) -> float:
    """min(cap, k x log10(g / unit)), never negative (32.3)."""
    fb = balance.foundation
    dollars = grant_cents / CENTS_A_DOLLAR
    if dollars <= fb.beloved_unit_dollars:
        return 0.0
    return min(fb.beloved_cap, fb.beloved_k * math.log10(dollars / fb.beloved_unit_dollars))


def grants_month(state: GameState, balance: Balance) -> tuple[GameState, list[LogItem]]:
    """December: each foundation grants foundation.payout of its endowment (32.3)."""
    if state.turn % 12 != DECEMBER:  # tunable-exempt: months a year
        return state, []
    logs: list[LogItem] = []
    for foundation in state.foundations:
        pid = foundation.person_id
        cents = round(personal.endowment_cents(state, pid) * balance.foundation.payout)
        if cents <= 0:
            continue
        state = personal.grant(state, pid, cents)
        state = with_foundation(
            state,
            replace(
                foundation,
                grants_cents=foundation.grants_cents + cents,
                last_grant_cents=cents,
                last_grant_turn=state.turn,
            ),
        )
        if not foundation.grants_cents:  # the first grants: a minor event next month
            from tst.sim.founder.events import queue

            state = queue(state, state.player.id, FIRST_GRANTS_TEMPLATE, state.turn + 1)
        life = life_of(state, pid)
        if life is not None:
            gain = beloved_from(cents, balance)
            life = raise_trait(life, "beloved", gain, "foundation grants", state.turn, balance)
            state = with_life(state, life)
        logs.append(
            inbox_item(
                state.turn,
                state.player.id,
                "foundation_grants",
                name=foundation.name,
                amount_cents=cents,
                cause=CAUSE_WORDS[foundation.cause],
            )
        )
    return state, logs
