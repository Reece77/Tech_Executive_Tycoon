"""Rivals age (docs/formulas.md 52.3; M37). Each January from dynasty.start_year:

**Leaders.** Every rival in business with people has a leader: its CEO as 29.4 names them
(`tst.sim.press.names.rival_ceo_id`), or the successor recorded here. The leader retires with
chance `retire_rate x (age - retire_age + 1)` (0 below retire_age), plus `loss_rate` while the
rival lost money over its last 12 months, from one uniform on stream `dynasty`, key (LEADER,
*rival key, year). The successor is an heir (the leader's surname), an insider (the next in
leadership) or an outside hire, by `successor`'s shares; an heir or an outsider is a new person
at exec level, generated on the same stream. With chance `personality_change[how]` the rival's
personality type (15) changes to another from rivals.startup.personalities.

**Entrants.** A category with fewer than `min_active` active rivals (rivals in business with a
live product in it, the player's group not counted) gets seeded entrants (stream `dynasty`, key
(ENTRANT, category index, year, k)), as many as it takes: a 15.4 startup with entrant_staff
people (all senior) and entrant_cash_months of their pay, launched at once at the category's
median rival quality, so the market never empties. With chance relaunch_share, and a failed rival in the category, it
carries that rival's brand (its name, "II" added): the brand bought and relaunched.

Before 2040 nothing here runs: no draw, no record (52.5 target 1). Draws stay in the engine;
the API shows a succession or an entrant once it happens (52.6).
"""

from __future__ import annotations

import statistics
from dataclasses import replace

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.dynasty.draws import ENTRANT, LEADER, gen
from tst.sim.dynasty.mode import in_dynasty_years
from tst.sim.dynasty.models import DynastyState, LeaderChange, Relaunch, SuccessorKind
from tst.sim.ledger import LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.press.names import rival_ceo_id
from tst.sim.rivals.models import RivalMove, stream_key
from tst.sim.rivals.setup import hire_key_people, key_people_split, market_salary_cents
from tst.sim.rivals.startups import ENTRANT_LEVEL, _mix, _record, found_company, sell_first_in
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    group_companies,
    with_company,
    with_employment,
    with_person,
    with_product,
)

JANUARY = 1  # tunable-exempt: calendar month
EXEC = "exec"  # tunable-exempt: a leader's level
DYNASTY_KEY = 3  # tunable-exempt: rival_key tag of a dynasty-years entrant (after 0, 1, 2)
LIVE = ("live", "sunset")
LOSS_MONTHS = 12  # tunable-exempt: "the last 12 months" (52.3's performance)
HOWS: tuple[SuccessorKind, ...] = ("heir", "insider", "outside")
SECOND = " II"  # tunable-exempt: a relaunched brand's mark


def _record_state(state: GameState) -> DynastyState:
    return state.dynasty if state.dynasty is not None else DynastyState()


def leader_of(state: GameState, company_id: int) -> int | None:
    """A rival's leader: 29.4's CEO, the latest successor recorded here first."""
    return rival_ceo_id(state, company_id)


def _lost_money(company: CompanyState) -> bool:
    recent = company.op_history[-LOSS_MONTHS:]
    return bool(recent) and sum(recent) < 0


def retire_chance(age: int, lost: bool, balance: Balance) -> float:
    r = balance.dynasty.rivals
    chance = r.retire_rate * max(0, age - r.retire_age + 1)
    return min(1.0, chance + (r.loss_rate if lost else 0.0))


def _pick(u: float, shares: dict[str, float]) -> SuccessorKind:
    acc = 0.0
    for how in HOWS:
        acc += shares[how]
        if u < acc:
            return how
    return HOWS[-1]


def _player_group(state: GameState) -> set[int]:
    return {c.id for c in group_companies(state, state.player.id)}


def _hire_leader(
    state: GameState,
    company: CompanyState,
    role: str,
    surname: str | None,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    year: int,
) -> tuple[GameState, int]:
    key = stream_key(company.id, company.rival_key)
    function = next((f for f, r in balance.rivals.function_roles.items() if r == role), "builder")
    before = {p.id for p in state.people}
    state = hire_key_people(
        state,
        company,
        [function],
        rng,
        balance,
        data,
        stream_part=0,
        levels=[EXEC],
        gen=gen(rng, state.turn, LEADER, *key, year, 1),
    )
    new = max(p.id for p in state.people if p.id not in before)
    if surname is not None:
        state = with_person(state, replace(state.person(new), last_name=surname))
    return state, new


def leaders_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Each January from 2040: rival leaders' retirements and successors (module docstring)."""
    if not in_dynasty_years(state, balance) or turn_to_ym(state.turn)[1] != JANUARY:
        return state, ()
    r = balance.dynasty.rivals
    year = turn_to_ym(state.turn)[0]
    mine = _player_group(state)
    logs: list[LogItem] = []
    for company in sorted(state.rivals(), key=lambda c: c.id):
        if company.id in mine:
            continue
        old = leader_of(state, company.id)
        if old is None:
            continue
        person = state.person(old)
        draws = gen(rng, state.turn, LEADER, *stream_key(company.id, company.rival_key), year)
        u, v, w, x = (float(t) for t in draws.random(4))  # tunable-exempt: four draws
        age = person.age(state.turn)
        if u >= retire_chance(age, _lost_money(company), balance):
            continue
        how = _pick(v, r.successor)
        job = state.employment_of(old)
        assert job is not None
        state = with_employment(
            state, replace(job, status="ended", end_turn=state.turn, end_reason="retired")
        )
        if how == "insider":
            staff = [
                e for e in state.staff(company.id) if e.status == "active" and e.person_id != old
            ]
            if staff:
                best = max(
                    staff,
                    key=lambda e: (state.person(e.person_id).skills["leadership"], -e.person_id),
                )
                state = with_employment(state, replace(best, level=EXEC))
                new = best.person_id
            else:
                how = "outside"
        if how != "insider":
            surname = person.last_name if how == "heir" else None
            state, new = _hire_leader(state, company, job.role, surname, rng, balance, data, year)
        before = company.personality
        after = before
        if before is not None and w < r.personality_change[how]:
            others = [p for p in balance.rivals.startup.personalities if p != before]
            if others:
                after = others[min(len(others) - 1, int(x * len(others)))]
                state = with_company(state, replace(state.company(company.id), personality=after))
        p = state.person(new)
        old_name = f"{person.first_name} {person.last_name}"
        new_name = f"{p.first_name} {p.last_name}"
        change = LeaderChange(
            company.id, state.turn, old, new, how, age, old_name, new_name, before, after
        )
        d = _record_state(state)
        state = replace(state, dynasty=replace(d, leader_changes=(*d.leader_changes, change)))
        logs.append(
            inbox_item(
                state.turn,
                state.player.id,
                "rival_succession",
                link_kind="rival",
                link_id=company.id,
                rival=company.name,
                old=old_name,
                new=new_name,
                how={"heir": "an heir", "insider": "an insider", "outside": "an outside hire"}[how],
            )
        )
    return state, tuple(logs)


def active_rivals(state: GameState, category: str, mine: set[int]) -> int:
    live = {
        p.company_id
        for p in state.products
        if p.category == category and p.status in LIVE and p.company_id not in mine
    }
    return sum(1 for c in state.rivals() if c.id in live)


def entrants_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[RivalMove, ...]]:
    """Each January from 2040: a seeded entrant in each category short of rivals."""
    if not in_dynasty_years(state, balance) or turn_to_ym(state.turn)[1] != JANUARY:
        return state, (), ()
    r = balance.dynasty.rivals
    year = turn_to_ym(state.turn)[0]
    mine = _player_group(state)
    entries: list[LedgerEntry] = []
    moves: list[RivalMove] = []
    for index, category in enumerate(data.categories):
        if not category.markets:
            continue
        for k in range(r.min_active):  # as many as it takes to reach min_active
            if active_rivals(state, category.key, mine) >= r.min_active:
                break
            g = gen(rng, state.turn, ENTRANT, index, year, k)
            draws = g.random(5)  # tunable-exempt: five draws
            u_relaunch, u_name, u_pers, u_staff, u_cash = (float(t) for t in draws)
            failed = sorted(
                (
                    c
                    for c in state.companies
                    if c.failed_turn is not None
                    and not c.is_player
                    and any(
                        p.company_id == c.id and p.category == category.key for p in state.products
                    )
                ),
                key=lambda c: c.id,
            )
            taken = {c.name for c in state.companies}
            brand: CompanyState | None = None
            if failed and u_relaunch < r.relaunch_share:
                brand = failed[min(len(failed) - 1, int(u_name * len(failed)))]
                name = brand.name + SECOND
                while name in taken:
                    name += "I"
            else:
                names = [n for n in data.startup_names if n not in taken]
                if not names:
                    break
                name = names[min(len(names) - 1, int(u_name * len(names)))]
            people = balance.rivals.startup.personalities
            personality = people[min(len(people) - 1, int(u_pers * len(people)))]
            lo, hi = r.entrant_staff
            staff = lo + min(hi - lo, int(u_staff * (hi - lo + 1)))
            role = balance.rivals.function_roles["builder"]
            pay = market_salary_cents(role, ENTRANT_LEVEL, balance, data)
            cash = round(pay * staff * r.entrant_cash_months.at(u_cash))
            functions = ["builder", *key_people_split(staff - 1, _mix(category.key, balance))]
            state, company, entry = found_company(
                state,
                name,
                personality,
                category,
                list(category.segment_keys),
                cash,
                functions,
                [ENTRANT_LEVEL] * staff,
                rng,
                balance,
                data,
                gen=g,
                rival_key=(DYNASTY_KEY, index, year, k),
            )
            entries.append(entry)
            product = state.company_products(company.id)[0]
            rivals_q = [
                p.quality
                for p in state.products
                if p.category == category.key and p.status in LIVE and p.company_id not in mine
            ]
            quality = statistics.median(rivals_q) if rivals_q else product.quality
            state = with_product(
                state,
                replace(
                    product,
                    status="live",
                    quality=quality,
                    feature_points=max(product.feature_points, category.features_at_start),
                    launched_turn=state.turn,
                ),
            )
            state = sell_first_in(state, company, product.id, "north_america", balance, data)
            if brand is not None:
                d = _record_state(state)
                relaunch = Relaunch(company.id, brand.id, state.turn)
                state = replace(state, dynasty=replace(d, relaunches=(*d.relaunches, relaunch)))
            what = f"relaunched {brand.name}'s brand in" if brand else "entered"
            state, move = _record(state, company, "founded", f"{what} {category.label}", product.id)
            moves.append(move)
    return state, tuple(entries), tuple(moves)
