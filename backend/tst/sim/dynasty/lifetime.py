"""The founder's lifetime (docs/formulas.md 52.4; M37). Each January from dynasty.start_year the
player's founder (the family head) aged at least `dynasty.mortality.from_age` may die:

    q = by_age(age) x wealth x stress_factor x family_factor

`by_age` the latest life-table entry at or below the age; `stress_factor` linear from
stress[0] at stress 0 to stress[1] at 100; `family_factor` linear from 1 with no family time to
`family_time` at family.max_time. One uniform from stream `dynasty`, key (MORTALITY, person id,
year). The chance and the draw never leave the engine (52.6): the API and prompts see a death
only once it has happened.

**With a family** the estate pays its tax at once (45.6) and the readiest heir (45.5's ranking)
takes over at once; with no heir ready, the eldest living child, else the partner, becomes the
family's head and the board appoints a professional CEO (45.5's family-head mode). **Without a
family** (or with no one left in it) the game ends: `founder_died`, with the campaign summary.
A founder without a family may also retire in dynasty years (`RetireFounder`): the game ends,
`founder_retired`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.dynasty.draws import MORTALITY, gen
from tst.sim.dynasty.mode import in_dynasty_years
from tst.sim.dynasty.models import Death, DynastyState
from tst.sim.errors import InvalidActionError
from tst.sim.family import rules, succession
from tst.sim.family.models import CHILD, PARTNER
from tst.sim.finance.models import GameOutcome
from tst.sim.ledger import LedgerBalances
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, life_of

JANUARY = 1  # tunable-exempt: calendar month
STRESS_SCALE = 100.0  # tunable-exempt: stress is 0-100


@dataclass(frozen=True, slots=True)
class RetireFounder:
    """Dynasty years without a family: the founder retires and the game ends (52.4)."""

    actor_id: int
    kind: Literal["retire_founder"] = "retire_founder"


def death_chance(state: GameState, person_id: int, balance: Balance) -> float:
    """52.4's annual chance for the person this January (engine only)."""
    m = balance.dynasty.mortality
    person = state.person(person_id)
    q = m.base(person.age(state.turn))
    if not q:
        return 0.0
    life = life_of(state, person_id)
    stress = life.stress if life is not None else STRESS_SCALE / 2
    q *= m.wealth * m.stress.at(max(0.0, min(1.0, stress / STRESS_SCALE)))
    family = state.family
    if family is not None and family.head_id == person_id:
        share = family.family_time / balance.family.max_time
        q *= 1 - (1 - m.family_time) * max(0.0, min(1.0, share))
    return min(1.0, q)


def _record(state: GameState, death: Death) -> GameState:
    d = state.dynasty if state.dynasty is not None else DynastyState()
    return replace(state, dynasty=replace(d, deaths=(*d.deaths, death)))


def _successor(state: GameState, balance: Balance) -> tuple[int | None, bool]:
    """(who takes over, ready): the readiest eligible heir, else the eldest living child,
    else the partner; None when no one is left."""
    heirs = rules.eligible_heirs(state, balance, "not_ready")
    if heirs:
        return heirs[0], True
    dead = {x.person_id for x in (state.dynasty.deaths if state.dynasty else ())}
    for relation in (CHILD, PARTNER):
        people = [
            m.person_id
            for m in state.family_members
            if m.relation == relation and m.person_id not in dead
        ]
        if people:
            return min(people, key=lambda pid: state.person(pid).birth_turn), False
    return None, False


def _end(state: GameState, outcome: GameOutcome) -> GameState:
    meta = replace(state.save_meta, game_state=outcome, ended_turn=state.turn)
    return replace(state, save_meta=meta)


def lifetime_month(
    state: GameState,
    rng: RngFactory,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    """Each January from 2040: the founder's mortality draw and what follows a death."""
    if not in_dynasty_years(state, balance) or turn_to_ym(state.turn)[1] != JANUARY:
        return state, []
    if state.ended:
        return state, []
    founder = state.founder_of(state.player.id)
    if founder is None:
        return state, []
    chance = death_chance(state, founder.id, balance)
    if not chance:
        return state, []
    year = turn_to_ym(state.turn)[0]
    if float(gen(rng, state.turn, MORTALITY, founder.id, year).random()) >= chance:
        return state, []
    age = founder.age(state.turn)
    name = rules.full_name(founder)
    company = state.player.name
    state = _record(state, Death(founder.id, state.turn, age, "head", name))
    heir, ready = _successor(state, balance) if state.family is not None else (None, False)
    if heir is None:
        log = inbox_item(
            state.turn,
            state.player.id,
            "founder_died_no_family",
            name=name,
            age=age,
            company=company,
        )
        return _end(state, "founder_died"), [log]
    logs = [
        inbox_item(state.turn, state.player.id, "founder_died", name=name, age=age, company=company)
    ]
    state, more = succession.hand_to_heir(state, heir, "death", rng, balances, balance, data)
    logs += more
    if not ready:  # no heir ready: the board appoints a professional CEO (45.5)
        state, more = succession.appoint_professional(state, None, "death", rng, balance, data)
        logs += more
    return state, logs


def retire_founder(state: GameState, balance: Balance) -> GameState:
    if not in_dynasty_years(state, balance):
        raise InvalidActionError("a founder can retire this way only from 2040")
    if state.family is not None:
        raise InvalidActionError("with a family, step back through a succession instead")
    return _end(state, "founder_retired")
