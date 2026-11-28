"""M57r-A sub-task 4 (review 10 items 10-12, ruling 4): currencies against engine prices."""

from __future__ import annotations

from dataclasses import replace

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.fx import phase as fx_phase
from tst.sim.fx import rates, translate
from tst.sim.fx.models import FxHedge, PriceMark
from tst.sim.geo.models import RegionalSegment
from tst.sim.ledger import LedgerEntry
from tst.sim.products import phases
from tst.sim.products.models import Product
from tst.sim.state import GameState, with_product, with_segments

PLAYER = 1
EU = "europe"
LINE = 9301


def _devices_abroad(loaded: LoadedData, turn: int, customers: float) -> GameState:
    state = replace(fresh_game(loaded), turn=turn)
    p = Product(
        id=LINE,
        company_id=PLAYER,
        category="devices",
        name="Phone",
        status="live",
        quality=70.0,
        feature_points=0.0,
        brand=60.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )
    seg = loaded.game_data.category("devices").markets[0].segment
    rows = [RegionalSegment(LINE, EU, seg, 30_000, customers)]
    return with_segments(with_product(state, p), [], rows)


def _revenue_of(entries: tuple[LedgerEntry, ...]) -> int:
    return sum(
        -x.amount
        for e in entries
        if e.memo == "Revenue: Phone"
        for x in e.lines
        if x.account.startswith("4")
    )


def test_fx_month_revenue_is_the_ledgers_for_a_unit_sale_line(loaded: LoadedData) -> None:
    """Fable 6: 50,000 customers at $300 and no production booked $0 while FxMonth showed
    $12.7M a month."""
    b, d = loaded.balance, loaded.game_data
    turn = ym_to_turn(2020, 6)
    seg = d.category("devices").markets[0].segment
    for sold in (0.0, 1_234.0):
        state = _devices_abroad(loaded, turn, 50_000.0)
        prices = translate.fx_prices(translate.update_marks(state, b, d), b, d)
        effects = fx_phase.with_effects(None, prices)
        state = translate.update_marks(state, b, d)
        units = {(LINE, EU, seg): sold}
        state, entries, _, _, _, by_region = phases._revenue(
            state, {}, d, units, None, effects, "north_america"
        )
        state, _ = fx_phase.after_sales(state, b, d, by_region)
        month = next((m for m in state.fx.months if m.region == EU and m.turn == turn), None)
        shown = month.revenue_cents if month is not None else 0  # no sale abroad, no row
        assert shown == _revenue_of(entries)
        assert (shown == 0) == (sold == 0)


def test_engine_priced_lines_re_mark_every_month(loaded: LoadedData) -> None:
    """Fable 19: an ad price recomputed in US cents was translated again when it stayed put."""
    b, d = loaded.balance, loaded.game_data
    turn = ym_to_turn(2020, 6)
    state = replace(fresh_game(loaded), turn=turn)
    p = Product(
        id=LINE,
        company_id=PLAYER,
        category=b.media.social,
        name="Feed",
        status="live",
        quality=70.0,
        feature_points=0.0,
        brand=60.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )
    seg = d.category(b.media.social).markets[0].segment
    state = with_segments(with_product(state, p), [], [RegionalSegment(LINE, EU, seg, 37, 1e6)])
    old = PriceMark(LINE, EU, seg, 37, turn - 30)  # the same price, marked long ago
    state = replace(state, fx=replace(state.fx, marks=(old,)))
    assert rates.index_at(state, EU, turn, b, d) != rates.index_at(state, EU, turn - 30, b, d)
    state = translate.update_marks(state, b, d)
    (mark,) = state.fx.marks
    assert mark.turn == turn
    assert (LINE, EU, seg) not in translate.fx_prices(state, b, d)


def test_several_forwards_settling_together_match_the_ledger(loaded: LoadedData) -> None:
    """Codex R10-14 / Fable 21: three forwards posted 11,543,400 cents and the month kept the
    last one's 3,847,800; a gain and a loss netted into one account."""
    b, d = loaded.balance, loaded.game_data
    turn = ym_to_turn(2023, 6)
    state = replace(fresh_game(loaded), turn=turn)
    spot = rates.index_at(state, EU, turn, b, d)
    hedges = tuple(
        FxHedge(
            id=i,
            company_id=PLAYER,
            region=EU,
            notional_cents=n,
            turn=turn - 3,
            settle_turn=turn,
            spot_index=spot,
            forward_index=fwd,
        )
        for i, (n, fwd) in enumerate(
            [(10_000_000, spot + 500), (20_000_000, spot + 300), (5_000_000, spot - 800)], 1
        )
    )
    state = replace(state, fx=replace(state.fx, hedges=hedges))
    state, entries = fx_phase.after_sales(state, b, d, {})
    gains = -sum(x.amount for e in entries for x in e.lines if x.account == "4940_fx_gains")
    losses = -sum(x.amount for e in entries for x in e.lines if x.account == "4945_fx_losses")
    assert gains > 0 > losses  # posted separately, never netted
    month = next(m for m in state.fx.months if m.region == EU and m.turn == turn)
    # a month with settlements alone has its row, carrying every forward's result
    assert (
        month.hedge_cents
        == gains + losses
        == sum(h.settled_cents for h in state.fx.hedges if h.settle_turn == turn)
    )
    assert all(sum(x.amount for x in e.lines) == 0 for e in entries)


def test_booked_revenue_drives_royalties_and_premiums(loaded: LoadedData) -> None:
    """Fable 17 (ruling 4): a share of revenue is a share of the booked, translated revenue."""
    from tst.sim.media.streaming import monthly_revenue_cents

    b, d = loaded.balance, loaded.game_data
    turn = ym_to_turn(2020, 6)
    state = _devices_abroad(loaded, turn, 1_000.0)
    seg = d.category("devices").markets[0].segment
    old = PriceMark(LINE, EU, seg, 30_000, turn - 60)
    state = replace(state, fx=replace(state.fx, marks=(old,)))
    booked = translate.fx_prices(state, b, d)[(LINE, EU, seg)]
    assert booked != 30_000
    line = state.product(LINE)
    assert line is not None
    assert monthly_revenue_cents(state, line, b, d) == booked * 1_000
