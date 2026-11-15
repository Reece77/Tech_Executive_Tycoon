"""M34 test helpers: a game in 2026+ whose player owns a launched OS and store with a given share
of a region's users (tests/platform_helpers.py's game, with a platform founded in play)."""

from __future__ import annotations

from dataclasses import replace

from tests.platform_helpers import START, platform_state
from tst.loader import LoadedData
from tst.sim.ledger import LedgerBalances
from tst.sim.platforms import data as pdata
from tst.sim.platforms.models import Platform, PlatformRegion
from tst.sim.products.models import Product
from tst.sim.state import GameState, with_product

OS_ID = 990_101
REGION = "europe"


def owner_state(
    loaded: LoadedData,
    users: float = 0.5,
    turn: int = START,
    region: str = REGION,
    mrr_cents: int = 0,
    self_pref: str = "off",
) -> tuple[GameState, LedgerBalances, Platform]:
    """The player owns platform `own_<id>` with `users` of `region`'s device users, and its
    monthly revenue history is `mrr_cents` (the money tests read the trailing year)."""
    state, balances = platform_state(loaded, turn=turn)
    os = Product(
        id=OS_ID, company_id=state.player.id, category="os", name="Test OS", status="live",
        quality=60.0, feature_points=100.0, brand=40.0, marketing_budget_cents=0,
        created_turn=turn - 24, launched_turn=turn - 12,
    )  # fmt: skip
    state = with_product(state, os)
    pid = pdata.next_platform_id(state)
    platform = Platform(
        id=pid, key=f"own_{pid}", name="Test OS", store="Test Store", kind="device",
        owner_id=state.player.id, owner_label=state.player.name,
        regions=tuple(loaded.game_data.region_keys), launched_turn=turn - 12, historical=False,
        product_id=OS_ID, self_pref=self_pref,  # type: ignore[arg-type]
    )  # fmt: skip
    rows = tuple(
        replace(r, users=r.users * (1 - users)) if r.region == region else r
        for r in state.platform_regions
    )
    rows = (*rows, PlatformRegion(pid, region, users=users, dev_share=users, catalogue=12.0))
    state = replace(state, platforms=(*state.platforms, platform), platform_regions=rows)
    if mrr_cents:
        state = replace(state, reg_turnover=((state.player.id, (mrr_cents,) * 12),))
    return state, balances, platform
