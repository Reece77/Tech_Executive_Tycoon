"""M31 sub-task 4's property test (docs/formulas.md 44.4): platform-fee postings balance per
entity whatever the fees, users and customers; what in-game owners earn equals what sellers
pay them; and within the player's group the fees are intercompany (5900 / 4300) in equal
amounts, so consolidation removes them."""

from __future__ import annotations

from dataclasses import replace
from functools import cache

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.platform_helpers import START, platform_state
from tst.loader import LoadedData, load_all
from tst.sim.ledger import (
    INTERCOMPANY_PURCHASES,
    INTERCOMPANY_SALES,
    PLATFORM_FEE_REVENUE,
    PLATFORM_FEES,
)
from tst.sim.platforms import fees
from tst.sim.platforms.phase import platforms_month
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


@cache
def _loaded() -> LoadedData:
    from pathlib import Path

    return load_all(Path(__file__).resolve().parents[2] / "data")


@cache
def _start() -> GameState:
    loaded = _loaded()
    state, _ = platform_state(loaded, turn=START)
    return platforms_month(state, RngFactory(3), loaded.balance, loaded.game_data)


def _sum(entries: list, account: str, company: int | None = None) -> int:  # type: ignore[type-arg]
    return sum(
        line.amount
        for e in entries
        for line in e.lines
        if line.account == account and (company is None or e.company_id == company)
    )


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    fee=st.floats(min_value=0.0, max_value=0.5),
    scale=st.floats(min_value=0.0, max_value=5.0),
    users=st.floats(min_value=0.0, max_value=1.0),
)
def test_fee_postings_balance(fee: float, scale: float, users: float) -> None:
    loaded = _loaded()
    state = _start()
    state = replace(
        state,
        platforms=tuple(replace(p, fee=fee) if p.key == "ios" else p for p in state.platforms),
        platform_regions=tuple(
            replace(r, users=users) if r.platform_id == 0 else r for r in state.platform_regions
        ),
        product_segments=tuple(
            replace(s, customers=s.customers * scale) for s in state.product_segments
        ),
    )
    entries = fees.fee_entries(state, loaded.balance, loaded.game_data)
    for e in entries:
        assert sum(line.amount for line in e.lines) == 0
    apple = next(c.id for c in state.companies if c.name == "Apple")
    # M36r (Codex review 7 finding 3): each seller-owner pair's exact month, rounded once
    paid_to_apple = sum(
        c
        for (_pid, owner, _inter), c in fees.pair_fees(
            state, loaded.balance, loaded.game_data
        ).items()
        if owner == apple
    )
    assert -_sum(entries, PLATFORM_FEE_REVENUE, apple) == paid_to_apple
    assert _sum(entries, PLATFORM_FEES) >= paid_to_apple


def test_group_fees_are_intercompany_and_eliminate(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded = _loaded()
    state = _start()
    player = state.player.id
    facebook = next(c for c in state.companies if c.name == "Facebook")
    state = replace(
        state,
        platforms=tuple(
            replace(p, owner_id=player) if p.key == "ios" else p for p in state.platforms
        ),
    )
    monkeypatch.setattr(fees.world, "group", lambda s: (s.player, facebook))
    entries = fees.fee_entries(state, loaded.balance, loaded.game_data)
    bought = _sum(entries, INTERCOMPANY_PURCHASES, facebook.id)
    sold = -_sum(entries, INTERCOMPANY_SALES, player)
    assert bought > 0
    assert bought == sold
    outside = sum(  # M36r: each seller-owner pair's exact month, rounded once
        c
        for (_pid, owner, inter), c in fees.pair_fees(
            state, loaded.balance, loaded.game_data
        ).items()
        if owner == player and not inter
    )
    assert -_sum(entries, PLATFORM_FEE_REVENUE, player) == outside  # apps outside the group
