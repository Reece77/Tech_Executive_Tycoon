"""Being acquired (docs/formulas.md 28.6, M14 sub-task 6): accepting a takeover bid sells
the company, and the game ends with an exit. The sale is recorded as a closed deal (buyer: the
largest rival by revenue, the "larger company" of 25.4's bid) at the bid's premium over the
share price, for every share; the founder's proceeds follow from their stake."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.log import LogItem, inbox_item
from tst.sim.mna.models import Deal
from tst.sim.money import format_money
from tst.sim.state import GameState, public_of, with_deal

EXIT: Final = "exit"


def buyer_of(state: GameState) -> int | None:
    """The bidder: the rival with the highest last monthly revenue (ties: lowest id)."""
    rivals = [c for c in state.rivals() if c.parent_id is None]
    if not rivals:
        return None
    return max(rivals, key=lambda c: (c.mrr_history[-1] if c.mrr_history else 0, -c.id)).id


def sell_company(
    state: GameState, company_id: int, balance: Balance
) -> tuple[GameState, list[LogItem]]:
    """Accept the bid: price = share price x (1 + public.takeover.premium) x every share."""
    public = public_of(state, company_id)
    buyer = buyer_of(state)
    if public is None or buyer is None:
        return state, []
    per_share = round(public.price_cents * (1 + balance.public.takeover.premium))
    shares = fd_shares(state, company_id)
    price = per_share * shares
    deal_id, ids = state.next_ids.take("deal")
    deal = Deal(
        id=deal_id,
        acquirer_id=buyer,
        target_id=company_id,
        price_cents=price,
        cash_share=1.0,
        made_turn=state.turn,
        status="closed",
        resolved_turn=state.turn,
        mode="integrate",
    )
    state = with_deal(replace(state, next_ids=ids), deal)
    founder = state.founder_of(company_id)
    stake = person_shares(state, company_id, founder.id) if founder is not None else 0
    proceeds = stake * per_share
    meta = replace(state.save_meta, game_state=EXIT, ended_turn=state.turn)
    state = replace(state, save_meta=meta)
    log = inbox_item(
        state.turn,
        company_id,
        "exit_sale",
        buyer=state.company(buyer).name,
        price=format_money(price),
        proceeds=format_money(proceeds),
    )
    return state, [log]


def sale_of(state: GameState, company_id: int) -> Deal | None:
    """The closed sale of the player's company, if it was sold."""
    return next(
        (d for d in state.deals if d.target_id == company_id and d.status == "closed"), None
    )
