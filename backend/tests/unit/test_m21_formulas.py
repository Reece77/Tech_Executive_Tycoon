"""M21 (formulas.md 38): capex, cost per good die at a yield, yield learning, the node-quality
rule, node prices, and the node timeline (history on every seed, seeded after 2025)."""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest

from tst.loader import LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.fabs import formulas as fx
from tst.sim.fabs import nodes as nd
from tst.sim.facilities.config import month_to_turn

DATA = Path(__file__).resolve().parents[2] / "data"


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


def test_capex_is_starts_times_capital_times_scale() -> None:
    # a 5 nm fab of 50,000 starts: 50,000 x 12 x $15,694 x 1.8 = $16.95B before overrun
    assert fx.capex_cents(50_000, 1_569_400, 1.8) == 50_000 * 12 * 1_569_400 * 18 // 10
    assert fx.capex_cents(50_000, 1_569_400, 1.8) / 100 == pytest.approx(16.949e9, rel=1e-3)
    # 7 nm by DUV costs 1.15x
    assert fx.capex_cents(10_000, 1_426_700, 1.8, 1.15) == round(
        10_000 * 12 * 1_426_700 * 1.8 * 1.15
    )


def test_build_months_and_first_yield_follow_the_node_age() -> None:
    assert fx.build_months(0, 36, 36, 24) == 36
    assert fx.build_months(-12, 36, 36, 24) == 36  # ordered before first volume
    assert fx.build_months(36, 36, 36, 24) == 24
    assert fx.yield_start(0, 36, 0.35, 0.7) == pytest.approx(0.35)
    assert fx.yield_start(18, 36, 0.35, 0.7) == pytest.approx(0.525)
    assert fx.yield_start(60, 36, 0.35, 0.7) == pytest.approx(0.7)
    assert fx.yield_start(-6, 36, 0.35, 0.7) == pytest.approx(0.35)


def test_yield_learns_toward_mature() -> None:
    rate = fx.learn_rate(0.075, 12, 12, 0, 0.02, 20)
    assert rate == pytest.approx(0.075)
    assert fx.next_yield(0.35, 0.9, rate) == pytest.approx(0.35 + 0.55 * 0.075)
    # 38.5 target 4: 35% to 80% within 24 months at skill 12 and no extra lead
    assert fx.months_to(0.8, 0.35, 0.9, rate) == 22  # in a game: one more for the first month
    # more skill and a research lead learn faster; the lead counts up to its cap
    assert fx.learn_rate(0.075, 16, 12, 10, 0.02, 20) == pytest.approx(0.075 * 16 / 12 * 1.2)
    assert fx.learn_rate(0.075, 12, 12, 50, 0.02, 20) == pytest.approx(0.075 * 1.4)
    assert fx.months_to(0.95, 0.35, 0.9, rate) is None


def test_cost_per_good_die_at_a_yield() -> None:
    # $9,000 a start, 60 chips, design yield 0.8, a mature fab (0.9 of 0.9): $187.50 + $8
    assert fx.die_cents(900_000, 60, 0.8, 0.9, 0.9, 800) == pytest.approx(900_000 / 48 + 800)
    # at half the mature yield, twice the wafer per good die
    assert fx.die_cents(900_000, 60, 0.8, 0.45, 0.9, 800) == pytest.approx(900_000 / 24 + 800)
    assert fx.die_cents(900_000, 60, 0.8, 0.0, 0.9, 800) == float("inf")


def test_node_quality_points() -> None:
    assert fx.node_quality_points(8, 6, 3) == 6  # two generations ahead: +6
    assert fx.node_quality_points(6, 6, 3) == 0
    assert fx.node_quality_points(4, 6, 3) == 0  # behind the median: nothing


def test_node_price_moves_with_the_index_and_the_edge() -> None:
    # the reference month: the reference price
    assert fx.node_price_cents(1_000_000, 1.5, 1.5, 2, 2, 0.12, 1.0) == pytest.approx(1_000_000)
    # one more generation behind: 12% less; one nearer the edge: dearer
    assert fx.node_price_cents(1_000_000, 1.5, 1.5, 3, 2, 0.12, 1.0) == pytest.approx(880_000)
    assert fx.node_price_cents(1_000_000, 1.5, 1.5, 1, 2, 0.12, 1.0) == pytest.approx(1e6 / 0.88)
    # the index and the capacity factor scale it
    assert fx.node_price_cents(1_000_000, 1.8, 1.5, 2, 2, 0.12, 0.9) == pytest.approx(1.08e6)


def test_tools_and_irr() -> None:
    assert fx.tools_needed(50_000, 2_000) == 25
    assert fx.tools_needed(10_001, 2_000) == 6
    # -100 now, +110 in 12 months: 10% a year
    flows = [-100.0] + [0.0] * 11 + [110.0]
    assert fx.irr(flows) == pytest.approx(0.10, abs=1e-6)
    assert fx.irr([1.0, 2.0]) is None


def test_history_holds_on_every_seed() -> None:
    """38.5 target 1: every foundry reaches every node on its nodes.yaml date, on any seed."""
    lg = loaded()
    nf = lg.game_data.nodes
    assert nf is not None
    expected = {}
    for f in nf.foundries:
        for n in nf.nodes:
            month = f.reaches.get(n.key) or n.first.get(f.key)
            if month is not None:
                expected[(f.key, n.key)] = month_to_turn(month)
    for seed in (1, 2, 3, 17, 2**40 + 5):
        tl = nd.timeline(seed, nf, lg.balance.fab)
        got = {k: v for k, v in tl.reach.items() if v <= nd.HISTORY_END}
        assert got == expected
    tl = nd.timeline(1, nf, lg.balance.fab)
    assert tl.foundry_has("tsmc", "n5", ym_to_turn(2020, 4))
    assert not tl.foundry_has("tsmc", "n5", ym_to_turn(2020, 3))
    assert tl.leading(ym_to_turn(2020, 6)) == "n5"
    assert tl.leading(ym_to_turn(2023, 1)) == "n3"
    assert not tl.foundry_has("intel", "n3", ym_to_turn(2039, 12))  # Intel skipped the class
    assert tl.reached("globalfoundries", ym_to_turn(2039, 12))[-1] == "n16"  # stopped in 2018


def test_future_nodes_arrive_in_their_windows_and_are_seeded() -> None:
    lg = loaded()
    nf = lg.game_data.nodes
    assert nf is not None
    a = nd.timeline(1, nf, lg.balance.fab)
    b = nd.build(1, nf, lg.balance.fab)
    assert a == b  # a pure function of the seed
    months = set()
    for seed in range(1, 11):
        tl = nd.timeline(seed, nf, lg.balance.fab)
        for i, fut in enumerate(nf.future):
            lag = max(f.lag.hi for f in nf.foundries if f.stops_at is None and f.euv_gate is None)
            assert fut.start_turn <= tl.arrival[fut.key] <= fut.start_turn + fut.months + lag
            prev = nf.node_keys()[nf.generation(fut.key) - 1]
            ratio = tl.wafer_cents[fut.key] / tl.wafer_cents[prev]
            assert 1.2 <= ratio <= 1.5
            assert 1.08 <= tl.capital_cents[fut.key] / tl.capital_cents[prev] <= 1.17
            if i == 0:
                months.add(tl.arrival[fut.key])
        assert ("smic", "a16") not in tl.reach  # without EUV, SMIC stays at 7 nm
        assert ("umc", "a16") not in tl.reach
    assert len(months) > 1


def test_capacity_follows_history_then_grows() -> None:
    lg = loaded()
    nf = lg.game_data.nodes
    assert nf is not None
    fb = lg.balance.fab
    tl = nd.timeline(1, nf, fb)
    tsmc = nf.foundry("tsmc")
    assert nd.capacity(tl, tsmc, 0, fb) == pytest.approx(420)
    assert nd.capacity(tl, tsmc, ym_to_turn(2025, 1), fb) == pytest.approx(1450)
    later = nd.capacity(tl, tsmc, ym_to_turn(2027, 1), fb)
    assert 1450 * 1.03**1 < later < 1450 * 1.09**2
    # through 2025 the market factor is exactly 1 without the player's slots (target 6)
    for t in range(0, nd.HISTORY_END + 1, 7):
        assert nd.price_factor(tl, nf, t, fb, 0.0) == 1.0
        assert nd.allocation_factor(tl, nf, t, fb, 0.0) == 1.0
    # the player's slots add capacity: prices fall a little
    assert nd.price_factor(tl, nf, ym_to_turn(2020, 1), fb, 50.0) < 1.0
    # after 2025 the rivals' seeded capacity moves it, within its bounds
    f = nd.price_factor(tl, nf, ym_to_turn(2030, 1), fb, 0.0)
    assert fb.capacity.bounds.lo <= f <= fb.capacity.bounds.hi
