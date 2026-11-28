"""M54 sub-task 2 (formulas.md 64.4, ADR-0025): rate indexes, the walk, translation and forwards."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.fx import hedges, rates, translate
from tst.sim.fx.config import INDEX_SCALE
from tst.sim.fx.models import FxHedge
from tst.sim.geo.models import RegionalSegment
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_product, with_segments

PLAYER = 1
EU = "europe"


def _line(state: GameState, pid: int, price: int, customers: float) -> GameState:
    p = Product(
        id=pid,
        company_id=PLAYER,
        category="b2b_saas",
        name=f"L{pid}",
        status="live",
        quality=60.0,
        feature_points=0.0,
        brand=50.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )
    return with_segments(
        with_product(state, p),
        [ProductSegment(pid, "smb", price, customers)],
        [RegionalSegment(pid, EU, "smb", price, customers)],
    )


def test_history_index_is_exact_and_based_in_january_2010(loaded: LoadedData) -> None:
    f = loaded.game_data.fx
    assert f is not None
    assert all(f.history_index(r, 0) == INDEX_SCALE for r in f.index)
    # Europe in December 2015: 0.80 x EUR + 0.16 x GBP + 0.04 x CHF against January 2010
    eu = f.history_index(EU, ym_to_turn(2015, 12))
    assert 800_000 < eu < 860_000
    # Latin America about halves by 2025 (the real's slide)
    assert f.history_index("latin_america", ym_to_turn(2025, 12)) < 520_000
    # a 2008 game reads 2008's months (negative turns)
    assert f.history_index(EU, ym_to_turn(2008, 7)) > INDEX_SCALE


def test_walk_is_seeded_and_drawn_month_by_month(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    start = b.fx.start_turn
    base = replace(fresh_game(loaded), turn=start)
    outs = []
    for seed in (7, 7, 8):
        s = base
        for t in range(start, start + 24):
            s = rates.walk_month(replace(s, turn=t), RngFactory(seed), b, d)
        outs.append(s.fx.walk)
    assert outs[0] == outs[1] != outs[2]
    walk = dict(outs[0])
    assert all(len(w) == 24 for w in walk.values())
    assert "north_america" not in walk
    # this month exists, the next does not
    s = replace(base, fx=replace(base.fx, walk=outs[0]), turn=start + 23)
    assert rates.index_at(s, EU, start + 23, b, d) == walk[EU][23]


def test_translation_rounds_half_even_and_is_identity_at_home(loaded: LoadedData) -> None:
    assert translate.translated(1000, 845_099, 1_000_000) == 845
    assert translate.translated(5, 1_100_000, 1_000_000) == 6  # 5.5 -> 6 (even)
    assert translate.translated(7, 1_500_000, 1_000_000) == 10  # 10.5 -> 10 (even)
    assert translate.translated(1234, 999_999, 999_999) == 1234


def test_marks_and_translated_prices(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _line(replace(fresh_game(loaded), turn=0), 9001, 10_000, 100.0)
    state = translate.update_marks(state, b, d)
    marks = {(m.product_id, m.region) for m in state.fx.marks}
    assert (9001, EU) in marks and (9001, "north_america") not in marks
    later = replace(state, turn=ym_to_turn(2015, 6))
    prices = translate.fx_prices(later, b, d)
    eu = rates.index_at(later, EU, later.turn, b, d)
    assert prices[(9001, EU, "smb")] == translate.translated(10_000, eu, INDEX_SCALE)
    # a new price is marked at this month's index: nothing to translate yet
    rs = replace(later.regional_segments_of(9001)[0], price_cents=12_000)
    later = translate.update_marks(with_segments(later, [], [rs]), b, d)
    assert (9001, EU, "smb") not in translate.fx_prices(later, b, d)


def test_rivals_translate_only_from_applies_from(loaded: LoadedData) -> None:
    b = loaded.balance
    state = fresh_game(loaded)
    rival = state.rivals()[0]
    assert not translate.translates(rival, b.fx.start_turn - 1, b)
    assert translate.translates(rival, b.fx.start_turn, b)
    assert translate.translates(state.player, 0, b)


def test_forward_parity_and_settlement(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2023, 1))
    spot = rates.index_at(state, "latin_america", state.turn, b, d)
    fwd = hedges.forward_index(state, "latin_america", 12, b, d)
    # Brazil's and Mexico's rates are far above the US's: the forward is at a discount
    assert fwd < spot
    state, h = hedges.buy(state, PLAYER, "latin_america", 1_000_000, 3, b, d)
    assert h.settle_turn == state.turn + 3 and h.status == "open"
    total = 0
    for k in range(4):
        s = replace(state, turn=state.turn + k)
        s, entries, settled = hedges.mark_and_settle(s, b, d)
        for e in entries:
            assert sum(x.amount for x in e.lines) == 0
        total += sum(settled.values())
        state = replace(s, turn=state.turn)
    final = state.fx.hedges[0]
    assert final.status == "settled"
    s_m = rates.index_at(replace(state, turn=h.settle_turn), "latin_america", h.settle_turn, b, d)
    assert final.settled_cents == hedges.value_cents(h, s_m) == total


def test_value_is_exact() -> None:
    h = FxHedge(1, 1, EU, 1_000_001, 0, 3, 1_000_000, 1_000_003)
    assert hedges.value_cents(h, 1_000_000) == 3  # 3.000003 -> 3
    assert hedges.value_cents(h, 1_000_005) == -2


def test_forward_terms_and_regions(loaded: LoadedData) -> None:
    from tst.sim.errors import FinservRuleError

    b, d = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    with pytest.raises(FinservRuleError):
        hedges.buy(state, PLAYER, "north_america", 100, 3, b, d)
    hedges.buy(state, PLAYER, EU, 100, 24, b, d)  # M57: forwards run to 24 months
    with pytest.raises(FinservRuleError):
        hedges.buy(state, PLAYER, EU, 100, 25, b, d)


def test_policy_rates_follow_the_data_then_comove(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    f = d.fx
    assert f is not None
    s = replace(fresh_game(loaded), turn=ym_to_turn(2022, 12))
    assert rates.policy_rate(s, EU, b, d) == pytest.approx(f.history_rate(EU, s.turn))
    assert 1.0 < f.history_rate(EU, s.turn) < 3.0  # the ECB's 2022 rises
