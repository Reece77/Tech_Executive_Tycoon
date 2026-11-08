"""Being acquired (docs/formulas.md 28.6, M14 sub-task 6): accepting a takeover bid sells
the company, and the game ends with an exit. The sale is recorded as a closed deal (buyer: the
largest rival by revenue, the "larger company" of 25.4's bid) at the bid's premium over the
share price, for every share; the founder's proceeds follow from their stake."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.ledger import CASH, LedgerBalances, LedgerEntry, account_balance
from tst.sim.log import LogItem, inbox_item
from tst.sim.mna.models import Deal
from tst.sim.money import exact, format_money
from tst.sim.state import GameState, public_of, with_acquisition

EXIT: Final = "exit"


def buyer_of(state: GameState) -> int | None:
    """The bidder: the rival with the highest last monthly revenue (ties: lowest id)."""
    rivals = [c for c in state.rivals() if c.parent_id is None]
    if not rivals:
        return None
    return max(rivals, key=lambda c: (c.mrr_history[-1] if c.mrr_history else 0, -c.id)).id


def sell_company(
    state: GameState,
    company_id: int,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Accept the bid: price = share price x (1 + public.takeover.premium) x every share.

    A share sale settles once, at acceptance, through the brand-closing path (M15r, Codex
    review 4 finding 1): the buyer pays the price from its cash, holds the company's book
    equity in 1810 and the rest as goodwill, and the acquisition is recorded; the sold
    company's own books are untouched. A buyer without the cash is refused: the sale falls
    through and the game goes on. The company becomes the buyer's brand when the founder
    founds again (tst.sim.modes.serial)."""
    from tst.sim.mna import deals
    from tst.sim.mna.closing import settle

    public = public_of(state, company_id)
    buyer = buyer_of(state)
    if public is None or buyer is None:
        return state, [], []
    per_share = round(public.price_cents * (1 + exact(balance.public.takeover.premium)))
    shares = fd_shares(state, company_id)
    price = per_share * shares
    buyer_name = state.company(buyer).name
    if account_balance(balances, buyer, CASH) < price:
        log = deals._update(
            state,
            company_id,
            "The sale fell through",
            f"{buyer_name} could not raise {format_money(price)} in cash; the company is still "
            "yours.",
            buyer,
        )
        return state, [], [log]
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
        mode="brand",
    )
    state, entries, acquisition = settle(
        replace(state, next_ids=ids), deal, (), balances, balance, data
    )
    founder = state.founder_of(company_id)
    staff = [e.person_id for e in state.staff(company_id)]
    acquisition = replace(
        acquisition,
        key_people=len(staff),
        person_ids=tuple(p for p in staff if founder is None or p != founder.id),
    )
    state = with_acquisition(state, acquisition)
    stake = person_shares(state, company_id, founder.id) if founder is not None else 0
    proceeds = stake * per_share
    meta = replace(state.save_meta, game_state=EXIT, ended_turn=state.turn)
    state = replace(state, save_meta=meta)
    log = inbox_item(
        state.turn,
        company_id,
        "exit_sale",
        buyer=buyer_name,
        price=format_money(price),
        proceeds=format_money(proceeds),
    )
    return state, entries, [log]


def sale_of(state: GameState, company_id: int) -> Deal | None:
    """The closed sale of the player's company, if it was sold."""
    return next(
        (d for d in state.deals if d.target_id == company_id and d.status == "closed"), None
    )
