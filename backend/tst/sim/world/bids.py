"""Bids for the player (docs/formulas.md 41.4).

From 2026, while the player's group is listed and no bid is open, each incumbent no one owns
values the group at its displayed fundamental value (V_f, the value the share price trades
around: 25.3, 28.1) x (1 + its personality's `bids.tilt` + `bids.view_sd` x a standard normal),
drawn each month (stream world, key (3, *rival_key, 1)) and never stored or shown (41.9). When
the market cap is under `bid_discount` x that view and the rival holds `bids.fund` x the price
in cash, it bids with chance `bids.monthly` a month, at most once a year per rival: the share
price x (1 + `bids.premium`). The bid arrives as 25.4's critical takeover event the next month;
the player's answers and the board's response are 28.6's, and accepting sells to this rival at
its bid (tst.sim.mna.exit). An unanswered bid lapses after `BID_MONTHS`. A private player gets
no bids (only friendly offers would come, and M28 adds none; 41.4).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.finance.captable import fd_shares
from tst.sim.ledger import CASH, AccountCode, account_balance
from tst.sim.markets_public import ipo
from tst.sim.markets_public.public import TAKEOVER
from tst.sim.money import Cents
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, listed_id, public_of
from tst.sim.world import draws
from tst.sim.world.groups import is_incumbent, unowned
from tst.sim.world.models import WorldBid
from tst.sim.world.news import Item

MONTHS: Final = 12  # tunable-exempt: "at most once a year per rival"
BID_MONTHS: Final = 3  # tunable-exempt: an unanswered bid lapses after this many months


def rival_draws(state: GameState, rival_id: int, rng: RngFactory) -> tuple[float, float]:
    """A rival's month: its view's standard normal, then the uniform for bidding."""
    rival = state.company(rival_id)
    gen = draws.gen(rng, state.turn, draws.DEALS, *rival.rival_key, draws.BID_TAG)
    return float(gen.standard_normal()), float(gen.random())


def rival_view_cents(
    state: GameState, rival_id: int, value_cents: int, z: float, balance: Balance
) -> float:
    """A rival's hidden view of the player's group's value this month (41.4, 41.9)."""
    bb = balance.world.bids
    tilt = bb.tilt.get(state.company(rival_id).personality or "", 0.0)
    return value_cents * (1 + tilt + bb.view_sd * z)


def bids_month(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, list[Item]]:
    wb = balance.world
    turn = state.turn
    lapsed = tuple(
        replace(b, status="lapsed") if b.status == "open" and turn - b.turn >= BID_MONTHS else b
        for b in state.world_bids
    )
    state = replace(state, world_bids=lapsed)
    if state.ended or any(b.status == "open" for b in state.world_bids):
        return state, []
    lid = listed_id(state)
    public = public_of(state, lid)
    if public is None or public.value_cents <= 0:
        return state, []
    shares = fd_shares(state, lid)  # V_f is a fully diluted value (25.3), as the sale's price
    cap = public.price_cents * shares
    per_share = round(public.price_cents * (1 + wb.bids.premium))
    price = per_share * shares
    recent = {b.rival_id for b in state.world_bids if turn - b.turn < MONTHS}
    for rival in sorted(state.rivals(), key=lambda c: c.id):
        if not is_incumbent(rival) or rival.id in recent or not unowned(state, rival.id):
            continue
        z, u = rival_draws(state, rival.id, rng)
        view = rival_view_cents(state, rival.id, public.value_cents, z, balance)
        if cap >= wb.bid_discount * view:
            continue
        if account_balance(balances, rival.id, CASH) < wb.bids.fund * price:
            continue
        if u >= wb.bids.monthly:
            continue
        bid_id = max((b.id for b in state.world_bids), default=0) + 1
        state = replace(
            state, world_bids=(*state.world_bids, WorldBid(bid_id, rival.id, turn, per_share))
        )
        state = ipo.queue_public(state, lid, TAKEOVER, turn + 1)
        return state, [
            Item(
                "bid",
                f"{rival.name} makes an unsolicited approach for {state.company(lid).name}",
                rival.id,
                lid,
            )
        ]
    return state, []
