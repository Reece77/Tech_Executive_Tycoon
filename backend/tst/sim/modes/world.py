"""World building at any start year (M15b sub-task 2; docs/formulas.md 30.2-30.3): the world
as it stood in a later month, for Sandbox and the historical scenarios.

The world is played from January 2010 to the start month with the player dormant (no product,
no hires, ample cash that is then discarded), so macro, components, eras, incumbents'
listings and the rivals' state are exactly those of a 2010 game on the same seed in that
month. Then the player's company is founded in the start month: a new founder record, the
starting cash and nothing else of the dormant years. The rivals' ledgers are condensed into
one opening entry each, so their balances carry over and the new save stays small."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Final

from tst.sim.calendar import ym_to_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.decisions import Decisions
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, LedgerBalances, LedgerEntry, LedgerLine, apply_entries
from tst.sim.modes.models import ErasOption, GameMode, ModeKind, RivalsOption
from tst.sim.people.founder import FounderSpec, build_founder
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_company, with_employment, with_person

CENTS_A_DOLLAR: Final = 100  # tunable-exempt: cents in a dollar
DORMANT_CASH: Final = 10**15  # tunable-exempt: the dormant player's cash while the world plays
JANUARY: Final = 1  # tunable-exempt: calendar


@dataclass(frozen=True, slots=True)
class ModeSpec:
    """A Sandbox or scenario start (30.2-30.3). `cash_cents` None keeps the scenario's (the
    background's) starting cash."""

    kind: ModeKind
    start_year: int
    cash_cents: int | None = None
    rivals: RivalsOption = "all"
    eras: ErasOption = "historical"
    scenario: str | None = None


def validate(spec: ModeSpec, balance: Balance) -> None:
    """A Sandbox start within what the game offers (30.2); InvalidModeError otherwise."""
    from tst.sim.errors import InvalidModeError

    sb = balance.sandbox
    if spec.kind == "sandbox":
        lo, hi = sb.years
        if not lo <= spec.start_year <= hi:
            raise InvalidModeError(f"a Sandbox starts in {lo}-{hi}, not {spec.start_year}")
        if spec.cash_cents is not None:
            low, high = (d * CENTS_A_DOLLAR for d in sb.cash_dollars)
            if not low <= spec.cash_cents <= high:
                raise InvalidModeError(
                    f"Sandbox cash is ${sb.cash_dollars[0]:,}-${sb.cash_dollars[1]:,}"
                )
    if spec.kind == "campaign":
        raise InvalidModeError("a campaign needs no mode")


def play_world(
    state: GameState,
    balances: LedgerBalances,
    until_turn: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, LedgerBalances]:
    """Advance month by month to `until_turn` with the player dormant and the ledger in
    memory: the same world a 2010 game has in that month."""
    from tst.sim.turn import advance_turn

    player = state.player.id
    balances = dict(balances)
    balances[(player, CASH)] = balances.get((player, CASH), 0) + DORMANT_CASH
    while state.turn < until_turn:
        result = advance_turn(state, Decisions(), rng, balance, data, balances)
        balances = dict(apply_entries(balances, result.ledger_entries))
        state = result.new_state
    return state, balances


def opening_entries(
    state: GameState, balances: LedgerBalances, turn: int
) -> tuple[LedgerEntry, ...]:
    """Each rival's balances as one opening entry (they sum to zero: double entry)."""
    player = state.player.id
    by_company: dict[int, list[LedgerLine]] = defaultdict(list)
    for (cid, account), amount in sorted(balances.items()):
        if cid != player and amount:
            by_company[cid].append(LedgerLine(account, amount))
    return tuple(
        LedgerEntry(turn=turn, company_id=cid, memo="Balances brought forward", lines=tuple(lines))
        for cid, lines in sorted(by_company.items())
        if len(lines) >= 2
    )


def found_player(
    state: GameState,
    founder: FounderSpec,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> GameState:
    """The player's company founded this month: a founder record built now (age and skills
    as chosen), its employment, knowledge and energy from now, and none of the dormant
    years' records."""
    company = state.player
    old = state.founder_of(company.id)
    assert old is not None
    person = build_founder(founder, rng, data, balance, state.turn, person_id=old.id)
    person = replace(person, city=old.city)
    state = with_person(state, person)
    employment = next(e for e in state.employments if e.person_id == old.id)
    state = with_employment(state, replace(employment, start_turn=state.turn))
    reveal = new_reveal_state(
        observer_company_id=company.id,
        person=person,
        turn=state.turn,
        rng=rng,
        data=data,
        balance=balance,
        knows_exactly=True,
    )
    pid = company.id
    state = replace(
        state,
        reveals=tuple(
            reveal if (r.observer_company_id, r.person_id) == (pid, person.id) else r
            for r in state.reveals
        ),
        person_states=tuple(
            PersonState(person_id=person.id, energy=balance.founder.energy_per_month)
            if p.person_id == person.id
            else p
            for p in state.person_states
        ),
        events=tuple(e for e in state.events if e.company_id != pid),
        queued=tuple(q for q in state.queued if q.company_id != pid),
        modifiers=tuple(m for m in state.modifiers if m.company_id != pid),
        press_moments=tuple(m for m in state.press_moments if m.company_id != pid),
        credibility=tuple(c for c in state.credibility if c.company_id != pid),
        feuds=tuple(f for f in state.feuds if f.company_id != pid),
        scores=tuple(s for s in state.scores if s.company_id != pid),
    )
    return with_company(
        state,
        replace(
            company,
            founded_turn=state.turn,
            stage_history=((company.stage, state.turn),),
            mrr_history=(),
            op_history=(),
            burn_history=(),
            insolvent_months=0,
            arr_milestone_cents=0,
        ),
    )


def thin_rivals(state: GameState, option: RivalsOption, balance: Balance) -> GameState:
    """Sandbox's rivals option (30.2): all of them, half (every other company in each
    category, by id, keeping the first), or none. Removed rivals close as a failed rival
    does (15.1): their products retire and their people leave."""
    if option == "all":
        return state
    from tst.sim.finance.insolvency import fail_rival

    alive = [c for c in state.rivals() if c.alive and c.parent_id is None]
    if option == "none":
        gone = alive
    else:
        by_category: dict[str, list[int]] = defaultdict(list)
        for c in sorted(alive, key=lambda c: c.id):
            products = state.company_products(c.id)
            by_category[products[0].category if products else ""].append(c.id)
        keep_every = round(1 / balance.sandbox.rival_share_half)
        removed = {
            cid for ids in by_category.values() for i, cid in enumerate(ids) if i % keep_every
        }
        gone = [c for c in alive if c.id in removed]
    for c in gone:
        state, _ = fail_rival(
            state,
            state.company(c.id),
            balance.hiring.candidate_shelf_turns,
            balance.rivals.free_agent_months,
        )
    return state


def start_mode(
    state: GameState,
    entries: tuple[LedgerEntry, ...],
    spec: ModeSpec,
    founder: FounderSpec,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    """A new game's turn-0 state and entries turned into a Sandbox or scenario start: the
    world played to January of the start year, the company founded then with its cash."""
    validate(spec, balance)
    start_turn = ym_to_turn(spec.start_year, JANUARY)
    player = state.player.id
    starting = [e for e in entries if e.company_id == player]
    cash = spec.cash_cents
    if cash is None:
        cash = sum(ln.amount for e in starting for ln in e.lines if ln.account == CASH)
    world, balances = play_world(state, apply_entries({}, entries), start_turn, rng, balance, data)
    world = found_player(world, founder, rng, balance, data)
    world = thin_rivals(world, spec.rivals, balance)
    extra: tuple[LedgerEntry, ...] = ()
    if spec.kind == "scenario" and spec.scenario is not None:
        from tst.sim.modes.scenarios import apply_start

        world, extra = apply_start(world, spec.scenario, rng, balance, data)
    world = replace(
        world,
        mode=GameMode(
            kind=spec.kind,
            start_turn=start_turn,
            scenario=spec.scenario,
            rivals=spec.rivals,
            eras=spec.eras,
        ),
    )
    opening = list(opening_entries(world, balances, start_turn))
    equity = next((ln.account for e in starting for ln in e.lines if ln.account != CASH), None)
    if cash and equity is not None:
        opening.insert(
            0,
            LedgerEntry.transfer(
                turn=start_turn,
                company_id=player,
                memo="Starting cash",
                debit=CASH,
                credit=equity,
                amount=cash,
            ),
        )
    return world, (*opening, *extra)
