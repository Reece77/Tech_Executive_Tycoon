"""Rivals' deals (docs/formulas.md 28.6, M14 sub-task 6): each quarter an incumbent with
cash above mna.rival_cash_months of costs buys one startup in its categories with
probability mna.rival_rate, at the startup's reservation, if antitrust clears it; the startup
always integrates. The same deal and closing code as the player's (28.6). Draws: stream
`rival_mna` (id 39), keyed by the acquirer's stable rival key."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.mna import antitrust, deals
from tst.sim.mna.integration import can_integrate
from tst.sim.mna.models import Deal
from tst.sim.products.models import SELLING
from tst.sim.rivals.models import INCUMBENT_KEY, stream_key
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_deal

QUARTER = 3  # tunable-exempt: months a quarter


def rival_deals(
    state: GameState,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> GameState:
    """Phase 2, in a quarter's first month: incumbents' startup purchases, agreed now and
    closed in this month's phase 7."""
    if state.turn % QUARTER != 0:
        return state
    mb = balance.mna
    for buyer in state.rivals():
        if buyer.rival_key[:1] != (INCUMBENT_KEY,) or buyer.parent_id is not None:
            continue
        cash = account_balance(balances, buyer.id, CASH)
        if cash <= mb.rival_cash_months * deals.monthly_costs_cents(state, buyer.id, balance, data):
            continue
        gen = rng.stream(state.turn, "rival_mna", *stream_key(buyer.id, buyer.rival_key))
        if float(gen.random()) >= mb.rival_rate:
            continue
        categories = {p.category for p in state.company_products(buyer.id) if p.status in SELLING}
        startups = [
            c
            for c in state.rivals()
            if c.is_startup
            and c.parent_id is None
            and deals.open_deal(state, c.id) is None
            and can_integrate(state, c.id, balance)  # startups always integrate (28.6)
            and any(p.category in categories for p in state.company_products(c.id))
        ]
        if not startups:
            continue
        target = startups[min(int(float(gen.random()) * len(startups)), len(startups) - 1)]
        price = deals.reservation_cents(state, target.id, balances, balance, data)
        if price <= 0 or price > cash:
            continue
        share, _ = antitrust.combined_share(state, buyer.id, target.id, balance, data)
        if share >= balance.antitrust.review:
            continue
        deal_id, ids = state.next_ids.take("deal")
        state = with_deal(
            replace(state, next_ids=ids),
            Deal(
                id=deal_id,
                acquirer_id=buyer.id,
                target_id=target.id,
                price_cents=price,
                cash_share=1.0,
                made_turn=state.turn,
                close_turn=state.turn + 1,
                mode="integrate",
            ),
        )
    return state
