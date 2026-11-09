"""The family office and the market index (docs/formulas.md 37.4, M26).

- **The market index** (phase 12, every month): the value-weighted return of every listed
  company (the player's, listed rivals, carve-outs and spin-offs) over the companies listed
  at both month ends, chained from 1.0.
- **Forming** (energy family_office.energy) once personal wealth (cash + investments at
  value, 37.4) reaches family_office.min_cents: a personal company outside the group, with
  an investment manager (a generated finance manager, stream `personal` key (3,)) and a
  mandate.
- **Returns** each month on its balance (9130): `index x r_index + (1 - index) x r_cash +
  alpha x (skill - alpha_mid) + vol x z - fee / 12`, with the mandate's index share and vol,
  r_cash the base rate a month, the manager's true finance skill (hidden), z from stream
  `personal` key (2,). Gains Dr 9130 Cr 9410; losses Dr 9420 Cr 9130.
- **Moving money** (energy family_office.move_energy): personal cash in or out."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.founder import draws
from tst.sim.founder.draws import personal_draws
from tst.sim.founder.investing_models import MANDATES, FamilyOffice, IndexPoint
from tst.sim.founder.models import FAMILY_OFFICE, GAINS, LOSSES, PERSONAL_CASH
from tst.sim.founder.personal import cash_cents
from tst.sim.founder.wealth import family_office_cents, personal_wealth_cents, post
from tst.sim.ledger import LedgerBalances
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    family_office_of,
    with_family_office,
    with_index_point,
    with_person,
    with_reveal,
)

MONTHS_A_YEAR = 12  # tunable-exempt: calendar
PCT = 100  # tunable-exempt: percent
MANAGER_ROLE = "finance_manager"  # tunable-exempt: roles.yaml key of the investment manager
MANAGER_LEVEL = "senior"  # tunable-exempt: an experienced manager
MANAGER_SKILL = "finance"  # tunable-exempt: skills.yaml key that drives the alpha


def index_month(
    state: GameState, balances: LedgerBalances, balance: Balance, data: GameData
) -> GameState:
    """37.4: this month's market index point."""
    from tst.sim.mna.valuation import is_listed, market_cap_cents

    caps: list[tuple[int, int]] = []
    for c in state.companies:
        if not is_listed(state, c.id, data):
            continue
        cap = market_cap_cents(state, c.id, balances, balance, data)
        if cap is not None and cap > 0:
            caps.append((c.id, cap))
    last = state.market_index[-1] if state.market_index else None
    r = 0.0
    if last is not None:
        before = dict(last.caps)
        both = [(cid, cap) for cid, cap in caps if cid in before]
        then = sum(before[cid] for cid, _ in both)
        if then > 0:
            r = float(Fraction(sum(cap for _, cap in both), then)) - 1
    level = (last.level if last is not None else 1.0) * (1 + r)
    point = IndexPoint(state.turn, level, r if last is not None else 0.0, tuple(caps))
    return with_index_point(state, point, balance.family_office.index_months)


def index_return(state: GameState) -> float:
    """This month's index return (0 before two points)."""
    if len(state.market_index) < 2 or state.market_index[-1].turn != state.turn:
        return 0.0
    return state.market_index[-1].month_return


def form(
    state: GameState,
    person_id: int,
    mandate: str,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, LogItem]:
    from tst.sim.people.generator import generate_pool
    from tst.sim.people.reveal import new_reveal_state

    fb = balance.family_office
    if mandate not in MANDATES:
        raise InvalidActionError(f"a mandate is one of {', '.join(MANDATES)}")
    if family_office_of(state, person_id) is not None:
        raise InvalidActionError("you already have a family office")
    wealth = personal_wealth_cents(state, person_id, balances, balance, data)
    if wealth < fb.min_cents:
        raise InvalidActionError(
            f"a family office needs ${fb.min_cents // 100:,} of personal wealth outside your "
            "company"
        )
    gen = personal_draws(rng, state.turn, draws.MANAGER)
    pid, ids = state.next_ids.take("rival_person")
    (manager,) = generate_pool(
        gen,
        data,
        balance,
        state.turn,
        data.role(MANAGER_ROLE),
        [MANAGER_LEVEL],
        first_person_id=pid,
    )
    manager = replace(manager, salary_expectation_cents=None)
    state = replace(with_person(state, manager), next_ids=ids)
    state = with_reveal(
        state,
        new_reveal_state(
            observer_company_id=state.player.id,
            person=manager,
            turn=state.turn,
            rng=rng,
            data=data,
            balance=balance,
        ),
    )
    office = FamilyOffice(person_id, state.turn, manager.id, mandate)  # type: ignore[arg-type]
    state = with_family_office(state, office)
    log = inbox_item(
        state.turn,
        state.player.id,
        "family_office_formed",
        manager=f"{manager.first_name} {manager.last_name}",
        mandate=mandate,
    )
    return state, log


def set_mandate(state: GameState, person_id: int, mandate: str) -> GameState:
    office = family_office_of(state, person_id)
    if office is None:
        raise InvalidActionError("you have no family office")
    if mandate not in MANDATES:
        raise InvalidActionError(f"a mandate is one of {', '.join(MANDATES)}")
    return with_family_office(state, replace(office, mandate=mandate))  # type: ignore[arg-type]


def move(state: GameState, person_id: int, cents: int) -> tuple[GameState, LogItem]:
    """Personal cash into the office (cents > 0) or out of it (cents < 0)."""
    if family_office_of(state, person_id) is None:
        raise InvalidActionError("you have no family office")
    if cents == 0:
        raise InvalidActionError("move a non-zero amount")
    if cents > 0 and cents > cash_cents(state, person_id):
        raise InvalidActionError("not enough personal cash for that")
    if cents < 0 and -cents > family_office_cents(state, person_id):
        raise InvalidActionError("the family office does not hold that much")
    memo = "Into the family office" if cents > 0 else "Out of the family office"
    state = post(state, person_id, memo, "family_office", FAMILY_OFFICE, PERSONAL_CASH, cents)
    log = inbox_item(
        state.turn, state.player.id, "family_office_moved", amount_cents=cents, memo=memo
    )
    return state, log


def monthly_return(
    index_r: float, cash_r: float, skill: float, z: float, mandate: str, balance: Balance
) -> float:
    """37.4: a month's return for a mandate (fees taken)."""
    fb = balance.family_office
    m = fb.mandates[mandate]
    return (
        m.index * index_r
        + (1 - m.index) * cash_r
        + fb.alpha * (skill - fb.alpha_mid)
        + m.vol * z
        - fb.fee / MONTHS_A_YEAR
    )


def office_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Phase 12 (37.4): each family office's month."""
    from tst.sim.finance.macro import base_rate

    for office in state.family_offices:
        held = family_office_cents(state, office.person_id)
        z = float(personal_draws(rng, state.turn, draws.OFFICE).standard_normal())
        skill = state.person(office.manager_id).skills[MANAGER_SKILL]
        cash_r = base_rate(state, data) / PCT / MONTHS_A_YEAR
        r = monthly_return(index_return(state), cash_r, skill, z, office.mandate, balance)
        returns = (*office.returns, (state.turn, r))[-balance.family_office.index_months :]
        state = with_family_office(state, replace(office, returns=returns))
        gain = round(held * r)
        if held <= 0 or not gain:
            continue
        memo = "Family office returns"
        if gain > 0:
            state = post(state, office.person_id, memo, "family_office", FAMILY_OFFICE, GAINS, gain)
        else:
            state = post(
                state, office.person_id, memo, "family_office", LOSSES, FAMILY_OFFICE, -gain
            )
    return state, []
