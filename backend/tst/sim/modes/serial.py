"""Serial founder (M15b addendum 10): after an exit the game goes on. The founder either
founds a new company in the same save, world and month, or retires (the old ending).

Founding again: the founder keeps their stats, reputation (credibility) and network (feuds
with rival CEOs, the people they know); their proceeds from the sale, less what they keep,
become the new company's starting cash, posted like a game start's (serial.background's cap
table and equity account). The sold company becomes a kept brand of its buyer: a rival with
its own books, products and people; the rivals' world is not touched. Every company the
player has run is a Venture, so History, the score and the Hall of Fame show each apart."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidModeError
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.finance.setup import initial_cap_table
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.mna.exit import EXIT, sale_of
from tst.sim.modes.models import Venture
from tst.sim.money import format_money
from tst.sim.people.models import FOUNDER_ROLE, Employment
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    ceo_of,
    credibility_of,
    with_ceo,
    with_company,
    with_credibility,
    with_employment,
    with_feud,
    with_reveal,
)

RETIRED: Final = "retired"


@dataclass(frozen=True, slots=True)
class FoundAgain:
    """After an exit: found a new company, putting the proceeds less `keep_cents` in."""

    actor_id: int
    company_name: str
    keep_cents: int = 0
    kind: Literal["found_again"] = "found_again"


@dataclass(frozen=True, slots=True)
class Retire:
    """After an exit: retire, which ends the game."""

    actor_id: int
    kind: Literal["retire"] = "retire"


CENTS_A_DOLLAR: Final = 100  # tunable-exempt: cents in a dollar
MAX_NAME: Final = 60  # tunable-exempt: the same limit as a new game's company name


def proceeds_cents(state: GameState, company_id: int) -> int:
    """The founder's share of the sale price: price x their shares / all shares (28.6)."""
    sale = sale_of(state, company_id)
    founder = state.founder_of(company_id)
    if sale is None or founder is None:
        return 0
    shares = fd_shares(state, company_id)
    stake = person_shares(state, company_id, founder.id)
    return sale.price_cents * stake // shares if shares else 0


def venture_of(state: GameState, company_id: int) -> Venture | None:
    return next((v for v in state.ventures if v.company_id == company_id), None)


def _close_venture(state: GameState, outcome: str, kept: int = 0) -> GameState:
    """Record the player's current company as a finished venture."""
    company = state.player
    sale = sale_of(state, company.id)
    venture = Venture(
        company_id=company.id,
        name=company.name,
        founded_turn=company.founded_turn,
        ended_turn=state.save_meta.ended_turn or state.turn,
        outcome=outcome,  # type: ignore[arg-type]
        buyer_id=sale.acquirer_id if sale else None,
        price_cents=sale.price_cents if sale else 0,
        proceeds_cents=proceeds_cents(state, company.id),
        kept_cents=kept,
    )
    rest = tuple(v for v in state.ventures if v.company_id != company.id)
    return replace(state, ventures=(*rest, venture))


def retire(state: GameState) -> GameState:
    """Retire after an exit: the game ends as before (28.6), recorded as retired."""
    if state.save_meta.game_state != EXIT:
        raise InvalidModeError("you can retire only after an exit")
    state = _close_venture(state, "exit")
    return replace(state, save_meta=replace(state.save_meta, game_state=RETIRED))


def found_again(
    state: GameState,
    company_name: str,
    keep_cents: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Found a new company after an exit. Returns the state, the starting cash's entry and
    the news."""
    if state.save_meta.game_state != EXIT:
        raise InvalidModeError("you can found a new company only after an exit")
    name = company_name.strip()
    if not name or len(name) > MAX_NAME:
        raise InvalidModeError(f"company name must be 1..{MAX_NAME} characters")
    old = state.player
    proceeds = proceeds_cents(state, old.id)
    cash = proceeds - keep_cents
    minimum = balance.serial.min_cash_dollars * CENTS_A_DOLLAR
    if keep_cents < 0 or cash < minimum:
        raise InvalidModeError(
            f"put at least {format_money(minimum)} of your {format_money(proceeds)} in"
        )
    background = data.scenario(balance.serial.background)
    assert background is not None  # checked at load
    founder = state.founder_of(old.id)
    assert founder is not None
    sale = sale_of(state, old.id)
    assert sale is not None
    state = _close_venture(state, "exit", keep_cents)
    turn = state.turn
    # The sold company: a kept brand of its buyer, delisted, with no board and no founder.
    buyer = state.company(sale.acquirer_id)
    state = with_company(
        state,
        replace(old, is_player=False, parent_id=buyer.id, personality=buyer.personality),
    )
    # The sale settled when the bid was accepted (tst.sim.mna.exit.sell_company), once: the
    # buyer's payment, its investment and goodwill and the acquisition record (M15r).
    state = replace(
        state,
        public_companies=tuple(p for p in state.public_companies if p.company_id != old.id),
        seats=tuple(s for s in state.seats if s.company_id != old.id),
    )
    ceo = ceo_of(state, old.id)  # a CEO serving the listed company goes with the listing
    if ceo is not None:
        state = with_ceo(state, replace(ceo, ended_turn=turn, end_reason="acquired"))
    job = next(e for e in state.staff(old.id) if e.person_id == founder.id)
    state = with_employment(
        state, replace(job, status="ended", end_turn=turn, end_reason="acquired")
    )
    # The new company, its founder and its starting cash.
    cid = max(c.id for c in state.companies) + 1
    state = replace(
        state,
        companies=(
            *state.companies,
            CompanyState(
                id=cid,
                name=name,
                is_player=True,
                stage=0,
                founded_turn=turn,
                stage_history=((0, turn),),
                mission=old.mission,
                hq_city=old.hq_city,
            ),
        ),
    )
    eid, ids = state.next_ids.take("employment")
    state = replace(state, next_ids=ids)
    state = with_employment(
        state,
        Employment(
            id=eid,
            person_id=founder.id,
            company_id=cid,
            role=FOUNDER_ROLE,
            level=job.level,
            salary_cents=0,
            equity_bp=0,
            start_turn=turn,
            end_turn=None,
            status="active",
        ),
    )
    state = with_reveal(
        state,
        new_reveal_state(
            observer_company_id=cid,
            person=founder,
            turn=turn,
            rng=rng,
            data=data,
            balance=balance,
            knows_exactly=True,
        ),
    )
    state = replace(
        state,
        person_states=tuple(
            PersonState(person_id=founder.id, energy=balance.founder.energy_per_month)
            if p.person_id == founder.id
            else p
            for p in state.person_states
        ),
    )
    state = initial_cap_table(state, cid, founder.id, background, rng, balance, data)
    # Reputation and network go with the founder.
    cred = credibility_of(state, old.id)
    if cred is not None:
        state = with_credibility(state, replace(cred, company_id=cid))
    for feud in [f for f in state.feuds if f.company_id == old.id]:
        if feud.rival_id != buyer.id:  # the buyer now owns their old company
            state = with_feud(state, replace(feud, company_id=cid))
    for r in [r for r in state.reveals if r.observer_company_id == old.id]:
        if r.person_id != founder.id:
            state = with_reveal(state, replace(r, observer_company_id=cid))
    state = replace(state, save_meta=replace(state.save_meta, game_state="active", ended_turn=None))
    entry = LedgerEntry.transfer(
        turn=turn,
        company_id=cid,
        memo="Starting cash from your exit",
        debit=CASH,
        credit=background.starting_equity_account,
        amount=cash,
    )
    log = inbox_item(
        turn,
        cid,
        "founded_again",
        name=name,
        old=old.name,
        buyer=buyer.name,
        cash=format_money(cash),
        kept=format_money(keep_cents),
    )
    return state, (entry,), (log,)
