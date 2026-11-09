"""Transfer prices (docs/formulas.md 31.6) and the minority complaint.

Each month, for every flow between two companies of the player's group: the buyer's spend on
the good this month (compute: 6300; chips: 5000) is supplied in-group instead. The buyer's
outside purchase is reversed, the seller's cost is `group.supply_cost` of it, and the buyer
pays the seller the transfer price (5900 / 4300; consolidation removes both). Inside 100%-owned
companies this only moves profit; where either side has minorities, a price more than
`group.fairness_band` from market for `group.fairness_months` months running raises a
critical minority complaint: until the price is fair again, the minority-held company pays
`group.complaint_legal` of its revenue a year in legal costs and is valued
`group.complaint_discount` lower."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import GroupRuleError
from tst.sim.events.models import GameEvent
from tst.sim.group import formulas as gf
from tst.sim.group.config import FLOWS, GOODS
from tst.sim.group.models import FULL_STAKE_BP, TransferFlow
from tst.sim.ledger import (
    CASH,
    COGS,
    COMPUTE,
    GENERAL_ADMIN,
    INTERCOMPANY_PURCHASES,
    INTERCOMPANY_SALES,
    LedgerEntry,
    LedgerLine,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.state import (
    GameState,
    group_companies,
    listed_id,
    owner_at,
    with_flow,
    with_queued,
)

GOOD_ACCOUNT: Final = {"compute": COMPUTE, "chips": COGS}
COMPLAINT_TEMPLATE: Final = "minority_complaint"
LINK: Final = "group"


@dataclass(frozen=True, slots=True)
class SetTransferPrice:
    """Set (or start) the price of one flow (31.6): `seller` supplies `good` to `buyer`."""

    actor_id: int
    seller_id: int
    buyer_id: int
    good: str
    price_kind: str  # cost, cost_plus or market
    margin: float | None = None
    kind: Literal["set_transfer_price"] = "set_transfer_price"


def flow_of(state: GameState, seller: int, buyer: int, good: str) -> TransferFlow | None:
    return next(
        (
            f
            for f in state.transfer_flows
            if (f.seller_id, f.buyer_id, f.good) == (seller, buyer, good) and f.ended_turn is None
        ),
        None,
    )


def set_price(state: GameState, action: SetTransferPrice) -> Outcome:
    if action.good not in GOODS:
        raise GroupRuleError(f"a flow is one of {', '.join(GOODS)}")
    if action.price_kind not in FLOWS:
        raise GroupRuleError(f"a transfer price is one of {', '.join(FLOWS)}")
    group = {c.id for c in group_companies(state, listed_id(state))}
    if action.seller_id == action.buyer_id or not {action.seller_id, action.buyer_id} <= group:
        raise GroupRuleError("a flow runs between two companies of your group")
    if action.margin is not None and not 0 <= action.margin <= 1:
        raise GroupRuleError("a cost-plus margin is 0-100%")
    old = flow_of(state, action.seller_id, action.buyer_id, action.good)
    flow = TransferFlow(
        id=old.id if old else 0,
        seller_id=action.seller_id,
        buyer_id=action.buyer_id,
        good=action.good,
        kind=action.price_kind,
        margin=action.margin,
        set_turn=state.turn,
        unfair_months=old.unfair_months if old else 0,
        complaint=old.complaint if old else False,
        complaint_turn=old.complaint_turn if old else None,
        trailing=old.trailing if old else (),
    )
    return Outcome(with_flow(state, flow))


def minority_held(state: GameState, company_id: int) -> bool:
    held = owner_at(state, company_id)
    return held is not None and held.stake_at() < FULL_STAKE_BP


def complaint_against(state: GameState, company_id: int) -> bool:
    """A complaint stands over a flow of this minority-held company (31.6): its value is
    `group.complaint_discount` lower until the price is fair."""
    return any(
        f.complaint and f.ended_turn is None and company_id in (f.seller_id, f.buyer_id)
        for f in state.transfer_flows
    ) and minority_held(state, company_id)


def transfer_month(
    state: GameState,
    spend: Mapping[tuple[int, str], int],
    revenue_year: Mapping[int, int],
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Phase 7 (31.6). `spend` holds (company, account) -> what it spent this month on that
    account; `revenue_year` each company's revenue over the last 12 month ends."""
    gb = balance.group
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    group = (
        {c.id for c in group_companies(state, listed_id(state))} if state.transfer_flows else set()
    )
    turn = state.turn
    for flow in [f for f in state.transfer_flows if f.ended_turn is None]:
        if not {flow.seller_id, flow.buyer_id} <= group:  # one left the group: the flow ends
            state = with_flow(state, replace(flow, ended_turn=turn))
            continue
        account = GOOD_ACCOUNT.get(flow.good)  # M20: materials flows are priced by refining
        market = spend.get((flow.buyer_id, account), 0) if account is not None else 0
        seller, buyer = state.company(flow.seller_id).name, state.company(flow.buyer_id).name
        price = 0
        if market > 0 and account is not None:
            cost = round(exact(gb.supply_cost) * market)
            price = gf.transfer_price_cents(flow.kind, cost, market, balance, flow.margin)
            entries += [
                LedgerEntry(
                    turn,
                    flow.buyer_id,
                    f"{flow.good.capitalize()} supplied by {seller}",
                    (
                        LedgerLine(CASH, market - price),
                        LedgerLine(account, -market),
                        LedgerLine(INTERCOMPANY_PURCHASES, price),
                    ),
                ),
                LedgerEntry(
                    turn,
                    flow.seller_id,
                    f"{flow.good.capitalize()} supplied to {buyer}",
                    (
                        LedgerLine(CASH, price - cost),
                        LedgerLine(INTERCOMPANY_SALES, -price),
                        LedgerLine(COGS, cost),
                    ),
                ),
            ]
        minorities = minority_held(state, flow.seller_id) or minority_held(state, flow.buyer_id)
        unfair = minorities and market > 0 and gf.unfair(price, market, balance)
        months = flow.unfair_months + 1 if unfair else 0
        complaint = flow.complaint
        logs_now: list[LogItem] = []
        if unfair and months >= gb.fairness_months and not complaint:
            complaint = True
            state = _queue_complaint(state, turn + 1)
            logs_now.append(
                inbox_item(
                    turn,
                    state.player.id,
                    "minority_complaint_filed",
                    link_kind=LINK,
                    seller=seller,
                    buyer=buyer,
                )
            )
        elif complaint and not unfair:
            complaint = False
            logs_now.append(
                inbox_item(
                    turn,
                    state.player.id,
                    "minority_complaint_settled",
                    link_kind=LINK,
                    seller=seller,
                    buyer=buyer,
                )
            )
        if complaint:  # the minority-held side pays the lawyers (31.6)
            held = flow.seller_id if minority_held(state, flow.seller_id) else flow.buyer_id
            legal = round(
                exact(gb.complaint_legal) * Fraction(revenue_year.get(held, 0), MONTHS_PER_YEAR)
            )
            if legal > 0:
                entries.append(
                    LedgerEntry.transfer(
                        turn=turn,
                        company_id=held,
                        memo="Legal costs: a minority complaint",
                        debit=GENERAL_ADMIN,
                        credit=CASH,
                        amount=legal,
                    )
                )
        logs += logs_now
        state = with_flow(
            state,
            replace(
                flow,
                unfair_months=months,
                complaint=complaint,
                complaint_turn=(flow.complaint_turn if flow.complaint else turn)
                if complaint
                else None,
                trailing=(*flow.trailing, price)[-MONTHS_PER_YEAR:],
            ),
        )
    return state, tuple(e for e in entries if any(x.amount for x in e.lines)), tuple(logs)


def _queue_complaint(state: GameState, due: int) -> GameState:
    from tst.sim.events.models import QueuedEvent

    qid, ids = state.next_ids.take("queued")
    return with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=state.player.id,
            template_id=COMPLAINT_TEMPLATE,
            due_turn=due,
            source_event_id=None,
        ),
    )


def group_step(state: GameState, event: GameEvent, step: str) -> tuple[GameState, list[LogItem]]:
    """A minority complaint's answer (31.6): move the flows under complaint to market prices
    (the complaint ends at the next month end), or defend them (it stands)."""
    if step == "correct_price":
        for f in state.transfer_flows:
            if f.complaint and f.ended_turn is None:
                state = with_flow(state, replace(f, kind="market", margin=None))
    return state, []


def intra_group_share(state: GameState, revenue_year: int) -> Fraction:
    """The share of group revenue over the year that is intra-group (31.7)."""
    paid = sum(sum(f.trailing) for f in state.transfer_flows if f.ended_turn is None)
    return Fraction(paid, revenue_year) if revenue_year > 0 else Fraction(0)
