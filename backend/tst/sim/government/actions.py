"""The player's government actions (ADR-0014; docs/formulas.md 57.2-57.3). They take effect at
once and spend the actor's energy (`government.energy`). A bid is a one-off of the player's own
(57.2): automating bids is out of scope (a follow-up automation area), so no owner acts on them.

- **PlaceBid** (`bid`): on an announced tender before it closes: a live product in the area, a
  price (`bids.price_floor`-`price_cap` of the tender's value) and a capture team (at most
  `capture_max` staff). A proposal's cost (`cost_bp` of the first year's price, at least
  `min_cost_cents`) posts to 6990 at once. One bid a tender; requirements are checked again at
  the award, so a bid may be placed while clearances are pending.
- **WithdrawBid** (`withdraw`): before the tender closes; the proposal's cost is not refunded.
- **ProtestAward** (`protest`): a lost or disqualified bid, within `protests.window_months` of
  the award (`protests.cost_cents` of legal fees, 6990); the award is held while it is decided.
- **RequestClearance** (`clearance`): staff clearances at a level for employees (each the
  level's investigation price, 6990).
- **SponsorFacilityClearance** (`facility`): a facility clearance for one of the company's
  facilities (`clearances.facility_cost_cents`, 6990).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import GovernmentRuleError, InsufficientCashError
from tst.sim.government import awards, clearances
from tst.sim.government.data import MONTHS, announced, area_of, file, scale
from tst.sim.government.models import Bid
from tst.sim.ledger import BIDS_CLEARANCES, CASH, LedgerBalances, LedgerEntry, account_balance
from tst.sim.log import inbox_item
from tst.sim.money import exact, format_money
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

BP: Final = 10_000  # tunable-exempt: basis points
LEVELS: Final = ("secret", "top_secret")


@dataclass(frozen=True, slots=True)
class PlaceBid:
    actor_id: int
    tender_id: int
    product_id: int
    price_cents: int
    team: tuple[int, ...] = ()
    kind: Literal["place_bid"] = "place_bid"


@dataclass(frozen=True, slots=True)
class WithdrawBid:
    actor_id: int
    tender_id: int
    kind: Literal["withdraw_bid"] = "withdraw_bid"


@dataclass(frozen=True, slots=True)
class ProtestAward:
    actor_id: int
    tender_id: int
    kind: Literal["protest_award"] = "protest_award"


@dataclass(frozen=True, slots=True)
class RequestClearance:
    actor_id: int
    person_ids: tuple[int, ...]
    level: str
    kind: Literal["request_clearance"] = "request_clearance"


@dataclass(frozen=True, slots=True)
class SponsorFacilityClearance:
    actor_id: int
    facility_id: int
    kind: Literal["sponsor_facility_clearance"] = "sponsor_facility_clearance"


type GovernmentAction = (
    PlaceBid | WithdrawBid | ProtestAward | RequestClearance | SponsorFacilityClearance
)
ACTION_TYPES: Final[dict[str, type]] = {
    "place_bid": PlaceBid,
    "withdraw_bid": WithdrawBid,
    "protest_award": ProtestAward,
    "request_clearance": RequestClearance,
    "sponsor_facility_clearance": SponsorFacilityClearance,
}


def _energy(state: GameState, actor_id: int, kind: str, key: str, balance: Balance) -> GameState:
    return spend_energy(state, actor_id, kind, balance, cost=balance.government.energy[key])


def _cash(balances: LedgerBalances, company: int, cents: int) -> None:
    if account_balance(balances, company, CASH) < cents:
        raise InsufficientCashError(f"this needs {format_money(cents)} in cash")


def _cost(turn: int, company: int, memo: str, cents: int) -> LedgerEntry:
    return LedgerEntry.transfer(
        turn=turn, company_id=company, memo=memo, debit=BIDS_CLEARANCES, credit=CASH, amount=cents
    )


def proposal_cents(tender_months: int, price_cents: int, balance: Balance) -> int:
    b = balance.government.bids
    year = exact(price_cents) * min(MONTHS, tender_months) / max(1, tender_months)
    return max(b.min_cost_cents, round(year * b.cost_bp / BP))


def place_bid(
    state: GameState, action: PlaceBid, balance: Balance, data: GameData, balances: LedgerBalances
) -> Outcome:
    company = acting_company(state, action.actor_id)
    b = balance.government.bids
    tender = state.tender(action.tender_id)
    turn = state.turn
    if tender is None or not announced(tender, turn):
        raise GovernmentRuleError("no such tender is open")
    if tender.status != "open" or turn >= tender.close_turn:
        raise GovernmentRuleError("the tender is closed to bids")
    if any(
        x.tender_id == tender.id and x.company_id == company and x.status == "submitted"
        for x in state.gov_bids
    ):
        raise GovernmentRuleError("you have already bid on this tender")
    product = state.product(action.product_id)
    if product is None or product.company_id != company or product.status != "live":
        raise GovernmentRuleError("bid with one of your live products")
    if area_of(product, data) != tender.area:
        raise GovernmentRuleError(
            f"{product.name} does not serve this tender's area ({tender.area})"
        )
    lo = round(exact(tender.value_cents) * exact(b.price_floor))
    hi = round(exact(tender.value_cents) * exact(b.price_cap))
    if not lo <= action.price_cents <= hi:
        raise GovernmentRuleError(
            f"the price must be {format_money(lo)} to {format_money(hi)} over the term"
        )
    team = tuple(dict.fromkeys(action.team))
    if len(team) > b.capture_max:
        raise GovernmentRuleError(f"a capture team has at most {b.capture_max} people")
    staff = {e.person_id for e in state.staff(company)}
    if any(p not in staff for p in team):
        raise GovernmentRuleError("the capture team must be your staff")
    cost = proposal_cents(tender.term_months, action.price_cents, balance)
    _cash(balances, company, cost)
    state = _energy(state, action.actor_id, action.kind, "bid", balance)
    world = state.government_world
    bid = Bid(
        id=world.next_bid,
        tender_id=tender.id,
        company_id=company,
        product_id=product.id,
        price_cents=action.price_cents,
        team=team,
        turn=turn,
    )
    state = replace(
        state,
        gov_bids=(*state.gov_bids, bid),
        government_world=replace(world, next_bid=world.next_bid + 1),
    )
    return Outcome(
        state=state,
        entries=(_cost(turn, company, f"Proposal: {tender.title}", cost),),
        log=(
            inbox_item(
                turn, company, "bid_placed", tender=tender.title, price_cents=action.price_cents
            ),
        ),
    )


def withdraw_bid(state: GameState, action: WithdrawBid, balance: Balance) -> Outcome:
    company = acting_company(state, action.actor_id)
    tender = state.tender(action.tender_id)
    bid = next(
        (
            x
            for x in state.gov_bids
            if x.tender_id == action.tender_id
            and x.company_id == company
            and x.status == "submitted"
        ),
        None,
    )
    if bid is None or tender is None:
        raise GovernmentRuleError("you have no bid on this tender")
    if state.turn >= tender.close_turn:
        raise GovernmentRuleError("bids are closed: it can no longer be withdrawn")
    state = _energy(state, action.actor_id, action.kind, "withdraw", balance)
    state = replace(
        state,
        gov_bids=tuple(
            replace(x, status="withdrawn") if x.id == bid.id else x for x in state.gov_bids
        ),
    )
    return Outcome(state=state)


def protest_award(
    state: GameState,
    action: ProtestAward,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    pb = balance.government.protests
    tender = state.tender(action.tender_id)
    bid = next(
        (
            x
            for x in state.gov_bids
            if x.tender_id == action.tender_id
            and x.company_id == company
            and x.status in ("lost", "disqualified")
        ),
        None,
    )
    if tender is None or bid is None:
        raise GovernmentRuleError("protest an award you bid for and lost")
    if bid.protested or tender.round > 0:
        raise GovernmentRuleError("this award has already been protested")
    if tender.status != "awarded" or state.turn > tender.award_turn + pb.window_months:
        raise GovernmentRuleError("the window for a protest has closed")
    _cash(balances, company, pb.cost_cents)
    state = _energy(state, action.actor_id, action.kind, "protest", balance)
    protest = awards.player_protest(state, tender, company, rng, balance, data)
    state = replace(
        state,
        protests=(*state.protests, protest),
        tenders=tuple(
            replace(t, status="protested", protest_until=protest.until) if t.id == tender.id else t
            for t in state.tenders
        ),
        gov_bids=tuple(replace(x, protested=True) if x.id == bid.id else x for x in state.gov_bids),
    )
    return Outcome(
        state=state,
        entries=(_cost(state.turn, company, f"Bid protest: {tender.title}", pb.cost_cents),),
        log=(
            inbox_item(
                state.turn, company, "protest_filed", tender=tender.title, until=str(protest.until)
            ),
        ),
    )


def request_clearance(
    state: GameState,
    action: RequestClearance,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    if action.level not in LEVELS:
        raise GovernmentRuleError(f"a clearance level is one of {list(LEVELS)}")
    people = tuple(dict.fromkeys(action.person_ids))
    if not people:
        raise GovernmentRuleError("choose at least one employee")
    staff = {e.person_id for e in state.staff(company)}
    for pid in people:
        if pid not in staff:
            raise GovernmentRuleError("clearances are for your own staff")
        held = [
            c
            for c in state.clearances
            if c.person_id == pid and c.company_id == company and c.status in ("pending", "cleared")
        ]
        if any(c.status == "pending" for c in held):
            raise GovernmentRuleError("a clearance is already pending for one of them")
        if any(
            c.level == action.level or c.level == "top_secret"
            for c in held
            if c.status == "cleared"
        ):
            raise GovernmentRuleError("one of them already holds that clearance")
    price = round(exact(file(data).clearances[action.level].cost_cents) * exact(scale(balance)))
    cents = price * len(people)
    _cash(balances, company, cents)
    state = _energy(state, action.actor_id, action.kind, "clearance", balance)
    made = tuple(
        clearances.draw_clearance(state, pid, company, action.level, rng, balance, data)  # type: ignore[arg-type]
        for pid in people
    )
    state = replace(state, clearances=(*state.clearances, *made))
    entries = (
        (_cost(state.turn, company, "Security clearance investigations", cents),)
        if cents > 0
        else ()
    )
    return Outcome(
        state=state,
        entries=entries,
        log=(
            inbox_item(
                state.turn,
                company,
                "clearances_requested",
                people=str(len(people)),
                level=action.level,
            ),
        ),
    )


def sponsor_facility(
    state: GameState,
    action: SponsorFacilityClearance,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    f = state.facility(action.facility_id)
    if f is None or f.company_id != company or f.status == "closed":
        raise GovernmentRuleError("sponsor a clearance for one of your own facilities")
    if any(
        x.facility_id == f.id and x.status in ("pending", "cleared")
        for x in state.facility_clearances
    ):
        raise GovernmentRuleError("the facility is already cleared or pending")
    cents = balance.government.clearances.facility_cost_cents
    _cash(balances, company, cents)
    state = _energy(state, action.actor_id, action.kind, "facility", balance)
    made = clearances.draw_facility(state, f.id, company, rng, data)
    state = replace(state, facility_clearances=(*state.facility_clearances, made))
    return Outcome(
        state=state,
        entries=(_cost(state.turn, company, "Facility clearance", cents),) if cents > 0 else (),
        log=(inbox_item(state.turn, company, "facility_clearance_requested", facility=str(f.id)),),
    )


def apply_government(
    state: GameState,
    action: GovernmentAction,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    if data.government is None:
        raise GovernmentRuleError("this game has no government tenders")
    match action:
        case PlaceBid():
            return place_bid(state, action, balance, data, balances)
        case WithdrawBid():
            return withdraw_bid(state, action, balance)
        case ProtestAward():
            return protest_award(state, action, rng, balance, data, balances)
        case RequestClearance():
            return request_clearance(state, action, rng, balance, data, balances)
        case SponsorFacilityClearance():
            return sponsor_facility(state, action, rng, balance, data, balances)
